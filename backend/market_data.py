"""Alpha Vantage daily-close connector; no browser or client-side credentials."""

import datetime as dt
import json
import math
import os
import urllib.error
import urllib.parse
import urllib.request

import exchange_calendars as calendars

ENDPOINT = "https://www.alphavantage.co/query"
SUPPORTED = {"AAPL", "MSFT", "EURUSD", "BTCUSD"}
FX_CALENDAR = "FX_WEEKDAYS_UTC"
CRYPTO_CALENDAR = "CRYPTO_DAILY_UTC"


class ProviderError(ValueError):
    pass


def calendar(start, end):
    first = dt.date.fromisoformat(str(start)) - dt.timedelta(days=10)
    last = dt.date.fromisoformat(str(end)) + dt.timedelta(days=10)
    return calendars.get_calendar("XNYS", start=first, end=last)


def weekdays(first, last):
    day = dt.date.fromisoformat(str(first))
    last = dt.date.fromisoformat(str(last))
    dates = []
    while day <= last:
        if day.weekday() < 5:
            dates.append(day.isoformat())
        day += dt.timedelta(days=1)
    return dates


def calendar_days(first, last):
    first = dt.date.fromisoformat(str(first))
    last = dt.date.fromisoformat(str(last))
    return [(first + dt.timedelta(days=i)).isoformat() for i in range((last - first).days + 1)]


def metadata(symbol, rows):
    common = {"source": "alphavantage", "provider": "Alpha Vantage", "currency": "USD"}
    if symbol == "BTCUSD":
        return {
            **common,
            "frequency": "daily-24x7",
            "price_basis": "spot",
            "calendar": CRYPTO_CALENDAR,
            "provider_timezone": "UTC",
            "base_currency": "BTC",
            "date_policy": "Completed UTC calendar dates, seven days per week",
            "policy_version": "crypto-utc-v1",
        }
    if symbol == "EURUSD":
        expected = set(weekdays(rows[0]["date"], rows[-1]["date"]))
        return {
            **common,
            "frequency": "daily-weekday-observations",
            "price_basis": "spot",
            "calendar": FX_CALENDAR,
            "provider_timezone": "UTC",
            "base_currency": "EUR",
            "date_policy": "Completed UTC dates, weekdays only; not New York 5pm sessions",
            "policy_version": "fx-utc-weekdays-v1",
            "missing_weekdays": sorted(expected - {r["date"] for r in rows}),
        }
    return {**common, "frequency": "daily", "price_basis": "unadjusted", "calendar": "XNYS"}


def validate_merge(symbol, old_rows, new_rows):
    if symbol == "EURUSD" and not ({r["date"] for r in old_rows} & {r["date"] for r in new_rows}):
        raise ValueError(
            "FX compact window has no overlap with stored API history. Import CSV to reset first."
        )
    merged = {r["date"]: r for r in old_rows}
    merged.update({r["date"]: r for r in new_rows})
    rows = sorted(merged.values(), key=lambda r: r["date"])
    if symbol == "BTCUSD":
        expected = set(calendar_days(rows[0]["date"], rows[-1]["date"]))
        if expected != {r["date"] for r in rows}:
            raise ValueError(
                "Crypto history has missing calendar dates; previous dataset retained."
            )
    elif symbol == "EURUSD":
        if any(
            (dt.date.fromisoformat(b["date"]) - dt.date.fromisoformat(a["date"])).days > 7
            for a, b in zip(rows, rows[1:])
        ):
            raise ValueError(
                "FX history contains a gap longer than seven calendar days; dataset retained."
            )
    else:
        cal = calendar(rows[0]["date"], rows[-1]["date"])
        expected = {
            s.date().isoformat() for s in cal.sessions_in_range(rows[0]["date"], rows[-1]["date"])
        }
        if expected != {r["date"] for r in rows}:
            raise ValueError(
                "Compact response cannot bridge the history gap. Import a complete CSV first."
            )
    return rows


def future_dates(last_date, horizon, calendar_name):
    last = dt.date.fromisoformat(last_date)
    if calendar_name == FX_CALENDAR:
        return weekdays(last + dt.timedelta(days=1), last + dt.timedelta(days=horizon * 3 + 10))[
            :horizon
        ]
    if calendar_name != "XNYS":
        return [(last + dt.timedelta(days=i)).isoformat() for i in range(1, horizon + 1)]
    first = last + dt.timedelta(days=1)
    end = last + dt.timedelta(days=horizon * 3 + 40)
    sessions = calendar(first, end).sessions_in_range(str(first), str(end))
    return [s.date().isoformat() for s in sessions[:horizon]]


