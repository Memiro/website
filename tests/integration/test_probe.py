from memiro.presentation.fast_api.routers.health import HealthStatus
from tests.integration.api_client import ApiClient


async def test_a_fresh_contour_reports_itself_alive(api_client: ApiClient) -> None:
    """The liveness probe answers 200 through the production app assembly."""
    response = await api_client.alive()

    assert response.assert_status(200).ensure_content() == HealthStatus(status="ok")


async def test_a_fresh_contour_is_ready_to_serve(api_client: ApiClient) -> None:
    """The readiness probe reaches the migrated database through DI."""
    response = await api_client.ready()

    assert response.assert_status(200).ensure_content() == HealthStatus(status="ok")
