"""EURUSD macro and BTC network evidence. Latest data, never historical model inputs."""

import csv
import datetime as dt
import gzip
import socket
import ssl
import hashlib
import io
import json
import math
import os
import re
import urllib.error
import urllib.parse
import urllib.request

import fundamentals as sec

SYMBOLS = ("EURUSD", "BTCUSD")
ECB_KEY = "FM.D.U2.EUR.4F.KR.DFR.LEV"
FRED = {
    "us_rate": ("DFF", "US effective federal funds rate", "%", 10),
    "us_cpi": ("CPIAUCNS", "US CPI, all items (NSA)", "index 1982–84=100", 75),
    "ea_hicp": (
        "CP0000EZCCM086NEST",
        "Euro-area HICP, all items (NSA, changing composition)",
        "index 2025=100",
        75,
    ),
}
CHARTS = {
    "hash-rate": ("Estimated Bitcoin hash rate", "TH/s"),
    "difficulty": ("Bitcoin mining difficulty", "difficulty"),
    "n-transactions": ("Confirmed transactions per day", "transactions/day"),
    "total-bitcoins": ("Bitcoin supply issued", "BTC"),
}


class ProviderError(ValueError):
    """Safe provider diagnostics without URLs, response bodies, or credentials."""


def init_schema(c):
    c.execute(
        "CREATE TABLE IF NOT EXISTS cross_fundamental_raw (id INTEGER PRIMARY KEY, symbol TEXT, fetched_at TEXT, payload TEXT, snapshot_id TEXT)"
    )


def credential(symbol):
    if symbol in sec.CIKS:
        sec.user_agent()
    elif symbol == "EURUSD":
        if not re.fullmatch(r"[A-Za-z0-9]{32}", os.getenv("FRED_API_KEY", "").strip()):
            raise ValueError(
                "Set FRED_API_KEY to your 32-character FRED key in backend/.env, then restart."
            )
    elif symbol != "BTCUSD":
        raise ValueError("Unsupported fundamental symbol")


def fetch(source, now):
    """Only fixed provider URLs. Never expose query strings, upstream errors, or keys."""
    if source == "ecb":
        url = (
            "https://data-api.ecb.europa.eu/service/data/FM/D.U2.EUR.4F.KR.DFR.LEV?"
            + urllib.parse.urlencode(
                {
                    "format": "csvdata",
                    "startPeriod": (now.date() - dt.timedelta(days=60)).isoformat(),
                }
            )
        )
    elif source in FRED:
        url = "https://api.stlouisfed.org/fred/series/observations?" + urllib.parse.urlencode(
            {
                "series_id": FRED[source][0],
                "api_key": os.environ["FRED_API_KEY"].strip(),
                "file_type": "json",
                "observation_start": (now.date() - dt.timedelta(days=800)).isoformat(),
                "observation_end": now.date().isoformat(),
                "realtime_start": now.date().isoformat(),
                "realtime_end": now.date().isoformat(),
                "sort_order": "asc",
            }
        )
    elif source in CHARTS:
        url = (
            f"https://api.blockchain.info/charts/{source}?timespan=60days&format=json&sampled=false"
        )
    else:
        raise ValueError("Unknown fundamental source")
    try:
        req = urllib.request.Request(
            url,
            headers={
                "User-Agent": "MarketLab/1.0",
                "Accept": (
                    "application/vnd.ecb.data+csv;version=1.0.0"
                    if source == "ecb"
                    else "application/json"
                ),
                "Accept-Encoding": "identity",
            },
        )
        with urllib.request.urlopen(req, timeout=60 if source == "ecb" else 25) as response:
            body = response.read(8_000_001)
            encoding = response.headers.get("Content-Encoding", "").lower()
        if encoding == "gzip" or body.startswith(b"\x1f\x8b"):
            with gzip.GzipFile(fileobj=io.BytesIO(body)) as compressed:
                body = compressed.read(8_000_001)
        if len(body) > 8_000_000:
            raise ProviderError(
                f"{source}: response exceeds the 8 MB limit; saved analysis retained."
            )
        text = body.decode("utf-8-sig")
        if source == "ecb":
            parse_ecb_csv(text)
            return text
        return json.loads(text)
    except urllib.error.HTTPError as error:
        raise ProviderError(
            f"{source}: provider returned HTTP {error.code}. Check access, credentials and provider limits; saved analysis retained."
        ) from None
    except ProviderError:
        raise
    except (urllib.error.URLError, OSError) as error:
        reason = error.reason if isinstance(error, urllib.error.URLError) else error
        if isinstance(reason, ssl.SSLCertVerificationError):
            message = "TLS certificate verification failed. Check the Python trust store, system clock and any HTTPS-inspecting proxy; certificate verification remains enabled."
        elif isinstance(reason, ssl.SSLError):
            message = "TLS handshake failed. Check proxy/network access to the provider."
        elif isinstance(reason, (TimeoutError, socket.timeout)):
            message = "Connection/read timed out. Check provider availability and network/proxy access, then retry."
        elif isinstance(reason, socket.gaierror):
            message = "DNS lookup failed. Check your connection and DNS/proxy settings."
        else:
            message = "Network connection failed or was closed. Check firewall, proxy and provider access."
        raise ProviderError(f"{source}: {message} Saved analysis retained.") from None
    except (UnicodeError, json.JSONDecodeError, csv.Error, EOFError):
        raise ProviderError(
            f"{source}: response encoding or format is invalid; saved analysis retained."
        ) from None
    except Exception:
        raise ProviderError(
            f"{source}: unexpected response or transport failure; saved analysis retained."
        ) from None


