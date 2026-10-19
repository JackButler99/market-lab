# ECB labeled CSV compatibility

Apply this add-on after `signal-ecb-transport.patch`.

The supplied ECB response has HTTP 200 and valid CSV. Its header uses `Key`, `Time period or range`, and `Observation value`; the previous parser only accepted `KEY`, `TIME_PERIOD`, and `OBS_VALUE`. This was a parser compatibility bug, not evidence of an error page.

The patch normalizes both variants through the same function at fetch validation and macro extraction. It handles quoted commas, UTF-8 BOM, header case and surrounding whitespace. The raw CSV is preserved. Unexpected/ambiguous headers, wrong series IDs, malformed rows and unexpected unit multipliers remain rejected.

Stop the backend with Ctrl+C, place `signal-ecb-csv-labels.patch` in the root, then run:

```bat
cd /d "G:\React porject\market-lab"
git apply --check signal-ecb-csv-labels.patch
git apply signal-ecb-csv-labels.patch
.venv-market\Scripts\python.exe backend\server.py
```

Keep the working SSL_CERT_FILE setting in backend/.env, or restart from the terminal where it was set. No frontend restart, dependency changes, database reset or new key is required.

Retry in a second terminal:

```bat
curl.exe --noproxy "*" -X POST http://127.0.0.1:8000/api/fundamentals/sync -H "Content-Type: application/json" -d "{\"symbol\":\"EURUSD\"}"
```

A successful response has `has_data: true`, `snapshot_id` and an `analysis` object. The EURUSD Macro tab reads saved data every 15 seconds. If a worker has just synced, the response can be a cache hit; if it is currently running, wait for the lock/cooldown rather than repeatedly clicking Sync.

Validation: 89 backend tests passed. Nine new regression tests cover labeled/code headers, quoted metadata, transport-to-parser compatibility, macro values and rate spread, BOM/case/whitespace, unknown/ambiguous headers, wrong series, multipliers, and empty/truncated rows. The patch was applied to a clean copy of its baseline and reconstructed all files exactly. Direct live provider fetching from the user's machine is not verified by these fixture tests.
