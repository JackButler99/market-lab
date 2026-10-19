"""Immutable close-series snapshots and additive SQLite migrations."""

import datetime as dt
import hashlib
import json


def now():
    return dt.datetime.now(dt.timezone.utc).isoformat()


def init_schema(c):
    c.executescript("""
        CREATE TABLE IF NOT EXISTS datasets (
            id TEXT PRIMARY KEY, symbol TEXT NOT NULL, created TEXT NOT NULL,
            metadata TEXT NOT NULL, observations TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS current_dataset (
            symbol TEXT PRIMARY KEY, dataset_id TEXT NOT NULL, updated TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS raw_responses (
            id INTEGER PRIMARY KEY, symbol TEXT, received TEXT, endpoint TEXT, payload TEXT
        );
        CREATE TABLE IF NOT EXISTS ingestion_jobs (
            id INTEGER PRIMARY KEY, symbol TEXT, started TEXT, finished TEXT,
            status TEXT, message TEXT, dataset_id TEXT, raw_id INTEGER
        );
        """)
    columns = {r[1] for r in c.execute("PRAGMA table_info(runs)")}
    for name in ("dataset_id", "model_version", "config_json"):
        if name not in columns:
            c.execute(f"ALTER TABLE runs ADD COLUMN {name} TEXT")
    c.execute(
        "UPDATE ingestion_jobs SET status='interrupted', finished=?, "
        "message='Server restarted before this sync finished.' WHERE status='running'",
        (now(),),
    )


def metadata_for(source):
    return {
        "source": source,
        "provider": "user" if source == "csv-import" else "synthetic-generator",
        "frequency": "daily" if source == "synthetic" else "observations-unspecified",
        "price_basis": "synthetic" if source == "synthetic" else "unspecified",
        "currency": "USD (assumed for imported CSV)",
        "calendar": "calendar-days",
    }


def snapshot(c, symbol, observations, metadata):
    rows = [{"date": r["date"], "close": float(r["close"])} for r in observations]
    rows.sort(key=lambda r: r["date"])
    canonical = json.dumps(
        {"symbol": symbol, "metadata": metadata, "observations": rows},
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    )
    identity = hashlib.sha256(canonical.encode()).hexdigest()
    c.execute(
        "INSERT OR IGNORE INTO datasets VALUES(?,?,?,?,?)",
        (identity, symbol, now(), json.dumps(metadata), json.dumps(rows)),
    )
    c.execute(
        "INSERT INTO current_dataset VALUES(?,?,?) ON CONFLICT(symbol) DO UPDATE SET "
        "dataset_id=excluded.dataset_id, updated=excluded.updated",
        (symbol, identity, now()),
    )
    return identity


def load(c, identity):
    row = c.execute("SELECT * FROM datasets WHERE id=?", (identity,)).fetchone()
    if row is None:
        raise ValueError("Dataset snapshot not found")
    result = dict(row)
    result["metadata"] = json.loads(result["metadata"])
    result["observations"] = json.loads(result["observations"])
    return result


def current(c, symbol):
    row = c.execute("SELECT dataset_id FROM current_dataset WHERE symbol=?", (symbol,)).fetchone()
    if row is None:
        raise ValueError("Current dataset not found")
    return load(c, row[0])


def summary(dataset):
    rows = dataset["observations"]
    return {
        "dataset_id": dataset["id"],
        "symbol": dataset["symbol"],
        "created": dataset["created"],
        "start_date": rows[0]["date"],
        "end_date": rows[-1]["date"],
        "observations": len(rows),
        **dataset["metadata"],
    }
