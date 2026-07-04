from __future__ import annotations

from typing import Any

from ..config import Config


class SubscriptionEmailService:
    def __init__(self, config: Config | None = None):
        self.config = config or Config()

    @property
    def is_configured(self) -> bool:
        return False

    async def send_subscribed_email(self, _user: Any) -> dict[str, str]:
        return {"status": "disabled", "reason": "Billing emails were removed."}

    async def send_unsubscribed_email(self, _user: Any) -> dict[str, str]:
        return {"status": "disabled", "reason": "Billing emails were removed."}
