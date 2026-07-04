# SupoClip Quick Start

This app now runs as a local stack without login or Docker.

## 1. Install prerequisites

- Node.js 20+
- pnpm 10+
- Python 3.11+
- uv
- PostgreSQL 15+
- Redis 7+
- ffmpeg

## 2. Configure `.env`

```powershell
Copy-Item .env.example .env
```

Edit `.env` and set at least:

```env
ASSEMBLY_AI_API_KEY=your_assemblyai_key
LLM=google-gla:gemini-3-flash-preview
GOOGLE_API_KEY=your_google_key
```

## 3. Prepare PostgreSQL

Create the `supoclip` database/user if they do not already exist:

```powershell
createuser supoclip
createdb supoclip -O supoclip
```

Then apply the schema:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/apply-schema.ps1
```

## 4. Start the app

Open three terminals from the repository root:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/dev-backend.ps1
```

```powershell
powershell -ExecutionPolicy Bypass -File scripts/dev-worker.ps1
```

```powershell
powershell -ExecutionPolicy Bypass -File scripts/dev-frontend.ps1
```

Open http://localhost:3107.

## Troubleshooting

- Videos stay queued: confirm Redis is running and the worker terminal is active.
- Backend cannot connect to DB: check `DATABASE_URL` in `.env`.
- Frontend cannot create tasks: check `NEXT_PUBLIC_API_URL` and `BACKEND_INTERNAL_URL`.
- Transcription fails: check `ASSEMBLY_AI_API_KEY`.
- AI analysis fails: check `LLM` and the matching provider key.
