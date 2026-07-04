# SupoClip Backend

FastAPI backend, async worker code, repositories, and video-processing services.

## Run Locally

From the repository root:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/dev-backend.ps1
```

Worker:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/dev-worker.ps1
```

Required local services:

- PostgreSQL
- Redis
- ffmpeg

## Tests

```powershell
cd backend
uv sync --all-groups
uv run pytest
```

Set `DATABASE_URL`, `TEST_DATABASE_URL`, `REDIS_HOST`, and `REDIS_PORT` if your local services do not match `.env.example`.