def parse_ecb_csv(text):
    """Normalize ECB code headers and the human-readable CSV label variant."""
    if not isinstance(text, str):
        raise ProviderError("ecb: expected ECB CSV text; saved analysis retained.")
    reader = csv.DictReader(io.StringIO(text.lstrip("\ufeff")), strict=True)
    headers = reader.fieldnames or []
    aliases = {
        "KEY": {"key"},
        "TIME_PERIOD": {"time_period", "time period or range"},
        "OBS_VALUE": {"obs_value", "observation value"},
    }
    mapping = {}
    for code, names in aliases.items():
        matches = [name for name in headers if name.strip().casefold() in names]
        if len(matches) != 1:
            raise ProviderError(
                "ecb: response is not the expected ECB CSV. Required columns: KEY/Key, TIME_PERIOD/Time period or range, OBS_VALUE/Observation value; saved analysis retained."
            )
        mapping[code] = matches[0]
    multipliers = [
        name for name in headers if name.strip().casefold() in {"unit_mult", "unit multiplier"}
    ]
    if len(multipliers) > 1:
        raise ProviderError("ecb: ambiguous unit multiplier columns; saved analysis retained.")
    rows = []
    for raw in reader:
        if None in raw or any(raw.get(name) is None for name in mapping.values()):
            raise ProviderError("ecb: malformed CSV row; saved analysis retained.")
        row = {code: raw[name].strip() for code, name in mapping.items()}
        if row["KEY"] != ECB_KEY:
            raise ProviderError("ecb: series identity mismatch; saved analysis retained.")
        if multipliers:
            value = (raw.get(multipliers[0]) or "").strip()
            if not re.fullmatch(r"0(?:\s*\([^)]*\))?", value):
                raise ProviderError(
                    "ecb: unexpected or missing unit multiplier; saved analysis retained."
                )
        rows.append(row)
    if not rows:
        raise ProviderError("ecb: CSV contains no observations; saved analysis retained.")
    return rows


def numeric(value):
    if isinstance(value, bool):
        raise ValueError("Boolean is not a metric")
    result = float(value)
    if not math.isfinite(result):
        raise ValueError("Nonfinite metric")
    return result


def points(rows, now, positive=False):
    values = {}
    for row in rows:
        try:
            date = dt.date.fromisoformat(row["date"])
            if date > now.date() or row["value"] in (None, "", "."):
                continue
            value = numeric(row["value"])
            if positive and value <= 0:
                raise ValueError("Nonpositive observation")
            key = date.isoformat()
            if key in values and values[key] != value:
                raise ValueError("Conflicting observations")
            values[key] = value
        except (KeyError, TypeError):
            raise ValueError("Malformed provider observation") from None
    if not values:
        raise ValueError("No valid provider observations; saved analysis retained")
    return [{"date": d, "value": v} for d, v in sorted(values.items())]


