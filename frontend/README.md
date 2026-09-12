# canarynet frontend

PoC UI for the three views: company dashboard, task mind-map, canary status.
Ships with mock data (`src/api/mockData.ts`) matching `../backend/models.py` so
it runs standalone with no backend - see `CONTRACT.md` for the API this is
meant to consume when pointed at the real one.

## Local dev

```bash
npm install
npm run dev        # http://localhost:5173
```

By default it uses mock data. To point it at a real backend instead, copy
`.env.example` to `.env.local` and set `VITE_USE_MOCK=false` (the dev server
proxies `/api` to `BACKEND_URL`, default `http://localhost:8000` - see
`vite.config.ts`), or use `make frontend` from the repo root, which sets
that for you. See the repo root `README.md`/`CLAUDE.md` for running both
halves together.
