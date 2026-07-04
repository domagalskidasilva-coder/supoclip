# SupoClip

SupoClip is a local-first AI video clipping app. It turns YouTube links or uploaded videos into short captioned clips with transcription, AI segment selection, face-aware cropping, caption templates, and export tools.

This build is intentionally simpler than the original hosted SaaS version:

- No login, accounts, sessions, admin users, billing, Stripe, or API keys.
- Tasks are global to the local instance.
- Settings are either browser-local caption defaults or global runtime provider keys.
- Docker is no longer the primary development path.

## Requirements

- Node.js 20+ and pnpm 10+
- Python 3.11+
- uv for Python dependency management
- PostgreSQL 15+
- Redis 7+
- ffmpeg on PATH
- An AssemblyAI API key
- One LLM provider key, or a local Ollama model

## Quick Start On Windows

1. Copy the environment template:

```powershell
Copy-Item .env.example .env
```

2. Edit `.env` and set:

```env
ASSEMBLY_AI_API_KEY=...
LLM=google-gla:gemini-3-flash-preview
GOOGLE_API_KEY=...
```

OpenAI, Anthropic, and Ollama are also supported. See `.env.example`.

3. Make sure PostgreSQL and Redis are running locally, then create the database/user if needed:

```powershell
createuser supoclip
createdb supoclip -O supoclip
```

If your local credentials differ, update `DATABASE_URL` and `FRONTEND_DATABASE_URL` in `.env`.

4. Apply the schema:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/apply-schema.ps1
```

5. Start the three app processes in three terminals:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/dev-backend.ps1
powershell -ExecutionPolicy Bypass -File scripts/dev-worker.ps1
powershell -ExecutionPolicy Bypass -File scripts/dev-frontend.ps1
```

Open http://localhost:3107. Backend docs are at http://localhost:8000/docs.

## Useful Commands

```powershell
cd frontend
pnpm.cmd test
pnpm.cmd build
```

```powershell
cd backend
uv sync --all-groups
uv run pytest
```

## Project Layout

- `backend/`: FastAPI API, processing services, repositories, workers.
- `frontend/`: Next.js app and API proxy routes.
- `waitlist/`: separate marketing/waitlist app.
- `scripts/`: local PowerShell scripts for running the app without Docker.
- `init.sql`: local PostgreSQL schema baseline.

## Improvement Ideas

Backend:

- Add real automated DB migrations for local mode instead of relying on `init.sql`.
- Add a health panel that checks PostgreSQL, Redis, ffmpeg, AssemblyAI, and the selected LLM.
- Add queue visibility: retry count, worker heartbeat, estimated wait time, and failed-job details.
- Move long video processing artifacts into a configurable media storage abstraction.

Frontend:

- Add a compact dashboard for active jobs, failed jobs, and recent exports.
- Add drag-and-drop batch uploads.
- Add preset management for caption styles and export formats.
- Add a guided first-run settings screen that validates provider keys before the first generation.

Quality:

- Expand integration tests around upload, resume, cancel, trim, split, merge, and export flows.
- Add Playwright smoke coverage for the new no-login local workflow.
- Upgrade Next.js to a patched version; `pnpm install` currently warns that `next@15.4.8` has a security advisory.

## License

SupoClip is released under the AGPL-3.0 License. See [LICENSE](LICENSE).