def metric(label, unit, history, source, series_id, url, now, stale_days):
    latest = history[-1]
    return {
        "label": label,
        "unit": unit,
        "value": latest["value"],
        "observation_date": latest["date"],
        "source": source,
        "series_id": series_id,
        "url": url,
        "stale": (now.date() - dt.date.fromisoformat(latest["date"])).days > stale_days,
        "history": history,
        "issue": None,
    }


def yoy(item):
    rows = {r["date"]: r["value"] for r in item["history"]}
    latest = dt.date.fromisoformat(item["observation_date"])
    # Monthly observations use first-of-month labels; require the exact prior year/month.
    prior = latest.replace(year=latest.year - 1, day=1).isoformat()
    value = rows.get(prior)
    result = {
        **item,
        "label": item["label"] + " YoY",
        "unit": "%",
        "value": None,
        "history": [],
        "formula": "(index / same calendar month one year earlier - 1) × 100",
    }
    if latest.day != 1 or value is None or value <= 0:
        result["issue"] = "Exact year-ago monthly index unavailable"
    else:
        result["value"] = (item["value"] / value - 1) * 100
    return result


def macro(raw, now):
    metrics = {}
    for key, (series, label, unit, age) in FRED.items():
        body = raw[key]
        if not isinstance(body, dict) or "observations" not in body or body.get("error_code"):
            raise ValueError("Invalid FRED response")
        history = points(body["observations"], now, positive=key != "us_rate")
        metrics[key] = metric(
            label,
            unit,
            history,
            (
                "FRED / Federal Reserve"
                if key == "us_rate"
                else "FRED / BLS" if key == "us_cpi" else "FRED / Eurostat"
            ),
            series,
            f"https://fred.stlouisfed.org/series/{series}",
            now,
            age,
        )
    rows = parse_ecb_csv(raw["ecb"])
    history = points([{"date": r["TIME_PERIOD"], "value": r["OBS_VALUE"]} for r in rows], now)
    metrics["ea_rate"] = metric(
        "ECB deposit facility rate",
        "%",
        history,
        "European Central Bank",
        ECB_KEY,
        "https://data.ecb.europa.eu/data/datasets/FM/" + ECB_KEY,
        now,
        10,
    )
    metrics["us_inflation"] = yoy(metrics["us_cpi"])
    metrics["ea_inflation"] = yoy(metrics["ea_hicp"])
    us = {r["date"]: r["value"] for r in metrics["us_rate"]["history"]}
    ea = {r["date"]: r["value"] for r in history}
    common = sorted(set(us) & set(ea))
    spread = {
        "label": "US effective rate − ECB deposit rate",
        "unit": "percentage points",
        "value": None,
        "observation_date": None,
        "source": "Derived / FRED + ECB",
        "series_id": "DFF minus " + ECB_KEY,
        "url": "https://fred.stlouisfed.org/series/DFF",
        "stale": True,
        "history": [],
        "formula": "DFF minus ECB deposit facility rate on the same observation date",
        "issue": "No common observation date in the downloaded window",
    }
    if common:
        date = common[-1]
        spread.update(
            value=us[date] - ea[date],
            observation_date=date,
            stale=(now.date() - dt.date.fromisoformat(date)).days > 10,
            issue=None,
        )
    metrics["rate_spread"] = spread
    return {
        "symbol": "EURUSD",
        "kind": "macro",
        "title": "EURUSD · macroeconomic context",
        "metrics": metrics,
        "limitations": [
            "Latest revised observations, not a historical point-in-time dataset. Observation dates are not publication timestamps.",
            "DFF is an effective overnight market rate; ECB deposit facility is an administered rate. Their difference is context, not an exact policy-rate differential or trading signal.",
            "US CPI and euro-area HICP use different baskets. Both series here are not seasonally adjusted; index levels cannot be compared directly.",
            "Changing euro-area composition and index rebasing can affect comparisons. YoY requires the exact year-ago month.",
            "Missing or stale observations are flagged. Fundamentals do not feed the price model yet.",
        ],
    }


