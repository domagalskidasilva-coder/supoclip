# SupoClip Frontend

Next.js 15 app for the local SupoClip workflow.

## Run Locally

From the repository root:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/dev-frontend.ps1
```

The frontend runs on http://localhost:3107 and proxies API requests to the backend at `NEXT_PUBLIC_API_URL` / `BACKEND_INTERNAL_URL`.

## Tests

```powershell
cd frontend
pnpm.cmd test
pnpm.cmd build
```
