"""Backend-local scheduler. Checks SQLite frequently; calls the provider only when due."""

import datetime as dt
import os
import threading

import datasets
import market_data

UTC = dt.timezone.utc


def settings():
    def flag(key, default="true"):
        return os.getenv(key, default).lower() in ("1", "true", "yes")

    return {
        "sync_enabled": flag("AUTO_SYNC_ENABLED"),
        "forecast_enabled": flag("AUTO_FORECAST_ENABLED"),
        "symbols": ["AAPL", "MSFT", "EURUSD", "BTCUSD"],
        "poll_seconds": 60,
        "close_delay_minutes": 60,
        "retry_minutes": 30,
        "max_attempts_per_day": 3,
        "model": "trend",
        "horizon": 7,
    }


def init_schema(c):
    c.executescript("""
        CREATE TABLE IF NOT EXISTS automation_state (
            symbol TEXT PRIMARY KEY, target_session TEXT, sync_status TEXT,
            sync_message TEXT, sync_retry_at TEXT, forecast_status TEXT,
            forecast_message TEXT, forecast_retry_at TEXT, forecast_id INTEGER,
            last_checked TEXT
        );
        CREATE TABLE IF NOT EXISTS automation_attempts (
            id INTEGER PRIMARY KEY, symbol TEXT, day TEXT, target_session TEXT,
            started TEXT, finished TEXT, status TEXT
        );
        """)
    if "origin" not in {r[1] for r in c.execute("PRAGMA table_info(runs)")}:
        c.execute("ALTER TABLE runs ADD COLUMN origin TEXT NOT NULL DEFAULT 'manual'")
    c.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS automatic_run_once ON "
        "runs(dataset_id,model,model_version,horizon) WHERE origin='automatic'"
    )
    c.execute(
        "UPDATE automation_attempts SET status='interrupted',finished=? WHERE status='running'",
        (datasets.now(),),
    )


def release_window(now, delay, symbol="AAPL"):
    first = now.date() - dt.timedelta(days=14)
    last = now.date() + dt.timedelta(days=14)
    if symbol in ("EURUSD", "BTCUSD"):
        date_labels = (
            market_data.weekdays(first, last)
            if symbol == "EURUSD"
            else market_data.calendar_days(first, last)
        )
        releases = [
            (
                date,
                dt.datetime.combine(
                    dt.date.fromisoformat(date) + dt.timedelta(days=1), dt.time(), UTC
                )
                + dt.timedelta(minutes=delay),
            )
            for date in date_labels
        ]
        target = next((date for date, release in reversed(releases) if release <= now), None)
        upcoming = next((release.isoformat() for _, release in releases if release > now), None)
        return target, upcoming
    cal = market_data.calendar(first, last)
    releases = [
        (s.date().isoformat(), cal.session_close(s).to_pydatetime() + dt.timedelta(minutes=delay))
        for s in cal.sessions_in_range(str(first), str(last))
    ]
    target = next((date for date, release in reversed(releases) if release <= now), None)
    upcoming = next((release.isoformat() for _, release in releases if release > now), None)
    return target, upcoming