def bitcoin_history(key, observations, now):
    rows = []
    supply = {}
    timestamps = {}
    for observation in observations:
        try:
            timestamp = numeric(observation["x"])
            instant = dt.datetime.fromtimestamp(timestamp, dt.timezone.utc)
            date = instant.date()
            if date >= now.date():
                continue
            value = numeric(observation["y"])
            if value <= 0 or (key == "total-bitcoins" and value > 21_000_000):
                raise ValueError()
        except (KeyError, TypeError, ValueError, OverflowError, OSError):
            raise ProviderError(
                f"{key}: invalid completed-day observation; saved analysis retained."
            ) from None
        if timestamp in timestamps and timestamps[timestamp] != value:
            raise ProviderError(
                f"{key}: conflicting values at the same timestamp; saved analysis retained."
            )
        timestamps[timestamp] = value
        if key == "total-bitcoins":
            # Issued supply is a stock, not an amount to sum or average across a day.
            label = date.isoformat()
            if label not in supply or timestamp > supply[label][0]:
                supply[label] = (timestamp, value, instant.isoformat())
        else:
            rows.append({"date": date.isoformat(), "value": value})
    if key == "total-bitcoins":
        rows = [{"date": date, "value": item[1]} for date, item in supply.items()]
    try:
        history = points(rows, now, positive=True)
    except ValueError:
        raise ProviderError(
            f"{key}: no valid daily observations or conflicting daily values; saved analysis retained."
        ) from None
    if key == "total-bitcoins":
        for item in history:
            item["source_timestamp"] = supply[item["date"]][2]
    return history


def bitcoin(raw, now):
    metrics = {}
    for key, (label, unit) in CHARTS.items():
        body = raw[key]
        if (
            not isinstance(body, dict)
            or body.get("status") != "ok"
            or body.get("unit")
            not in {
                "hash-rate": {"TH/s", "Hash Rate", "Hash Rate TH/s"},
                "difficulty": {"difficulty", "Difficulty"},
                "n-transactions": {"transactions/day", "Transactions"},
                "total-bitcoins": {"BTC"},
            }[key]
            or not isinstance(body.get("values"), list)
        ):
            raise ProviderError(
                f"{key}: unsupported Blockchain.com chart schema or unit; saved analysis retained."
            )
        history = bitcoin_history(key, body["values"], now)
        metrics[key] = metric(
            label,
            unit,
            history,
            "Blockchain.com",
            key,
            f"https://www.blockchain.com/explorer/charts/{key}",
            now,
            3,
        )
        if key == "total-bitcoins":
            metrics[key]["observation_timestamp"] = history[-1]["source_timestamp"]
            metrics[key][
                "sampling_policy"
            ] = "Last available observation per completed UTC day; not a guaranteed midnight close"
        prev = (dt.date.fromisoformat(history[-1]["date"]) - dt.timedelta(days=7)).isoformat()
        old = next((r["value"] for r in history if r["date"] == prev), None)
        metrics[key]["change_7d_pct"] = (
            (history[-1]["value"] / old - 1) * 100 if old and old > 0 else None
        )
    return {
        "symbol": "BTCUSD",
        "kind": "network",
        "title": "Bitcoin · network fundamentals",
        "metrics": metrics,
        "limitations": [
            "Blockchain.com is a third-party network-data provider, not an official financial reporting authority.",
            "Hash rate is estimated. Transactions are not users; issued supply is not liquid supply and includes lost coins.",
            "Current incomplete UTC day is excluded; data may still be revised. Stale means the newest observation is over three days old.",
            "Issued supply uses the last available timestamp per completed UTC day, not a sum or average. The provider may not supply a true end-of-day observation; source timestamps are retained in the snapshot.",
            "Seven-day changes require an exact observation seven calendar days earlier. No interpolation is used.",
            "No on-chain valuation, exchange-flow coverage, buy/sell rating or price-model input is implied.",
        ],
    }


