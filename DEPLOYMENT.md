# Deployment Render + Vercel

Requires all prior patches through signal-fundamental-visuals.patch.
Public production UI is read-only. Local npm run dev retains manual actions.

## Install locally (Windows CMD)
Stop both servers. From project root:

    git apply --check signal-deployment.patch
    git apply signal-deployment.patch
    .venv-market\Scripts\python.exe -m pip install -r backend\requirements-production.txt
    .venv-market\Scripts\python.exe -m unittest discover -s backend -p "test_*.py"
    cd frontend
    npm ci
    npx tsc --noEmit
    npm run build
    cd ..

Review git status and staged changes; never commit real .env, SQLite databases,
venvs, node_modules or API keys. Commit and push the deployment code to GitHub.
Do not force-apply the patch if --check fails; preserve the error for diagnosis.

## Render backend
1. New > Blueprint > select your GitHub repository and main branch.
2. Use root render.yaml. Review costs before creating: paid web service + 1 GB disk.
3. Set ALPHAVANTAGE_API_KEY, FRED_API_KEY and SEC_USER_AGENT (app name + real email).
4. Blueprint generates API_ACCESS_TOKEN. Keep it secret and copy to Vercel later.
5. Blueprint sets HOST=0.0.0.0, PORT=10000, MARKET_ENV=production,
   DATABASE_PATH=/var/data/research.sqlite3, and enables all three workers.
6. Runtime is Docker, Dockerfile backend/Dockerfile, build context backend.
   One instance; health check /health; persistent disk mounted at /var/data.
7. Deploy, then open https://YOUR-BACKEND.onrender.com/health. Expect HTTP 200.
   /api/dashboard without a token should return 401.

Never copy Windows SSL_CERT_FILE paths to Render. The container installs system CAs.
Existing local SQLite data is not uploaded. Provider syncs populate the new database;
custom imported datasets require a separate deliberate database migration.
Do not run a second scheduler service against the same database.

## Vercel frontend
1. Add New > Project > import the same repository.
2. Framework Next.js; Root Directory frontend.
3. Install npm ci; Build npm run build; Output Directory default.
4. Set Production environment variables:

       BACKEND_URL=https://YOUR-BACKEND.onrender.com
       BACKEND_API_TOKEN=EXACT_VALUE_OF_RENDER_API_ACCESS_TOKEN

5. BACKEND_URL is an HTTPS origin without /api or another path.
   Do not prefix either variable with NEXT_PUBLIC_.
   NEXT_PUBLIC_API_URL is only for direct local development.
6. Deploy. Redeploy after changing environment variables.
7. Set Preview variables only if intentionally allowing previews to read this backend.

Browser requests use the same-origin /api proxy; Vercel adds the token server-side.
No CORS allowlist is necessary for this server-to-server path. Manual public POST,
PUT, PATCH and DELETE are blocked. The proxy token is not a user login system.
Only expose datasets you intend visitors to read; this demo has no per-user isolation.

## Verify
- Render /health returns 200 and unauthenticated /api/dashboard returns 401.
- Vercel /api/dashboard returns JSON successfully; no localhost requests in browser.
- Public write actions are disabled; workers perform scheduled refreshes.
- Check Fundamentals for source dates, freshness and provider errors.
- Redeploy backend and verify persisted data remains.
- Turn off local servers and confirm the deployed application still works.

Troubleshooting:
503 proxy not configured: check Vercel variables and redeploy.
502 token mismatch: match BACKEND_API_TOKEN to Render API_ACCESS_TOKEN.
502 unreachable: inspect Render status/logs, BACKEND_URL and provider durations.
Backend boot failure: check disk mount, token length and requirements installation.
A successful health check alone does not prove provider syncs have succeeded.

References: https://render.com/docs/blueprint-spec
https://render.com/docs/disks
https://vercel.com/docs/monorepos
https://vercel.com/docs/environment-variables
