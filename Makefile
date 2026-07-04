BACKEND_TEST_ENV = DATABASE_URL=$${TEST_DATABASE_URL:-$${DATABASE_URL:-postgresql+asyncpg://supoclip:supoclip_password@127.0.0.1:5432/supoclip}} REDIS_HOST=$${REDIS_HOST:-127.0.0.1} REDIS_PORT=$${REDIS_PORT:-6379}
FRONTEND_TEST_ENV = DATABASE_URL=$${TEST_DATABASE_URL:-$${FRONTEND_DATABASE_URL:-postgresql://supoclip:supoclip_password@127.0.0.1:5432/supoclip}} NEXT_PUBLIC_API_URL=$${NEXT_PUBLIC_API_URL:-http://localhost:8000} BACKEND_INTERNAL_URL=$${BACKEND_INTERNAL_URL:-http://localhost:8000}

.PHONY: test test-backend test-frontend test-e2e test-ci

test: test-backend test-frontend

test-backend:
	cd backend && uv sync --all-groups
	cd backend && $(BACKEND_TEST_ENV) uv run pytest

test-frontend:
	cd frontend && pnpm install
	cd frontend && $(FRONTEND_TEST_ENV) pnpm test

test-e2e:
	cd frontend && pnpm install
	cd frontend && $(FRONTEND_TEST_ENV) pnpm exec playwright install --with-deps
	cd frontend && $(FRONTEND_TEST_ENV) pnpm test:e2e

test-ci: test-backend test-frontend test-e2e
