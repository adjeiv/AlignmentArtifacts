# canarynet frontend

PoC UI for the three views: company dashboard, task mind-map, canary status.
Ships with mock data (`src/api/mockData.ts`) matching `../rfc/frontend_models.py`
so it runs standalone with no backend — see `CONTRACT.md` for the API this
is meant to consume once the backend implements it.

## Local dev

```bash
npm install
npm run dev        # http://localhost:5173
```

By default it uses mock data. To point it at a real backend instead, copy
`.env.example` to `.env.local` and set `VITE_USE_MOCK=false` (the dev server
proxies `/api` to `BACKEND_URL`, default `http://localhost:8000` - see
`vite.config.ts`).

## Docker

```bash
docker build -t canarynet-frontend .
docker run -p 8080:80 canarynet-frontend    # http://localhost:8080
```

Runs in mock mode by default (baked in at build time). To build against a
real backend:

```bash
docker build --build-arg VITE_USE_MOCK=false -t canarynet-frontend .
docker run -p 8080:80 -e BACKEND_ORIGIN=http://backend:8000 canarynet-frontend
```

`BACKEND_ORIGIN` is where nginx proxies `/api/*` to at container start (see
`nginx.conf.template`) - it's read at runtime, not build time, so it's the
one to set from `docker-compose.yml` when wiring this up to the backend
service.
