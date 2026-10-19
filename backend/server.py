"""Local research API with versioned datasets and on-demand daily-market ingestion."""

from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
from pathlib import Path
import csv, io, json, math, random, sqlite3, statistics, datetime, urllib.parse
import threading
from contextlib import contextmanager

from dotenv import load_dotenv
import datasets
import deploy_config
import market_data
import automation
import fundamentals
import insights
import cross_fundamentals

load_dotenv(Path(__file__).parent / ".env")
DATA_LOCK = threading.Lock()
AUTOMATION = None
FUNDAMENTALS_AUTOMATION = None

DB = deploy_config.database_path()
if not deploy_config.production():
    DB.parent.mkdir(parents=True, exist_ok=True)
ASSETS = {
    "AAPL": ("Apple", "Equity", 210),
    "MSFT": ("Microsoft", "Equity", 430),
    "EURUSD": ("Euro / US Dollar", "Forex", 1.09),
    "BTCUSD": ("Bitcoin", "Crypto", 67000),
}


@contextmanager
def conn():
    c = sqlite3.connect(DB, timeout=30)
    c.row_factory = sqlite3.Row
    try:
        with c:
            yield c
    finally:
        c.close()


def init():
    with conn() as c:
        c.execute("PRAGMA journal_mode=WAL")
        c.executescript(
            (
                "CREATE TABLE IF NOT EXISTS prices(symbol TEXT,date TEXT,close REAL,source "
                "TEXT,PRIMARY KEY(symbol,date)); CREATE TABLE IF NOT EXISTS runs(id INTEGER PRIMARY"
                " KEY,created TEXT,symbol TEXT,model TEXT,horizon INTEGER,mae REAL,baseline_mae "
                "REAL,payload TEXT);"
            )
        )
        for i, (s, (_, _, start)) in enumerate(ASSETS.items()):
            if c.execute("SELECT 1 FROM prices WHERE symbol=?", (s,)).fetchone():
                continue
            r = random.Random(41 + i)
            price = start
            for day in range(420):
                price *= math.exp(r.gauss(0.0003, 0.013 if s != "EURUSD" else 0.003))
                date = (datetime.date(2024, 1, 1) + datetime.timedelta(days=day)).isoformat()
                c.execute("INSERT INTO prices VALUES(?,?,?,?)", (s, date, price, "synthetic"))

        datasets.init_schema(c)
        automation.init_schema(c)
        fundamentals.init_schema(c)
        cross_fundamentals.init_schema(c)
        for symbol in ASSETS:
            if c.execute("SELECT 1 FROM current_dataset WHERE symbol=?", (symbol,)).fetchone():
                continue
            rows = [
                dict(r)
                for r in c.execute("SELECT * FROM prices WHERE symbol=? ORDER BY date", (symbol,))
            ]
            datasets.snapshot(c, symbol, rows, datasets.metadata_for(rows[-1]["source"]))


def prices(s):
    with conn() as c:
        return [
            dict(x) for x in c.execute("SELECT * FROM prices WHERE symbol=? ORDER BY date", (s,))
        ]


def predict(history, model, h):
    if model == "naive":
        return history[-1]
    # Rolling log-price regression: uses only observations available at prediction time.
    y = [math.log(x) for x in history[-30:]]
    n = len(y)
    xm = (n - 1) / 2
    ym = statistics.mean(y)
    slope = sum((i - xm) * (v - ym) for i, v in enumerate(y)) / sum((i - xm) ** 2 for i in range(n))
    return math.exp(ym + slope * (n - 1 + h - xm))


def experiment(s, model, h, dataset_id=None):
    with conn() as c:
        dataset = datasets.load(c, dataset_id) if dataset_id else datasets.current(c, s)
    if dataset["symbol"] != s:
        raise ValueError("Dataset does not belong to the selected asset")
    rows = dataset["observations"]
    metadata = dataset["metadata"]
    dates = market_data.future_dates(rows[-1]["date"], h, metadata["calendar"])
    y = [x["close"] for x in rows]
    start = min(max(60, int(len(y) * 0.8)), len(y) - h - 9)
    errors = []
    base = []
    residual = []
    backtest = []
    for t in range(start, len(y) - h + 1):
        guess = predict(y[:t], model, h)
        actual = y[t + h - 1]
        errors.append(abs(guess - actual))
        base.append(abs(y[t - 1] - actual))
        residual.append(actual - guess)
        backtest.append({"date": rows[t + h - 1]["date"], "actual": actual, "predicted": guess})
    # Exploratory empirical residual bands, not calibrated confidence intervals.
    residual.sort()
    lo = residual[int(0.1 * (len(residual) - 1))]
    hi = residual[int(0.9 * (len(residual) - 1))]
    forecast = []
    for k in range(1, h + 1):
        v = predict(y, model, k)
        forecast.append(
            {
                "date": dates[k - 1],
                "predicted": v,
                "lower": max(0, v + lo),
                "upper": v + hi,
            }
        )
    return {
        "symbol": s,
        "model": model,
        "horizon": h,
        "mae": statistics.mean(errors),
        "baseline_mae": statistics.mean(base),
        "samples": len(errors),
        "train_end": rows[start - 1]["date"],
        "backtest": backtest,
        "forecast": forecast,
        "band_note": "Exploratory 10–90% historical residual band; not calibrated.",
        "source": metadata["source"],
        "dataset_id": dataset["id"],
        "dataset": datasets.summary(dataset),
        "model_version": "trend-v1" if model == "trend" else "naive-v1",
        "config": {
            "model": model,
            "horizon": h,
            "window": 30 if model == "trend" else 1,
            "validation": "walk-forward",
            "evaluation_start_index": start,
            "calendar": metadata["calendar"],
            "calendar_library": market_data.calendars.__version__,
        },
    }


