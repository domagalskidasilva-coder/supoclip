import pytest

from src.services.billing_service import BillingService


class _FakeSession:
    pass


@pytest.mark.asyncio
async def test_billing_summary_is_disabled_for_local_mode():
    service = BillingService(_FakeSession())  # type: ignore[arg-type]

    summary = await service.get_usage_summary()

    assert summary["monetization_enabled"] is False
    assert summary["plan"] == "local"
    assert summary["can_create_task"] is True
    assert summary["upgrade_required"] is False
    assert summary["usage_limit"] is None


@pytest.mark.asyncio
async def test_assert_can_create_task_is_noop():
    service = BillingService(_FakeSession())  # type: ignore[arg-type]

    await service.assert_can_create_task()
