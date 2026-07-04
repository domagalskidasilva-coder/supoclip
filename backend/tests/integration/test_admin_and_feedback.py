import pytest


@pytest.mark.asyncio
async def test_admin_health_is_available_in_local_mode(client):
    response = await client.get("/admin/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


@pytest.mark.asyncio
async def test_feedback_rejects_when_not_configured(client):
    response = await client.post(
        "/feedback",
        json={"category": "unknown", "message": "hi"},
    )

    assert response.status_code == 400


@pytest.mark.asyncio
async def test_performance_metrics_are_available_in_local_mode(client):
    response = await client.get("/tasks/metrics/performance")

    assert response.status_code == 200
