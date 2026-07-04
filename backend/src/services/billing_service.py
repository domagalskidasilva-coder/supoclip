from __future__ import annotations

from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from ..config import Config, get_config


class BillingLimitExceeded(Exception):
    def __init__(self, summary: dict[str, Any]):
        super().__init__("Billing limit reached")
        self.summary = summary


class BillingService:
    def __init__(self, db: AsyncSession, config: Config | None = None):
        self.db = db
        self.config = config or get_config()

    async def get_usage_summary(self) -> dict[str, Any]:
        return {
            "monetization_enabled": False,
            "plan": "local",
            "subscription_status": "disabled",
            "period_start": None,
            "period_end": None,
            "usage_count": 0,
            "usage_limit": None,
            "remaining": None,
            "can_create_task": True,
            "upgrade_required": False,
            "reason": None,
        }

    async def assert_can_create_task(self) -> None:
        return None