def normalize(payload, symbol, utc_now=None):
    if not isinstance(payload, dict):
        raise ProviderError("Provider returned an invalid response.")
    if any(k in payload for k in ("Error Message", "Information", "Note")):
        raise ProviderError(
            "Provider rejected the request: check your API key, quota and endpoint entitlement."
        )
    meta = payload.get("Meta Data", {})
    if not isinstance(meta, dict) or str(meta.get("2. Symbol", "")).upper() != symbol:
        raise ProviderError("Provider response symbol does not match the requested asset.")
    series = payload.get("Time Series (Daily)")
    if not isinstance(series, dict) or not 100 <= len(series) <= 50000:
        raise ProviderError("Expected at least 100 daily observations from the provider.")
    rows = []
    try:
        for date, bar in sorted(series.items()):
            day = dt.date.fromisoformat(date)
            close = float(bar["4. close"])
            if not math.isfinite(close) or close <= 0:
                raise ValueError()
            rows.append({"date": day.isoformat(), "close": close})
    except (ValueError, TypeError, KeyError, OverflowError):
        raise ProviderError("Provider data contains an invalid date or closing price.") from None
    utc_now = utc_now or dt.datetime.now(dt.timezone.utc)
    cal = calendar(rows[0]["date"], rows[-1]["date"])
    for row in rows:
        date = row["date"]
        if not cal.is_session(date):
            raise ProviderError("Provider data includes a non-session date.")
        if cal.session_close(date).to_pydatetime() > utc_now:
            raise ProviderError(
                "Latest session has not closed yet; try syncing after market close."
            )
    expected = {
        s.date().isoformat() for s in cal.sessions_in_range(rows[0]["date"], rows[-1]["date"])
    }
    if expected != {r["date"] for r in rows}:
        raise ProviderError("Missing daily sessions in provider response; dataset was not changed.")
    return rows


def normalize_fx(payload, utc_now=None):
    if not isinstance(payload, dict):
        raise ProviderError("FX provider returned an invalid response.")
    if any(k in payload for k in ("Error Message", "Information", "Note")):
        raise ProviderError("FX request rejected: check API key, quota and FX_DAILY entitlement.")
    meta = payload.get("Meta Data", {})
    if (
        not isinstance(meta, dict)
        or meta.get("2. From Symbol") != "EUR"
        or meta.get("3. To Symbol") != "USD"
    ):
        raise ProviderError("Provider currency pair does not match EUR/USD.")
    if str(meta.get("6. Time Zone", "")).upper() not in ("UTC", "GMT"):
        raise ProviderError("FX timezone is missing or unsupported; expected UTC metadata.")
    series = payload.get("Time Series FX (Daily)")
    if not isinstance(series, dict) or not 100 <= len(series) <= 50000:
        raise ProviderError("Expected at least 100 FX daily provider rows before filtering.")
    today = (utc_now or dt.datetime.now(dt.timezone.utc)).astimezone(dt.timezone.utc).date()
    rows = []
    try:
        for date, bar in sorted(series.items()):
            day = dt.date.fromisoformat(date)
            close = float(bar["4. close"])
            if not math.isfinite(close) or close <= 0 or day > today:
                raise ValueError()
            # A daily endpoint can include the current, still-changing UTC date.
            if day == today or day.weekday() >= 5:
                continue
            rows.append({"date": day.isoformat(), "close": close})
    except (ValueError, TypeError, KeyError, OverflowError):
        raise ProviderError("FX response contains invalid dates or prices.") from None
    if len(rows) < 70:
        raise ProviderError("Need at least 70 completed weekday FX observations after filtering.")
    if any(
        (dt.date.fromisoformat(b["date"]) - dt.date.fromisoformat(a["date"])).days > 7
        for a, b in zip(rows, rows[1:])
    ):
        raise ProviderError("FX response has a gap longer than seven calendar days.")
    return rows


