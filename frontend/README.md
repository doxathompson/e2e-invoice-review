# Invoice Review frontend

Vite + React + TypeScript app for the Northstar document review workflow.

```bash
cp .env.example .env
pnpm install --frozen-lockfile
pnpm dev
```

Requires the backend on `VITE_API_BASE_URL` (default `http://localhost:8000`).

Verification:

```bash
pnpm exec tsc -b --pretty false
pnpm lint
pnpm build
```