class Runner:
    def __init__(self, connect, sync, experiment, save, config=None, clock=None):
        self.connect, self.sync, self.experiment, self.save = connect, sync, experiment, save
        self.config = config or settings()
        self.clock = clock or (lambda: dt.datetime.now(UTC))
        self.stop_event = threading.Event()
        self.thread = None
        self.next_check = None
        self.last_error = None

    def state(self, symbol, **values):
        if "sync_status" in values:
            values.setdefault("sync_retry_at", None)
        if values.get("forecast_status") in ("running", "waiting_for_data", "disabled"):
            values.setdefault("forecast_id", None)
            values.setdefault("forecast_retry_at", None)
        with self.connect() as c:
            c.execute("INSERT OR IGNORE INTO automation_state(symbol) VALUES(?)", (symbol,))
            if values:
                fields = ",".join(f"{key}=?" for key in values)
                c.execute(
                    f"UPDATE automation_state SET {fields} WHERE symbol=?",
                    (*values.values(), symbol),
                )

    def forecast(self, symbol, now):
        if not self.config["forecast_enabled"]:
            self.state(
                symbol, forecast_status="disabled", forecast_message="Automatic forecasts disabled"
            )
            return
        with self.connect() as c:
            ds = datasets.current(c, symbol)
            state = c.execute("SELECT * FROM automation_state WHERE symbol=?", (symbol,)).fetchone()
            existing = c.execute(
                "SELECT id FROM runs WHERE dataset_id=? AND model=? AND model_version='trend-v1' "
                "AND horizon=? AND origin='automatic'",
                (ds["id"], self.config["model"], self.config["horizon"]),
            ).fetchone()
        if ds["metadata"]["source"] == "synthetic":
            self.state(
                symbol,
                forecast_status="waiting_for_data",
                forecast_message="Waiting for API or CSV data",
            )
            return
        if existing:
            self.state(
                symbol,
                forecast_status="ready",
                forecast_id=existing[0],
                forecast_retry_at=None,
                forecast_message="Forecast saved for the current dataset",
            )
            return
        if state and state["forecast_retry_at"] and state["forecast_retry_at"] > now.isoformat():
            return
        try:
            self.state(
                symbol,
                forecast_status="running",
                forecast_message="Evaluating the current snapshot",
            )
            result = self.experiment(symbol, self.config["model"], self.config["horizon"], ds["id"])
            result = self.save(result, origin="automatic")
            self.state(
                symbol,
                forecast_status="ready",
                forecast_id=result["id"],
                forecast_retry_at=None,
                forecast_message="New dataset forecast saved",
            )
        except Exception:
            self.state(
                symbol,
                forecast_status="retry_scheduled",
                forecast_id=None,
                forecast_message="Forecast failed; retry scheduled without discarding data",
                forecast_retry_at=(now + dt.timedelta(minutes=10)).isoformat(),
            )

    def tick(self, now=None):
        now = now or self.clock()
        requested = False
        for symbol in self.config["symbols"]:
            target, _ = release_window(now, self.config["close_delay_minutes"], symbol)
            self.state(symbol, last_checked=now.isoformat(), target_session=target)
            self.forecast(symbol, now)
            if not self.config["sync_enabled"]:
                self.state(symbol, sync_status="disabled", sync_message="Automatic sync disabled")
                continue
            with self.connect() as c:
                ds = datasets.current(c, symbol)
                attempts = c.execute(
                    "SELECT COUNT(*) FROM automation_attempts WHERE symbol=? AND day=?",
                    (symbol, now.date().isoformat()),
                ).fetchone()[0]
                latest = c.execute(
                    "SELECT started FROM automation_attempts WHERE symbol=? ORDER BY id DESC LIMIT 1",
                    (symbol,),
                ).fetchone()
                recent_job = c.execute(
                    "SELECT started FROM ingestion_jobs ORDER BY id DESC LIMIT 1"
                ).fetchone()
            if ds["metadata"]["source"] == "csv-import":
                self.state(
                    symbol,
                    sync_status="csv_protected",
                    sync_message="CSV data is preserved; use manual Sync to switch to API",
                )
                continue
            if (
                ds["metadata"]["source"] == "alphavantage"
                and target
                and ds["observations"][-1]["date"] >= target
            ):
                self.state(
                    symbol,
                    sync_status="up_to_date",
                    sync_message="Latest eligible session is stored",
                    sync_retry_at=None,
                )
                continue
            key = os.getenv("ALPHAVANTAGE_API_KEY", "").strip()
            if not key or key in ("demo", "your_key_here"):
                self.state(
                    symbol,
                    sync_status="missing_key",
                    sync_message="Configure backend/.env and restart; no provider request was sent",
                )
                continue
            if target is None:
                self.state(
                    symbol,
                    sync_status="waiting",
                    sync_message="Waiting for an eligible closed session",
                )
                continue
            if attempts >= self.config["max_attempts_per_day"]:
                tomorrow = dt.datetime.combine(now.date() + dt.timedelta(days=1), dt.time(), UTC)
                self.state(
                    symbol,
                    sync_status="daily_limit",
                    sync_message="Automatic daily attempt limit reached",
                    sync_retry_at=tomorrow.isoformat(),
                )
                continue
            retry_at = (
                (
                    dt.datetime.fromisoformat(latest[0])
                    + dt.timedelta(minutes=self.config["retry_minutes"])
                )
                if latest
                else now
            )
            if retry_at > now:
                self.state(
                    symbol,
                    sync_status="retry_scheduled",
                    sync_message="Waiting before another provider request",
                    sync_retry_at=retry_at.isoformat(),
                )
                continue
            if requested or (
                recent_job and (now - dt.datetime.fromisoformat(recent_job[0])).total_seconds() < 15
            ):
                self.state(
                    symbol,
                    sync_status="queued",
                    sync_message="Waiting for the next scheduler check",
                )
                continue
            requested = True
            self.state(
                symbol,
                sync_status="syncing",
                sync_message="Fetching the latest daily window",
                sync_retry_at=None,
            )
            with self.connect() as c:
                attempt_id = c.execute(
                    "INSERT INTO automation_attempts(symbol,day,target_session,started,status) VALUES(?,?,?,?,?)",
                    (symbol, now.date().isoformat(), target, now.isoformat(), "running"),
                ).lastrowid
            try:
                result = self.sync(symbol)
                with self.connect() as c:
                    current = datasets.current(c, symbol)
                caught_up = current["observations"][-1]["date"] >= target
                self.state(
                    symbol,
                    sync_status="updated" if caught_up else "provider_lag",
                    sync_message=(
                        result["message"]
                        if caught_up
                        else "Provider has not published the eligible session yet"
                    ),
                    sync_retry_at=(
                        None
                        if caught_up
                        else (now + dt.timedelta(minutes=self.config["retry_minutes"])).isoformat()
                    ),
                )
                status = "succeeded"
                self.forecast(symbol, now)
            except Exception:
                status = "failed"
                self.state(
                    symbol,
                    sync_status="retry_scheduled",
                    sync_message="Sync failed; stored data retained. Check manual Sync for diagnostics.",
                    sync_retry_at=(
                        now + dt.timedelta(minutes=self.config["retry_minutes"])
                    ).isoformat(),
                )
            with self.connect() as c:
                c.execute(
                    "UPDATE automation_attempts SET status=?,finished=? WHERE id=?",
                    (status, now.isoformat(), attempt_id),
                )

    def status(self):
        now = self.clock()
        _, next_release = release_window(now, self.config["close_delay_minutes"])
        per_market = {
            symbol: release_window(now, self.config["close_delay_minutes"], symbol)[1]
            for symbol in self.config["symbols"]
        }
        with self.connect() as c:
            states = [dict(r) for r in c.execute("SELECT * FROM automation_state ORDER BY symbol")]
        return {
            **self.config,
            "worker_running": bool(self.thread and self.thread.is_alive()),
            "next_check": self.next_check,
            "next_market_release": next_release,
            "next_market_releases": per_market,
            "states": states,
            "last_error": self.last_error,
        }

    def start(self):
        if not (self.config["sync_enabled"] or self.config["forecast_enabled"]):
            return

        def work():
            while not self.stop_event.is_set():
                try:
                    self.tick()
                    self.last_error = None
                except Exception:
                    self.last_error = "Scheduler check failed; the next check will retry."
                self.next_check = (
                    self.clock() + dt.timedelta(seconds=self.config["poll_seconds"])
                ).isoformat()
                if self.stop_event.wait(self.config["poll_seconds"]):
                    break

        self.thread = threading.Thread(target=work, name="market-automation", daemon=True)
        self.thread.start()

    def stop(self):
        self.stop_event.set()
        if self.thread:
            self.thread.join(timeout=30)