def cached(connect, symbol):
    with connect() as c:
        row = c.execute(
            "SELECT s.id,s.payload,p.fetched_at FROM fundamental_current p JOIN fundamental_snapshots s ON s.id=p.snapshot_id WHERE p.symbol=?",
            (symbol,),
        ).fetchone()
        job = c.execute(
            "SELECT started,finished,status,message FROM fundamental_jobs WHERE symbol=? ORDER BY id DESC LIMIT 1",
            (symbol,),
        ).fetchone()
    analysis = json.loads(row["payload"]) if row else None
    if analysis:
        today = dt.datetime.now(dt.timezone.utc).date()
        for item in analysis["metrics"].values():
            age_limit = (
                3
                if symbol == "BTCUSD"
                else 75 if item["series_id"] in ("CPIAUCNS", "CP0000EZCCM086NEST") else 10
            )
            item["stale"] = (
                not item["observation_date"]
                or (today - dt.date.fromisoformat(item["observation_date"])).days > age_limit
            )
    return {
        "symbol": symbol,
        "supported": True,
        "has_data": bool(row),
        "snapshot_id": row["id"] if row else None,
        "fetched_at": row["fetched_at"] if row else None,
        "analysis": analysis,
        "last_job": dict(job) if job else None,
    }


def sync(connect, symbol, fetcher=None, now=None):
    now = now or dt.datetime.now(dt.timezone.utc)
    if symbol not in SYMBOLS:
        raise ValueError("Unsupported fundamental symbol")
    if not sec.LOCK.acquire(blocking=False):
        raise ValueError("Another fundamental sync is running; wait for it to finish")
    job = None
    try:
        saved = cached(connect, symbol)
        if (
            saved["fetched_at"]
            and (now - dt.datetime.fromisoformat(saved["fetched_at"])).total_seconds() < 21600
        ):
            return {**saved, "cached": True}
        credential(symbol)
        with connect() as c:
            last = c.execute(
                "SELECT started FROM fundamental_jobs ORDER BY id DESC LIMIT 1"
            ).fetchone()
            if last and (now - dt.datetime.fromisoformat(last[0])).total_seconds() < 45:
                raise ValueError("Wait 45 seconds between fundamental sync attempts")
            job = c.execute(
                "INSERT INTO fundamental_jobs(symbol,started,status,message) VALUES(?,?,?,?)",
                (symbol, now.isoformat(), "running", "Fetching macro or Bitcoin network evidence"),
            ).lastrowid
        loader = fetcher or fetch
        sources = [*FRED, "ecb"] if symbol == "EURUSD" else list(CHARTS)
        raw = {key: loader(key, now) for key in sources}
        analysis = macro(raw, now) if symbol == "EURUSD" else bitcoin(raw, now)
        analysis["extractor_version"] = "cross-fundamental-v1"
        payload = json.dumps(analysis, sort_keys=True, separators=(",", ":"), allow_nan=False)
        identity = hashlib.sha256(payload.encode()).hexdigest()
        raw_json = json.dumps(raw, allow_nan=False)
        secret = os.getenv("FRED_API_KEY", "").strip()
        if secret:
            raw_json = raw_json.replace(secret, "[redacted]")
        with connect() as c:
            c.execute(
                "INSERT INTO cross_fundamental_raw(symbol,fetched_at,payload,snapshot_id) VALUES(?,?,?,?)",
                (symbol, now.isoformat(), raw_json, identity),
            )
            c.execute(
                "INSERT OR IGNORE INTO fundamental_snapshots VALUES(?,?,?,?)",
                (identity, symbol, now.isoformat(), payload),
            )
            c.execute(
                "INSERT INTO fundamental_current VALUES(?,?,?,?) ON CONFLICT(symbol) DO UPDATE SET snapshot_id=excluded.snapshot_id,raw_id=excluded.raw_id,fetched_at=excluded.fetched_at",
                (symbol, identity, None, now.isoformat()),
            )
            c.execute(
                "UPDATE fundamental_jobs SET status='succeeded',finished=?,message=? WHERE id=?",
                (now.isoformat(), "Fundamental evidence updated", job),
            )
        return {**cached(connect, symbol), "cached": False}
    except Exception as error:
        if job is None:
            raise
        if job is not None:
            with connect() as c:
                c.execute(
                    "UPDATE fundamental_jobs SET status='failed',finished=?,message=? WHERE id=?",
                    (now.isoformat(), "Fundamental sync failed; saved analysis retained", job),
                )
        if isinstance(error, ProviderError):
            raise ValueError(str(error)) from None
        # No provider URLs, keys, payloads, or exceptions reach HTTP logs or browser.
        raise ValueError(
            "Fundamental sync failed. Check provider access and settings; saved analysis retained."
        ) from None
    finally:
        sec.LOCK.release()
