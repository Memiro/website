from collections.abc import Sequence

from memiro.application.browse_catalog.models import ImageModel, ImageVariant, ProductSummary
from memiro.application.common.gateway.product_image import ProductImageStorage


async def photographed[Product: ProductSummary](
    storage: ProductImageStorage,
    products: Sequence[Product],
) -> list[Product]:
    """Pair every gallery of the page with the copies the storage really holds, in one hop."""
    held = await storage.variants([key for product in products for key in product.image_keys])
    return [
        product.model_copy(
            update={
                "images": [
                    ImageModel(
                        key=key,
                        variants=[ImageVariant(key=variant.key, width=variant.width) for variant in held.get(key, ())],
                    )
                    for key in product.image_keys
                ]
            }
        )
        for product in products
    ]
