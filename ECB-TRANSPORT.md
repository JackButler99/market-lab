# ECB transport update

Apply after `signal-forex-crypto-fundamentals.patch`. This backend-only add-on does not change packages, credentials, stored observations or forecasting behavior.

The earlier error `ecb: request failed or returned invalid data` hides the underlying transport condition. It does not establish a specific root cause. This update uses the ECB CSV media type `application/vnd.ecb.data+csv;version=1.0.0`, gives ECB requests 60 seconds, supports bounded gzip decoding and detects non-CSV service/proxy pages. TLS certificate verification stays enabled. Errors distinguish DNS, timeout, certificate verification, TLS handshake, connection failure and malformed responses without exposing raw messages, URLs, keys or response bodies.

Stop the Python backend with Ctrl+C. Save the patch in the project root and run:

```bat
cd /d "G:\React porject\market-lab"
git apply --check signal-ecb-transport.patch
git apply signal-ecb-transport.patch
.venv-market\Scripts\python.exe backend\server.py
```

In another terminal, retry the same request:

```bat
curl.exe --noproxy "*" -X POST http://127.0.0.1:8000/api/fundamentals/sync -H "Content-Type: application/json" -d "{\"symbol\":\"EURUSD\"}"
```

Allow up to a minute for the ECB request, plus time for the FRED requests. A concurrent worker may hold the sync lock or trigger the shared 45-second cooldown; follow the response before retrying. Existing six-hour cache behavior remains unchanged. No database cleanup or frontend restart is required.

If it still fails, retain the new JSON error to identify the next step. For comparison, the public ECB endpoint can be checked directly without disclosing any key:

```bat
curl.exe --connect-timeout 15 --max-time 60 -H "Accept: application/vnd.ecb.data+csv;version=1.0.0" "https://data-api.ecb.europa.eu/service/data/FM/D.U2.EUR.4F.KR.DFR.LEV?format=csvdata&lastNObservations=2"
```

That direct command uses the terminal's normal proxy settings. The local API command bypasses proxies only for localhost. If Python reports certificate verification failure, investigate the Python trust store, system clock and HTTPS-inspecting network software; do not disable verification. A timeout or DNS error requires checking network/provider access rather than replacing the FRED key.

80 backend tests passed, including six new transport tests covering headers/timeouts, gzip, BOM, HTML error pages, safe network-error categories and decompressed-size limits. Live ECB success from the user's network is not verified; this patch improves transport handling and exposes the cause when access still fails.

Reference: https://data.ecb.europa.eu/help/download-data-refreshable-excel
