# Aldergate Frontend — Milestone 1: Foundation Layer

Enterprise React console for the Aldergate ERISA 401(k) backend
(`api/main.py`, documented in `../SWAGGER_GUIDE.md`). This milestone ships
the application shell only — routing, auth/session handling, layout, and
dashboard scaffolding. The AI agent chat interface, compliance engine,
loan/hardship workflows, review queue, audit log, and blackout manager are
intentionally out of scope; they arrive in Milestones 2–4.

## Stack

- React 18 + Vite 5
- React Router 6
- Tailwind CSS 3 (dark theme, tokens lifted from the original
  `chatbot_ui_1.html` demo for visual continuity)
- Plain `fetch` API client with automatic mock-data fallback — no backend
  required to explore the foundation layer

## Getting Started

```bash
cd frontend
npm install
cp .env.example .env
npm run dev
```

Open http://localhost:5173. The dev server proxies `/api/*` to
`http://localhost:8000` (the FastAPI backend) — start it separately with:

```bash
cd ..
source .venv/bin/activate
uvicorn api.main:app --reload --port 8000
```

If the backend isn't running, every API call falls back to an in-memory
mock client (`src/mocks`) whose data shapes mirror `api/routes/meta.py`, so
login and the dashboards work standalone. Set `VITE_USE_MOCK_API=true` in
`.env` to force mock mode even when a backend is reachable.

## Structure

```
src/
  context/AuthContext.jsx     Session state, login/logout, expiry handling
  lib/apiClient.js            fetch wrapper + mock fallback
  lib/storage.js              Namespaced localStorage helper
  lib/format.js               Shared currency/percent/name formatters
  mocks/                      Mock API client + fixture data
  routes/ProtectedRoute.jsx   Auth + role route guard
  components/layout/          Sidebar, Header, AppLayout shell
  components/ui/              Avatar, StatCard, RoadmapNotice
  pages/Login/                Login page
  pages/Dashboard/Participant/ Participant shell + Overview
  pages/Dashboard/Sponsor/     Sponsor shell + Overview
```

## Roles

Login accepts the same `principal_type` values as `POST /auth/login`:
`participant`, `investment_advisor`, `plan_sponsor`, `plan_trustee`. The
session is persisted to `localStorage` under the `aldergate:session` key
and expires client-side in lockstep with the JWT's `expires_in`.

## What ships in later milestones

See the in-app "roadmap" notices on `/participant/loans`,
`/participant/investments`, `/participant/distributions`,
`/sponsor/queue`, `/sponsor/audit`, and `/sponsor/blackout` — each states
exactly which milestone brings that feature online, matching
`../DEMO_GUIDE.md` and `../README.md`'s phase table.
