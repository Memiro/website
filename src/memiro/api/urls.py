from dmr.openapi import OpenAPIConfig
from dmr.openapi.core.context import OpenAPIContext
from dmr.openapi.views.json import OpenAPIJsonView
from dmr.routing import Router, path

from memiro.api.ping import PingController

router = Router(
    "api/",
    [
        path("ping", PingController.as_view(), name="ping"),
    ],
)

openapi_context = OpenAPIContext(
    config=OpenAPIConfig(title="Memiro API", version="0.1.0"),
)

urlpatterns = [
    router.to_urlpatterns(),
    path(
        "api/openapi/schema.json",
        OpenAPIJsonView.as_view(schema=router.get_schema(openapi_context)),
        name="openapi-schema",
    ),
]