def save_experiment(result, origin="manual"):
    result["origin"] = origin
    with conn() as c:
        cursor = c.execute(
            "INSERT OR IGNORE INTO runs(created,symbol,model,horizon,mae,baseline_mae,payload,"
            "dataset_id,model_version,config_json,origin) VALUES(?,?,?,?,?,?,?,?,?,?,?)",
            (
                datasets.now(),
                result["symbol"],
                result["model"],
                result["horizon"],
                result["mae"],
                result["baseline_mae"],
                json.dumps(result),
                result["dataset_id"],
                result["model_version"],
                json.dumps(result["config"]),
                origin,
            ),
        )
        if cursor.rowcount:
            result["id"] = cursor.lastrowid
        else:
            result["id"] = c.execute(
                "SELECT id FROM runs WHERE dataset_id=? AND model=? AND model_version=? AND horizon=? AND origin=?",
                (
                    result["dataset_id"],
                    result["model"],
                    result["model_version"],
                    result["horizon"],
                    origin,
                ),
            ).fetchone()[0]
    return result


def sync_market(symbol):
    if symbol not in market_data.SUPPORTED:
        raise ValueError("API sync supports AAPL, MSFT, EURUSD and BTCUSD")
    if not DATA_LOCK.acquire(blocking=False):
        raise ValueError("Another ingestion is running. Try again after it finishes.")
    job_id = None
    try:
        with conn() as c:
            last = c.execute(
                "SELECT started FROM ingestion_jobs ORDER BY id DESC LIMIT 1"
            ).fetchone()
            if (
                last
                and (
                    datetime.datetime.now(datetime.timezone.utc)
                    - datetime.datetime.fromisoformat(last[0])
                ).total_seconds()
                < 15
            ):
                raise ValueError("Wait 15 seconds between provider sync attempts.")
            job_id = c.execute(
                "INSERT INTO ingestion_jobs(symbol,started,status,message) VALUES(?,?,?,?)",
                (symbol, datasets.now(), "running", "Fetching daily observations"),
            ).lastrowid
        rows, raw = market_data.fetch_daily(symbol)
        with conn() as c:
            previous = datasets.current(c, symbol)
            # Never mix API history with synthetic or user-imported observations.
            if previous["metadata"]["source"] == "alphavantage":
                rows = market_data.validate_merge(symbol, previous["observations"], rows)
            meta = market_data.metadata(symbol, rows)
            raw_id = c.execute(
                "INSERT INTO raw_responses(symbol,received,endpoint,payload) VALUES(?,?,?,?)",
                (symbol, datasets.now(), market_data.ENDPOINT, raw),
            ).lastrowid
            identity = datasets.snapshot(c, symbol, rows, meta)
            c.execute("DELETE FROM prices WHERE symbol=?", (symbol,))
            c.executemany(
                "INSERT INTO prices VALUES(?,?,?,?)",
                [(symbol, r["date"], r["close"], meta["source"]) for r in rows],
            )
            changed = identity != previous["id"]
            message = "Dataset updated" if changed else "Already up to date; snapshot reused"
            c.execute(
                "UPDATE ingestion_jobs SET finished=?,status='succeeded',message=?,dataset_id=?,raw_id=? WHERE id=?",
                (datasets.now(), message, identity, raw_id, job_id),
            )
        return {
            "symbol": symbol,
            "dataset_id": identity,
            "rows": len(rows),
            "changed": changed,
            "message": message,
        }
    except Exception:
        if job_id is not None:
            with conn() as c:
                c.execute(
                    "UPDATE ingestion_jobs SET finished=?,status='failed',message=? WHERE id=?",
                    (
                        datasets.now(),
                        "Sync failed; previous dataset preserved. Check key, quota, connectivity or data quality.",
                        job_id,
                    ),
                )
        raise
    finally:
        DATA_LOCK.release()


