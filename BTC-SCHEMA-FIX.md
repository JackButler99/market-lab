# Bitcoin fundamental schema fix

Apply after `signal-ecb-csv-labels.patch`. The observed Blockchain.com response uses the hash-rate unit `Hash Rate TH/s`, which was missing from the accepted aliases. Its `total-bitcoins` chart also supplies multiple timestamps within a UTC day, whereas the old parser rejected differing values on the same date.

This fix accepts the observed hash-rate label and preserves TH/s as the canonical unit. For issued supply only, it selects the last available timestamp per completed UTC day, independent of response ordering. It does not sum or average supply and does not assume the provider has supplied a true midnight close. Each retained supply point stores its source timestamp, and the metric includes its sampling policy. Current-day/future points remain excluded. Conflicting identical timestamps, invalid supply values and conflicting daily values for other charts remain rejected. Parser failures now include safe chart-specific diagnostics.

Stop the backend with Ctrl+C. Save the patch in the root and run:

```bat
cd /d "G:\React porject\market-lab"
git apply --check signal-btc-schema-fix.patch
git apply signal-btc-schema-fix.patch
.venv-market\Scripts\python.exe backend\server.py
```

Keep the working SSL_CERT_FILE setting if required by your Python environment. No dependencies, API keys, database cleanup or frontend changes are required.

Retry in another terminal:

```bat
curl.exe --noproxy "*" -X POST http://127.0.0.1:8000/api/fundamentals/sync -H "Content-Type: application/json" -d "{\"symbol\":\"BTCUSD\"}"
```

Success returns `has_data: true`, `snapshot_id` and `analysis`. The BTC Network tab refreshes saved data every 15 seconds. Existing six-hour caching, 45-second cooldown and automatic retries are unchanged. A stale badge means the provider observation is over three days old; successful fetching does not make old observations current. Exact seven-calendar-day changes remain unavailable when the necessary prior date is missing.

97 backend tests passed, including eight new regressions for the observed unit, unordered intraday supply, incomplete-day exclusion, same-timestamp conflicts, strict other-chart validation, invalid supply, timestamp provenance and safe parser diagnostics. Patch application was verified against its baseline. Live fetching from the user's environment was not run here.
