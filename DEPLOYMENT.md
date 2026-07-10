# Deployment

## Local (docker compose)

```bash
cp .env.example .env   # fill GROQ_API_KEY, TAVILY_API_KEY
docker compose up --build
```

Brings up the API on :8000 and Postgres 16 (checkpoints + run store) with healthchecks. The compose file wires `DATABASE_URL` automatically.

## Backend — Railway (free tier)

1. Create a Railway project → **Deploy from GitHub repo**. `railway.json` configures the Dockerfile build, `/health` healthcheck, and start command.
2. Add a **PostgreSQL** service to the project.
3. Set backend service variables:

| Variable | Value |
|---|---|
| `GROQ_API_KEY` | your key |
| `TAVILY_API_KEY` | your key |
| `DATABASE_URL` | `${{Postgres.DATABASE_URL}}` (Railway reference) |
| `API_KEYS` | a long random string (the frontend's server key) |
| `CORS_ORIGINS` | `https://<your-vercel-app>.vercel.app` |
| `APP_DEBUG` | `false` |

Render works identically (Docker runtime + managed Postgres); use `/health` as the health check path.

## Frontend — Vercel

Import the repo, set **Root Directory = `frontend`**, then:

| Variable | Value |
|---|---|
| `BACKEND_API_URL` | `https://<railway-backend-domain>` |
| `BACKEND_API_KEY` | same value as the backend's `API_KEYS` |

Both are read **server-side only** (Next.js route handlers proxy every backend call); no key ever reaches the browser.

## Post-deploy smoke test

```bash
curl https://<backend>/health                       # {"status":"healthy","database":"ok"}
curl -X POST https://<backend>/api/research \
  -H "Content-Type: application/json" -H "X-API-Key: <key>" \
  -d '{"prompt": "Quick overview of perovskite solar cells"}'
```

Then open the Vercel app, run a research from the dashboard, and watch the live workflow graph. Seed 2–3 example runs so the history page has content for visitors.

## Monitoring (local)

```bash
docker compose --profile monitoring up --build
# Grafana: http://localhost:3001 (dashboard "Research Agent", anonymous view)
# Prometheus: http://localhost:9090
```

The monitoring profile is local tooling — cloud deploys just expose `/metrics`, which any hosted Prometheus (e.g. Grafana Cloud free tier) can scrape.

## Notes

- The Pipelock proxy is local-dev tooling; leave `PIPELOCK_PROXY_URL` unset in deployment.
- Rate limiting is per-IP in-process (slowapi); if you scale beyond one instance, move it to a shared store.
- `logs/pipelab_trace.jsonl` is per-instance; SSE replay for old runs works only on the instance that ran them (the run *result* is always in Postgres).
