import pytest

from memiro.entities.errors.product import DuplicateProductImageError
from tests.clock import CLOCK, LATER, LATER_CLOCK
from tests.common.factory.catalog import demo_product

FIRST = "a1b2c3.jpg"
SECOND = "d4e5f6.jpg"

# Where the second photo lands when the owner says nothing about its place.
SECOND_PLACE = 1


def test_a_product_keeps_the_photos_it_was_given() -> None:
    """A photo the owner uploaded belongs to the gallery of the product it was uploaded to."""
    product = demo_product()

    product.add_image(FIRST, clock=CLOCK)

    assert [image.key for image in product.images] == [FIRST]


def test_a_photo_goes_behind_the_ones_already_in_the_gallery() -> None:
    """A gallery is read in the owner's order, and a new photo takes the place after it."""
    product = demo_product()
    product.add_image(FIRST, clock=CLOCK)

    added = product.add_image(SECOND, clock=CLOCK)

    assert added.sort_order == SECOND_PLACE


def test_a_photo_moves_the_product_it_joins() -> None:
    """Adding a photo restates the product the gallery belongs to."""
    product = demo_product()

    product.add_image(FIRST, clock=LATER_CLOCK)

    assert product.updated_at == LATER


def test_a_product_gives_up_the_photo_it_is_told_to() -> None:
    """A photo the owner took off the card leaves the gallery, the rest of it untouched."""
    product = demo_product()
    product.add_image(FIRST, clock=CLOCK)
    added = product.add_image(SECOND, clock=CLOCK)

    product.remove_image(added, clock=LATER_CLOCK)

    assert [image.key for image in product.images] == [FIRST]
    assert product.updated_at == LATER


def test_a_product_refuses_a_second_photo_under_one_key() -> None:
    """A key names one photo: DUPLICATE_PRODUCT_IMAGE."""
    product = demo_product()
    product.add_image(FIRST, clock=CLOCK)

    with pytest.raises(DuplicateProductImageError):
        product.add_image(FIRST, clock=CLOCK)


def test_a_product_names_the_photo_a_command_points_at() -> None:
    """A gallery answers by key: that is all a command carries about a photo."""
    product = demo_product()
    product.add_image(FIRST, clock=CLOCK)

    assert product.image(FIRST) is not None
    assert product.image(SECOND) is None
