"""SEC annual XBRL analysis with matched periods, filing evidence and immutable views."""

import datetime as dt
import hashlib
import json
import math
import os
import re
import threading
import time
import urllib.error
import urllib.request

import datasets

CIKS = {"AAPL": 320193, "MSFT": 789019}
LOCK = threading.Lock()
METRICS = {
    "revenue": (
        ["RevenueFromContractWithCustomerExcludingAssessedTax", "Revenues", "SalesRevenueNet"],
        "USD",
        True,
    ),
    "net_income": (["NetIncomeLoss"], "USD", True),
    "operating_income": (["OperatingIncomeLoss"], "USD", True),
    "operating_cash_flow": (["NetCashProvidedByUsedInOperatingActivities"], "USD", True),
    "capex": (["PaymentsToAcquirePropertyPlantAndEquipment"], "USD", True),
    "cash": (["CashAndCashEquivalentsAtCarryingValue"], "USD", False),
    "assets": (["Assets"], "USD", False),
    "liabilities": (["Liabilities"], "USD", False),
    "equity": (["StockholdersEquity"], "USD", False),
    "diluted_eps": (["EarningsPerShareDiluted"], "USD/shares", True),
}


def init_schema(c):
    c.executescript("""
        CREATE TABLE IF NOT EXISTS fundamental_automation (
            symbol TEXT PRIMARY KEY, status TEXT, message TEXT, next_attempt TEXT, checked TEXT
        );
        CREATE TABLE IF NOT EXISTS fundamental_auto_attempts (
            id INTEGER PRIMARY KEY, symbol TEXT, day TEXT, started TEXT
        );
        CREATE TABLE IF NOT EXISTS sec_raw (
            id INTEGER PRIMARY KEY, symbol TEXT, fetched_at TEXT,
            companyfacts TEXT, submissions TEXT
        );
        CREATE TABLE IF NOT EXISTS fundamental_snapshots (
            id TEXT PRIMARY KEY, symbol TEXT, created TEXT, payload TEXT
        );
        CREATE TABLE IF NOT EXISTS fundamental_current (
            symbol TEXT PRIMARY KEY, snapshot_id TEXT, raw_id INTEGER, fetched_at TEXT
        );
        CREATE TABLE IF NOT EXISTS fundamental_jobs (
            id INTEGER PRIMARY KEY, symbol TEXT, started TEXT, finished TEXT, status TEXT, message TEXT
        );
    """)
    c.execute(
        "UPDATE fundamental_jobs SET status='interrupted',finished=?,message=? WHERE status='running'",
        (datasets.now(), "Backend restarted before SEC sync completed"),
    )


def user_agent():
    value = os.environ.get("SEC_USER_AGENT", "").strip()
    if (
        not re.search(r"[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}", value)
        or "example.com" in value.lower()
        or "your-email" in value.lower()
    ):
        raise ValueError(
            "Set SEC_USER_AGENT to your app name and genuine contact email in backend/.env, then restart."
        )
    return value