def normalize_crypto(payload, utc_now=None):
    if not isinstance(payload, dict):
        raise ProviderError("Crypto provider returned an invalid response.")
    if any(k in payload for k in ("Error Message", "Information", "Note")):
        raise ProviderError(
            "Crypto request rejected: check API key, quota and DIGITAL_CURRENCY_DAILY entitlement."
        )
    meta = payload.get("Meta Data", {})
    if (
        not isinstance(meta, dict)
        or meta.get("2. Digital Currency Code") != "BTC"
        or meta.get("4. Market Code") != "USD"
    ):
        raise ProviderError("Provider response is not BTC quoted in USD. USDT is not USD.")
    if str(meta.get("7. Time Zone", "")).upper() not in ("UTC", "GMT"):
        raise ProviderError("Crypto timezone is missing or unsupported; expected UTC metadata.")
    series = payload.get("Time Series (Digital Currency Daily)")
    if not isinstance(series, dict) or not 70 <= len(series) <= 50000:
        raise ProviderError("Expected sufficient digital-currency daily history.")
    today = (utc_now or dt.datetime.now(dt.timezone.utc)).astimezone(dt.timezone.utc).date()
    rows = []
    try:
        for date, bar in sorted(series.items()):
            day = dt.date.fromisoformat(date)
            if not isinstance(bar, dict) or day > today:
                raise ValueError()
            # Support plain and currency-qualified USD close fields, without guessing a quote.
            keys = [k for k in ("4. close", "4a. close (USD)", "4b. close (USD)") if k in bar]
            if not keys or any(isinstance(bar[k], bool) for k in keys):
                raise ValueError()
            values = [float(bar[k]) for k in keys]
            if any(not math.isfinite(v) or v <= 0 for v in values) or any(
                v != values[0] for v in values
            ):
                raise ValueError()
            if day == today:
                continue
            rows.append({"date": day.isoformat(), "close": values[0]})
    except (ValueError, TypeError, KeyError, OverflowError):
        raise ProviderError(
            "Crypto response contains invalid dates, prices or conflicting USD close fields."
        ) from None
    if len(rows) < 70:
        raise ProviderError("Need at least 70 completed UTC crypto daily observations.")
    expected = set(calendar_days(rows[0]["date"], rows[-1]["date"]))
    if expected != {r["date"] for r in rows}:
        raise ProviderError(
            "Crypto daily response has missing calendar dates; data was not filled."
        )
    return rows


def fetch_daily(symbol):
    if symbol not in SUPPORTED:
        raise ProviderError("API sync currently supports AAPL, MSFT, EURUSD and BTCUSD.")
    key = os.environ.get("ALPHAVANTAGE_API_KEY", "").strip()
    if not key or key in ("demo", "your_key_here"):
        raise ProviderError("Set ALPHAVANTAGE_API_KEY in backend/.env and restart the backend.")
    parameters = {"apikey": key}
    if symbol == "BTCUSD":
        parameters.update(function="DIGITAL_CURRENCY_DAILY", symbol="BTC", market="USD")
    elif symbol == "EURUSD":
        parameters.update(
            function="FX_DAILY", from_symbol="EUR", to_symbol="USD", outputsize="compact"
        )
    else:
        parameters.update(function="TIME_SERIES_DAILY", symbol=symbol, outputsize="compact")
    query = urllib.parse.urlencode(parameters)
    req = urllib.request.Request(
        ENDPOINT + "?" + query, headers={"User-Agent": "SignalResearch/0.2"}
    )
    try:
        with urllib.request.urlopen(req, timeout=25) as response:
            body = response.read(4_000_001)
        if len(body) > 4_000_000:
            raise ProviderError("Provider response exceeded the 4 MB safety limit.")
        # Credentials are never stored in raw-response records or exposed through errors.
        raw = body.decode("utf-8").replace(key, "[REDACTED]")
        payload = json.loads(raw)
    except (urllib.error.URLError, TimeoutError, OSError):
        raise ProviderError(
            "Could not reach the data provider. Check connectivity and retry."
        ) from None
    except (UnicodeError, json.JSONDecodeError):
        raise ProviderError("Provider returned invalid JSON.") from None
    if symbol == "BTCUSD":
        return normalize_crypto(payload), raw
    return (normalize_fx(payload) if symbol == "EURUSD" else normalize(payload, symbol)), raw
