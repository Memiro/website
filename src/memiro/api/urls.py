from dmr.openapi import OpenAPIConfig
from dmr.openapi.core.context import OpenAPIContext
from dmr.openapi.views.json import OpenAPIJsonView
from dmr.routing import Router, path

from memiro.api.ping import PingController
from memiro.catalog.api import PriceController
from memiro.inquiries.api import InquiryController, ProductSummariesController

router = Router(
    "api/",
    [
        path("ping", PingController.as_view(), name="ping"),
        path(
            "products",
            ProductSummariesController.as_view(),
            name="product-summaries",
        ),
        path("price", PriceController.as_view(), name="price"),
        path("inquiries", InquiryController.as_view(), name="inquiries"),
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