def fetch_json(url):
    req = urllib.request.Request(
        url, headers={"User-Agent": user_agent(), "Accept": "application/json"}
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as response:
            body = response.read(20_000_001)
        if len(body) > 20_000_000:
            raise ValueError("SEC response exceeds the 20 MB limit")
        result = json.loads(body.decode("utf-8"))
        if not isinstance(result, dict):
            raise ValueError("SEC returned an unexpected JSON format")
        return result
    except urllib.error.HTTPError as e:
        if e.code == 403:
            raise ValueError(
                "SEC denied access (403). Check the contact User-Agent and SEC fair-access policy."
            ) from None
        if e.code == 429:
            raise ValueError(
                "SEC rate limit reached. Cached analysis is preserved; retry later."
            ) from None
        raise ValueError("SEC request failed; cached analysis is preserved.") from None
    except (urllib.error.URLError, OSError, TimeoutError, UnicodeError, json.JSONDecodeError):
        raise ValueError(
            "Could not read SEC data. Check connectivity; cached analysis is preserved."
        ) from None


def filing_url(cik, accession, document=None):
    if not re.fullmatch(r"\d{10}-\d{2}-\d{6}", str(accession)):
        raise ValueError("Invalid SEC accession number")
    base = f"https://www.sec.gov/Archives/edgar/data/{cik}/{accession.replace('-', '')}/"
    if document and re.fullmatch(r"[A-Za-z0-9_.-]+", document):
        return base + document
    return base + accession + "-index.html"


def fact_valid(f, cutoff, duration):
    try:
        start = dt.date.fromisoformat(f["start"]) if duration else None
        end = dt.date.fromisoformat(f["end"])
        filed = dt.date.fromisoformat(f["filed"])
        value = float(f["val"])
        return (
            f.get("form") in ("10-K", "10-K/A")
            and f.get("fp") == "FY"
            and re.fullmatch(r"\d{10}-\d{2}-\d{6}", str(f.get("accn", "")))
            and end <= filed <= cutoff
            and not isinstance(f["val"], bool)
            and math.isfinite(value)
            and (not duration or 330 <= (end - start).days <= 400)
        )
    except (ValueError, KeyError, TypeError, OverflowError):
        return False


def extract(facts, submissions, symbol, cutoff=None):
    if symbol not in CIKS:
        raise ValueError("SEC fundamentals currently support AAPL and MSFT")
    cik = CIKS[symbol]
    cutoff = cutoff or dt.datetime.now(dt.timezone.utc).date()
    try:
        if int(facts["cik"]) != cik or int(submissions["cik"]) != cik:
            raise ValueError()
        concepts = facts["facts"]["us-gaap"]
        if not isinstance(concepts, dict):
            raise ValueError()
    except (KeyError, TypeError, ValueError):
        raise ValueError(
            "SEC company identity or US-GAAP facts do not match the selected asset"
        ) from None

    recent = submissions.get("filings", {}).get("recent", {})
    reports = []
    forms = recent.get("form", [])
    for i, form in enumerate(forms):
        if form not in ("10-K", "10-K/A", "10-Q", "10-Q/A"):
            continue
        try:
            filed = recent["filingDate"][i]
            if dt.date.fromisoformat(filed) > cutoff:
                continue
            accn = recent["accessionNumber"][i]
            document = (
                recent.get("primaryDocument", [])[i]
                if i < len(recent.get("primaryDocument", []))
                else None
            )
            reports.append(
                {"form": form, "filed": filed, "accn": accn, "url": filing_url(cik, accn, document)}
            )
        except (KeyError, IndexError, ValueError, TypeError):
            continue
    reports.sort(key=lambda r: (r["filed"], r["accn"]), reverse=True)
    urls = {r["accn"]: r["url"] for r in reports}

    revenue_candidates = []
    for rank, tag in enumerate(METRICS["revenue"][0]):
        for f in concepts.get(tag, {}).get("units", {}).get("USD", []):
            if fact_valid(f, cutoff, True):
                revenue_candidates.append((f, tag, rank))
    if not revenue_candidates:
        raise ValueError(
            "No comparable annual entity-wide USD revenue facts were found; cached analysis retained"
        )
    anchor, _, _ = max(
        revenue_candidates,
        key=lambda item: (item[0]["end"], item[0]["filed"], item[0]["accn"], -item[2]),
    )
    accession = anchor["accn"]
    anchors = {}
    for f, tag, rank in sorted(revenue_candidates, key=lambda item: item[2], reverse=True):
        if f["accn"] == accession:
            anchors[f["end"]] = f
    periods = sorted(anchors.values(), key=lambda f: f["end"], reverse=True)[:3]

    def metric(key, period):
        tags, unit, duration = METRICS[key]
        for tag in tags:
            candidates = [
                f
                for f in concepts.get(tag, {}).get("units", {}).get(unit, [])
                if fact_valid(f, cutoff, duration)
                and f["accn"] == accession
                and f["end"] == period["end"]
                and (not duration or f.get("start") == period["start"])
            ]
            if not candidates:
                continue
            values = {float(f["val"]) for f in candidates}
            if len(values) != 1:
                return {
                    "value": None,
                    "unit": unit,
                    "issue": "Conflicting fact contexts; no value chosen",
                    "evidence": None,
                }
            f = max(candidates, key=lambda f: f["filed"])
            return {
                "value": float(f["val"]),
                "unit": unit,
                "issue": None,
                "evidence": {
                    "tag": "us-gaap/" + tag,
                    "unit": unit,
                    "start": f.get("start"),
                    "end": f["end"],
                    "filed": f["filed"],
                    "accn": accession,
                    "form": f["form"],
                    "url": urls.get(accession, filing_url(cik, accession)),
                },
            }
        return {
            "value": None,
            "unit": unit,
            "issue": "Comparable standard fact unavailable in this filing",
            "evidence": None,
        }

    years = []
    for period in periods:
        metrics = {key: metric(key, period) for key in METRICS}
        values = {key: m["value"] for key, m in metrics.items()}
        revenue = values["revenue"]

        def margin(key):
            return (
                values[key] / revenue * 100
                if revenue and revenue > 0 and values[key] is not None
                else None
            )

        cfo, capex = values["operating_cash_flow"], values["capex"]
        years.append(
            {
                "start": period["start"],
                "end": period["end"],
                "metrics": metrics,
                "derived": {
                    "net_margin": margin("net_income"),
                    "operating_margin": margin("operating_income"),
                    "free_cash_flow": (
                        cfo - capex
                        if cfo is not None and capex is not None and capex >= 0
                        else None
                    ),
                    "revenue_yoy": None,
                },
            }
        )
    for i, year in enumerate(years[:-1]):
        previous = years[i + 1]
        a, b = year["metrics"]["revenue"]["value"], previous["metrics"]["revenue"]["value"]
        contiguous = (
            dt.date.fromisoformat(year["start"]) - dt.date.fromisoformat(previous["end"])
        ).days == 1
        if contiguous and a is not None and b is not None and b > 0:
            year["derived"]["revenue_yoy"] = (a / b - 1) * 100
    return {
        "symbol": symbol,
        "company": facts.get("entityName", submissions.get("name", symbol)),
        "cik": cik,
        "source": "SEC EDGAR / US-GAAP",
        "extractor_version": "sec-annual-v1",
        "annual_filing": {
            "accn": accession,
            "filed": anchor["filed"],
            "form": anchor["form"],
            "url": urls.get(accession, filing_url(cik, accession)),
        },
        "years": years,
        "reports": reports[:12],
        "formulas": {
            "net_margin": "net_income / revenue × 100",
            "operating_margin": "operating_income / revenue × 100",
            "free_cash_flow": "operating_cash_flow - PaymentsToAcquirePropertyPlantAndEquipment",
            "revenue_yoy": "(current revenue / prior contiguous annual revenue - 1) × 100",
        },
        "limitations": [
            "Latest/as-restated annual report view, not a historical point-in-time dataset.",
            "Quarterly reports are linked; quarterly/TTM metrics are not computed.",
            "Standard USD facts only; custom tags and ambiguous contexts remain unavailable.",
            "Fundamentals are not inputs to the price model yet. No valuation target or buy/sell score.",
        ],
    }


def cached(connect, symbol):
    if symbol in ("EURUSD", "BTCUSD"):
        import cross_fundamentals

        return cross_fundamentals.cached(connect, symbol)
    if symbol not in CIKS:
        return {"symbol": symbol, "supported": False, "has_data": False}
    with connect() as c:
        row = c.execute(
            "SELECT s.id,s.payload,p.fetched_at FROM fundamental_current p JOIN fundamental_snapshots s "
            "ON s.id=p.snapshot_id WHERE p.symbol=?",
            (symbol,),
        ).fetchone()
        job = c.execute(
            "SELECT started,finished,status,message FROM fundamental_jobs WHERE symbol=? ORDER BY id DESC LIMIT 1",
            (symbol,),
        ).fetchone()
    return {
        "symbol": symbol,
        "supported": True,
        "has_data": bool(row),
        "snapshot_id": row["id"] if row else None,
        "fetched_at": row["fetched_at"] if row else None,
        "analysis": json.loads(row["payload"]) if row else None,
        "last_job": dict(job) if job else None,
    }


def sync(connect, symbol, fetcher=None, now=None):
    if symbol in ("EURUSD", "BTCUSD"):
        import cross_fundamentals

        return cross_fundamentals.sync(connect, symbol, fetcher, now)
    if symbol not in CIKS:
        raise ValueError(
            "Company fundamentals currently support AAPL and MSFT; FX/crypto fundamentals differ"
        )
    if not LOCK.acquire(blocking=False):
        raise ValueError("Another SEC sync is running. Wait for it to finish.")
    job_id = None
    now = now or dt.datetime.now(dt.timezone.utc)
    try:
        existing = cached(connect, symbol)
        if (
            existing["fetched_at"]
            and (now - dt.datetime.fromisoformat(existing["fetched_at"])).total_seconds() < 21600
        ):
            return {**existing, "cached": True}
        user_agent()
        with connect() as c:
            last = c.execute(
                "SELECT started FROM fundamental_jobs ORDER BY id DESC LIMIT 1"
            ).fetchone()
            if last and (now - dt.datetime.fromisoformat(last[0])).total_seconds() < 45:
                raise ValueError("Wait 45 seconds between SEC sync attempts.")
            job_id = c.execute(
                "INSERT INTO fundamental_jobs(symbol,started,status,message) VALUES(?,?,?,?)",
                (symbol, now.isoformat(), "running", "Fetching SEC filings and XBRL facts"),
            ).lastrowid
        fetcher = fetcher or fetch_json
        cik = f"{CIKS[symbol]:010d}"
        facts = fetcher(f"https://data.sec.gov/api/xbrl/companyfacts/CIK{cik}.json")
        time.sleep(0.15)
        submissions = fetcher(f"https://data.sec.gov/submissions/CIK{cik}.json")
        analysis = extract(facts, submissions, symbol, now.date())
        canonical = json.dumps(analysis, sort_keys=True, separators=(",", ":"), allow_nan=False)
        identity = hashlib.sha256(canonical.encode()).hexdigest()
        with connect() as c:
            raw_id = c.execute(
                "INSERT INTO sec_raw(symbol,fetched_at,companyfacts,submissions) VALUES(?,?,?,?)",
                (symbol, now.isoformat(), json.dumps(facts), json.dumps(submissions)),
            ).lastrowid
            c.execute(
                "INSERT OR IGNORE INTO fundamental_snapshots VALUES(?,?,?,?)",
                (identity, symbol, now.isoformat(), canonical),
            )
            c.execute(
                "INSERT INTO fundamental_current VALUES(?,?,?,?) ON CONFLICT(symbol) DO UPDATE SET "
                "snapshot_id=excluded.snapshot_id,raw_id=excluded.raw_id,fetched_at=excluded.fetched_at",
                (symbol, identity, raw_id, now.isoformat()),
            )
            c.execute(
                "UPDATE fundamental_jobs SET finished=?,status='succeeded',message=? WHERE id=?",
                (datasets.now(), "SEC annual analysis updated", job_id),
            )
        return {**cached(connect, symbol), "cached": False}
    except Exception:
        if job_id is not None:
            with connect() as c:
                c.execute(
                    "UPDATE fundamental_jobs SET finished=?,status='failed',message=? WHERE id=?",
                    (datasets.now(), "SEC sync failed; cached analysis preserved", job_id),
                )
        raise
    finally:
        LOCK.release()


class Runner:
    """Fundamental worker: persisted retry budget and no price-provider dependency."""

    def __init__(
        self, connect, syncer=None, clock=None, enabled=None, symbols=None, credential=None
    ):
        self.connect = connect
        self.symbols = symbols or list(CIKS)
        self.credential = credential or (lambda symbol: user_agent())
        self.syncer = syncer or (lambda symbol, now: sync(connect, symbol, now=now))
        self.clock = clock or (lambda: dt.datetime.now(dt.timezone.utc))
        self.enabled = (
            (os.getenv("AUTO_FUNDAMENTALS_ENABLED", "true").lower() in ("1", "true", "yes"))
            if enabled is None
            else enabled
        )
        self.stop_event = threading.Event()
        self.thread = None
        self.next_check = None
        self.last_error = None

    def state(self, symbol, status, message, next_attempt=None):
        with self.connect() as c:
            c.execute(
                "INSERT INTO fundamental_automation VALUES(?,?,?,?,?) ON CONFLICT(symbol) DO UPDATE SET "
                "status=excluded.status,message=excluded.message,next_attempt=excluded.next_attempt,checked=excluded.checked",
                (symbol, status, message, next_attempt, self.clock().isoformat()),
            )

    def tick(self, now=None):
        now = now or self.clock()
        requested = False
        for symbol in self.symbols:
            if not self.enabled:
                self.state(
                    symbol, "disabled", "Set AUTO_FUNDAMENTALS_ENABLED=true and restart to enable"
                )
                continue
            try:
                self.credential(symbol)
            except ValueError as error:
                self.state(
                    symbol,
                    "missing_contact",
                    str(error),
                )
                continue
            saved = cached(self.connect, symbol)
            if saved["fetched_at"]:
                due = dt.datetime.fromisoformat(saved["fetched_at"]) + dt.timedelta(hours=6)
                if due > now:
                    self.state(
                        symbol,
                        "up_to_date",
                        "Stored fundamental evidence is within its six-hour cache",
                        due.isoformat(),
                    )
                    continue
            with self.connect() as c:
                state = c.execute(
                    "SELECT * FROM fundamental_automation WHERE symbol=?", (symbol,)
                ).fetchone()
                attempts = c.execute(
                    "SELECT COUNT(*) FROM fundamental_auto_attempts WHERE symbol=? AND day=?",
                    (symbol, now.date().isoformat()),
                ).fetchone()[0]
                last_job = c.execute(
                    "SELECT started FROM fundamental_jobs ORDER BY id DESC LIMIT 1"
                ).fetchone()
            if (
                state
                and state["next_attempt"]
                and dt.datetime.fromisoformat(state["next_attempt"]) > now
            ):
                continue
            # Allow the four six-hour checks plus a bounded number of retries per UTC day.
            if attempts >= 6:
                tomorrow = dt.datetime.combine(
                    now.date() + dt.timedelta(days=1), dt.time(), dt.timezone.utc
                )
                self.state(
                    symbol,
                    "daily_limit",
                    "Six automatic attempts reached for this UTC day",
                    tomorrow.isoformat(),
                )
                continue
            if (
                requested
                or LOCK.locked()
                or (
                    last_job and (now - dt.datetime.fromisoformat(last_job[0])).total_seconds() < 45
                )
            ):
                self.state(symbol, "queued", "Waiting for the next fundamental worker check")
                continue
            requested = True
            with self.connect() as c:
                c.execute(
                    "INSERT INTO fundamental_auto_attempts(symbol,day,started) VALUES(?,?,?)",
                    (symbol, now.date().isoformat(), now.isoformat()),
                )
            self.state(symbol, "syncing", "Fetching fundamental observations and evidence")
            try:
                self.syncer(symbol, now)
                self.state(
                    symbol,
                    "updated",
                    "Fundamental evidence refreshed; stored data is available",
                    (now + dt.timedelta(hours=6)).isoformat(),
                )
            except Exception:
                self.state(
                    symbol,
                    "retry_scheduled",
                    "Fundamental sync failed; saved analysis retained. Use manual Sync for diagnostics.",
                    (now + dt.timedelta(minutes=30)).isoformat(),
                )

    def status(self):
        with self.connect() as c:
            states = [
                dict(r) for r in c.execute("SELECT * FROM fundamental_automation ORDER BY symbol")
            ]
        return {
            "enabled": self.enabled,
            "worker_running": bool(self.thread and self.thread.is_alive()),
            "next_check": self.next_check,
            "cache_hours": 6,
            "retry_minutes": 30,
            "max_attempts_per_utc_day": 6,
            "states": states,
            "last_error": self.last_error,
        }

    def start(self):
        if self.thread and self.thread.is_alive():
            return
        if not self.enabled:
            self.tick()
            return
        self.stop_event.clear()

        def work():
            while not self.stop_event.is_set():
                try:
                    self.tick()
                    self.last_error = None
                except Exception:
                    self.last_error = (
                        "Fundamental worker check failed; next local check will retry."
                    )
                self.next_check = (self.clock() + dt.timedelta(seconds=60)).isoformat()
                if self.stop_event.wait(60):
                    break

        self.thread = threading.Thread(target=work, name="fundamental-automation", daemon=True)
        self.thread.start()

    def stop(self):
        self.stop_event.set()
        if self.thread:
            self.thread.join(timeout=5)