class APIActions:
    """Routes shared by the local HTTP server and the production WSGI adapter."""

    def do_OPTIONS(self):
        self.send(200, {})

    def do_GET(self):
        if not deploy_config.authorized(self.headers, self.path):
            return self.send(401, {"error": "API authorization required"})
        path = urllib.parse.urlparse(self.path)
        q = urllib.parse.parse_qs(path.query)
        try:
            if path.path == "/health":
                return self.send(200, {"status": "ok"})
            if path.path == "/api/fundamentals/automation":
                return self.send(
                    200,
                    (
                        FUNDAMENTALS_AUTOMATION.status()
                        if FUNDAMENTALS_AUTOMATION
                        else {"enabled": False, "worker_running": False, "states": []}
                    ),
                )
            if path.path == "/api/fundamentals/insights":
                symbol = q.get("symbol", ["AAPL"])[0]
                if symbol not in insights.SUPPORTED:
                    raise ValueError("Unsupported fundamental insight symbol")
                saved = fundamentals.cached(conn, symbol)
                identity = q.get("snapshot_id", [None])[0]
                if identity and identity != saved.get("snapshot_id"):
                    with conn() as c:
                        row = c.execute(
                            "SELECT payload,created FROM fundamental_snapshots WHERE id=? AND symbol=?",
                            (identity, symbol),
                        ).fetchone()
                    if not row:
                        raise ValueError("Fundamental snapshot not found for this symbol")
                    saved = {
                        "has_data": True,
                        "snapshot_id": identity,
                        "analysis": json.loads(row["payload"]),
                        "fetched_at": row["created"],
                        "last_job": None,
                    }
                result = insights.build(saved, symbol, q.get("period", [None])[0])
                return self.send(200, result)
            if path.path == "/api/fundamentals":
                return self.send(200, fundamentals.cached(conn, q.get("symbol", ["AAPL"])[0]))
            if path.path == "/api/automation":
                runner = AUTOMATION or automation.Runner(
                    conn, sync_market, experiment, save_experiment
                )
                return self.send(200, runner.status())
            if path.path == "/api/forecast":
                with conn() as c:
                    row = c.execute(
                        "SELECT id,payload FROM runs WHERE symbol=? AND dataset_id=? AND model=? "
                        "AND horizon=? AND origin='automatic' ORDER BY id DESC LIMIT 1",
                        (
                            q.get("symbol", [""])[0],
                            q.get("dataset_id", [""])[0],
                            q.get("model", ["trend"])[0],
                            int(q.get("horizon", [7])[0]),
                        ),
                    ).fetchone()
                return self.send(
                    200, {**json.loads(row["payload"]), "id": row["id"]} if row else None
                )
            if path.path == "/api/dashboard":
                assets = []
                with conn() as c:
                    for symbol, (name, kind, _) in ASSETS.items():
                        ds = datasets.current(c, symbol)
                        rows = ds["observations"]
                        job = c.execute(
                            "SELECT * FROM ingestion_jobs WHERE symbol=? ORDER BY id DESC LIMIT 1",
                            (symbol,),
                        ).fetchone()
                        successful = c.execute(
                            "SELECT finished FROM ingestion_jobs WHERE symbol=? AND dataset_id=? "
                            "AND status='succeeded' ORDER BY id DESC LIMIT 1",
                            (symbol, ds["id"]),
                        ).fetchone()
                        assets.append(
                            {
                                "symbol": symbol,
                                "name": name,
                                "kind": kind,
                                "price": rows[-1]["close"],
                                "change": (rows[-1]["close"] / rows[-2]["close"] - 1) * 100,
                                "source": ds["metadata"]["source"],
                                "as_of": rows[-1]["date"],
                                **datasets.summary(ds),
                                "last_sync": dict(job) if job else None,
                                "fetched_at": successful[0] if successful else None,
                            }
                        )
                    runs = [
                        dict(r)
                        for r in c.execute(
                            "SELECT id,created,symbol,model,horizon,mae,baseline_mae,dataset_id,model_version,origin FROM runs ORDER BY id DESC LIMIT 20"
                        )
                    ]
                return self.send(
                    200,
                    {
                        "assets": assets,
                        "runs": runs,
                        "pipeline": {
                            "storage": "SQLite",
                            "mode": "Backend-local automation / manual override",
                            "last_checked": datasets.now(),
                        },
                    },
                )
            if path.path == "/api/prices":
                symbol = q.get("symbol", ["AAPL"])[0]
                if symbol not in ASSETS:
                    raise ValueError("Unknown symbol")
                return self.send(200, prices(symbol))
            if path.path == "/api/datasets":
                with conn() as c:
                    if "id" in q:
                        ds = datasets.load(c, q["id"][0])
                        return self.send(
                            200, {**datasets.summary(ds), "prices": ds["observations"]}
                        )
                    symbol = q.get("symbol", ["AAPL"])[0]
                    if symbol not in ASSETS:
                        raise ValueError("Unknown symbol")
                    ids = c.execute(
                        "SELECT id FROM datasets WHERE symbol=? ORDER BY created DESC LIMIT 100",
                        (symbol,),
                    )
                    return self.send(
                        200, [datasets.summary(datasets.load(c, r[0])) for r in ids.fetchall()]
                    )
            self.send(404, {"error": "Not found"})
        except (ValueError, KeyError, TypeError) as e:
            self.send(400, {"error": str(e)})

    def do_POST(self):
        if not deploy_config.authorized(self.headers, self.path):
            return self.send(401, {"error": "API authorization required"})
        try:
            size = int(self.headers.get("Content-Length", 0))
            if size < 1 or size > 2_000_000:
                return self.send(413, {"error": "Request body must be between 1 byte and 2 MB"})
            data = json.loads(self.rfile.read(size))
            if not isinstance(data, dict):
                raise ValueError("Expected a JSON object")
            symbol = data.get("symbol", "AAPL")
            if symbol not in ASSETS:
                raise ValueError("Unknown symbol")
            if self.path == "/api/fundamentals/sync":
                return self.send(200, fundamentals.sync(conn, symbol))
            if self.path == "/api/sync":
                return self.send(200, sync_market(symbol))
            if self.path == "/api/experiments":
                model = data.get("model", "trend")
                horizon = int(data.get("horizon", 7))
                if model not in ("trend", "naive") or horizon not in (1, 7, 14, 30):
                    raise ValueError("Invalid model or horizon")
                result = experiment(symbol, model, horizon, data.get("dataset_id"))
                result = save_experiment(result)
                return self.send(200, result)
            if self.path == "/api/import":
                reader = csv.DictReader(io.StringIO(data.get("csv", "").lstrip("\ufeff")))
                if not reader.fieldnames or not {"date", "close"} <= set(reader.fieldnames):
                    raise ValueError("CSV requires date,close headers")
                parsed = {}
                for row in reader:
                    date = datetime.date.fromisoformat(row["date"]).isoformat()
                    value = float(row["close"])
                    if not math.isfinite(value) or value <= 0:
                        raise ValueError("Close must be finite and positive")
                    parsed[date] = value
                if len(parsed) < 100:
                    raise ValueError("Provide at least 100 unique dates; columns: date,close")
                rows = [{"date": d, "close": v} for d, v in sorted(parsed.items())]
                with DATA_LOCK, conn() as c:
                    c.execute("DELETE FROM prices WHERE symbol=?", (symbol,))
                    c.executemany(
                        "INSERT INTO prices VALUES(?,?,?,?)",
                        [(symbol, r["date"], r["close"], "csv-import") for r in rows],
                    )
                    identity = datasets.snapshot(
                        c, symbol, rows, datasets.metadata_for("csv-import")
                    )
                return self.send(200, {"rows": len(rows), "symbol": symbol, "dataset_id": identity})
            self.send(404, {"error": "Not found"})
        except (ValueError, KeyError, TypeError, OverflowError) as e:
            self.send(400, {"error": str(e)})
        except Exception:
            self.send(
                500,
                {"error": "Processing failed; previous data has not been intentionally replaced."},
            )


class Handler(APIActions, BaseHTTPRequestHandler):
    def send(self, code, data):
        body = json.dumps(data, allow_nan=False).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Cache-Control", "no-store")
        for key, value in deploy_config.cors(self.headers.get("Origin", "")).items():
            self.send_header(key, value)
        self.end_headers()
        self.wfile.write(body)


if __name__ == "__main__":
    if deploy_config.production():
        raise SystemExit("Production must use python serve.py (Waitress WSGI)")
    host, port = deploy_config.validate()
    # Bind before starting the scheduler so a second server cannot start a second worker.
    http = ThreadingHTTPServer((host, port), Handler)
    init()
    AUTOMATION = automation.Runner(conn, sync_market, experiment, save_experiment)
    AUTOMATION.start()
    FUNDAMENTALS_AUTOMATION = fundamentals.Runner(
        conn, symbols=["AAPL", "MSFT", "EURUSD", "BTCUSD"], credential=cross_fundamentals.credential
    )
    FUNDAMENTALS_AUTOMATION.start()
    print(f"Research API: http://{host}:{port} — backend automation configured", flush=True)
    try:
        http.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        FUNDAMENTALS_AUTOMATION.stop()
        AUTOMATION.stop()
        http.server_close()
