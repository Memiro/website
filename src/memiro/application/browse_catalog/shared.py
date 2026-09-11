from collections.abc import Mapping, Sequence

from memiro.application.browse_catalog.models import ImageModel, ImageVariant, PhotographedTile, ProductSummary
from memiro.application.common.gateway.product_image import ProductImageStorage, StoredVariant


async def photographed[Product: ProductSummary](
    storage: ProductImageStorage,
    products: Sequence[Product],
) -> list[Product]:
    """Pair every gallery of the page with the copies the storage really holds, in one hop."""
    held = await storage.variants([key for product in products for key in product.image_keys])
    return [
        product.model_copy(update={"images": [_described(key, held) for key in product.image_keys]})
        for product in products
    ]


async def photographed_tiles[Tile: PhotographedTile](
    storage: ProductImageStorage,
    tiles: Sequence[Tile],
) -> list[Tile]:
    """Pair the photograph of every tile with the copies the storage holds for it, in one hop."""
    held = await storage.variants([tile.image.key for tile in tiles if tile.image is not None])
    return [
        tile if tile.image is None else tile.model_copy(update={"image": _described(tile.image.key, held)})
        for tile in tiles
    ]


def _described(key: str, held: Mapping[str, list[StoredVariant]]) -> ImageModel:
    """Spell one photograph the way the storefront reads it: the key and the copies there are."""
    return ImageModel(
        key=key,
        variants=[ImageVariant(key=variant.key, width=variant.width) for variant in held.get(key, ())],
    )
