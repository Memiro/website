import pytest

from memiro.entities.catalog.landing.entity import landing_factory, settled_slug
from memiro.entities.catalog.landing.landing_service import ensure_the_narrowing_is_buildable
from memiro.entities.errors.landing import InvalidLandingNarrowingError, InvalidLandingSlugError
from tests.clock import CLOCK, LATER, LATER_CLOCK, NOW
from tests.common.factory.catalog import (
    ALUMINIUM,
    BACKLIGHT,
    BLADE,
    CATEGORY,
    CONTOUR,
    CUTOUT,
    CUTOUTS,
    FRAME,
    NO_FRAME,
    RECTANGULAR,
    ROUND,
    SECOND_CATEGORY,
    SHAPE,
    SILVER,
    demo_attributes,
)
from tests.common.factory.landing import demo_condition, demo_landing, demo_landing_copy, demo_landing_data


def test_a_landing_is_born_with_the_copy_and_the_address_the_owner_wrote() -> None:
    """Both dates come from one reading of the clock, and the address is the owner's own."""
    landing = landing_factory(demo_landing_data(), clock=CLOCK)

    assert (landing.slug, landing.heading, landing.created_at, landing.updated_at) == (
        "kruglye-zerkala",
        "Круглые зеркала",
        NOW,
        NOW,
    )


def test_an_address_nobody_typed_is_transliterated_from_the_heading() -> None:
    """The owner writes a heading in Russian; the address it gets is the same words in latin."""
    landing = landing_factory(demo_landing_data(slug="", heading="Зеркала с подсветкой"), clock=CLOCK)  # noqa: RUF001

    assert landing.slug == "zerkala-s-podsvetkoy"


def test_a_heading_that_spells_no_address_is_refused() -> None:
    """INVALID_LANDING_SLUG: a page without an address is a page nobody can open."""
    with pytest.raises(InvalidLandingSlugError):
        settled_slug("", "!!!")


def test_the_narrowing_is_replaced_whole() -> None:
    """The set is one command, not a row edited at a time; the page is stamped with the change."""
    landing = demo_landing()

    landing.narrow_by(
        [demo_condition(FRAME, ALUMINIUM), demo_condition(FRAME, NO_FRAME)],
        clock=LATER_CLOCK,
    )

    assert [condition.value_id for condition in landing.conditions] == [ALUMINIUM, NO_FRAME]
    assert landing.updated_at == LATER


def test_a_page_that_narrows_by_nothing_is_refused() -> None:
    """A landing without conditions is its category under a second address."""
    landing = demo_landing()

    with pytest.raises(InvalidLandingNarrowingError):
        landing.narrow_by([], clock=LATER_CLOCK)


def test_the_same_value_is_named_once() -> None:
    """A repeated value narrows nothing twice: the card sends a set, not a list."""
    landing = demo_landing()

    with pytest.raises(InvalidLandingNarrowingError):
        landing.narrow_by([demo_condition(), demo_condition()], clock=LATER_CLOCK)


def test_a_page_narrowing_by_three_attributes_is_refused() -> None:
    """Two questions about a mirror is a landing; three is the faceted page ADR-0003 keeps out of the index."""
    landing = demo_landing()

    with pytest.raises(InvalidLandingNarrowingError):
        landing.narrow_by(
            [demo_condition(), demo_condition(FRAME, ALUMINIUM), demo_condition(BACKLIGHT, CONTOUR)],
            clock=LATER_CLOCK,
        )


def test_the_copy_changes_and_the_category_does_not_move() -> None:
    """A landing keeps the category its narrowing belongs to; the rest is the owner's to restate."""
    landing = demo_landing()

    landing.change(
        demo_landing_copy(heading="Круглые зеркала с подсветкой", is_published=False),  # noqa: RUF001
        clock=LATER_CLOCK,
    )

    assert (landing.heading, landing.is_published, landing.category_id) == (
        "Круглые зеркала с подсветкой",  # noqa: RUF001
        False,
        CATEGORY,
    )


def test_a_value_of_another_category_narrows_nothing() -> None:
    """The sidebar of this category never offers it, so the page would show the whole category."""
    with pytest.raises(InvalidLandingNarrowingError):
        ensure_the_narrowing_is_buildable(
            [demo_condition()],
            category_id=SECOND_CATEGORY,
            dictionary=demo_attributes(),
        )


def test_an_attribute_the_owner_took_out_of_the_filters_narrows_nothing() -> None:
    """A landing has no narrowing of its own: what the sidebar drops, it drops too."""
    with pytest.raises(InvalidLandingNarrowingError):
        ensure_the_narrowing_is_buildable(
            [demo_condition(BLADE, SILVER)],
            category_id=CATEGORY,
            dictionary=demo_attributes(),
        )


def test_a_numeric_attribute_narrows_nothing() -> None:
    """A number is typed, not picked: the sidebar builds no group from it."""
    with pytest.raises(InvalidLandingNarrowingError):
        ensure_the_narrowing_is_buildable(
            [demo_condition(CUTOUTS, CUTOUT)],
            category_id=CATEGORY,
            dictionary=demo_attributes(),
        )


def test_the_whole_dictionary_of_an_attribute_is_the_category_itself() -> None:
    """Every value ticked leaves the catalogue untouched — a duplicate of the category under its own address."""
    with pytest.raises(InvalidLandingNarrowingError):
        ensure_the_narrowing_is_buildable(
            [demo_condition(SHAPE, ROUND), demo_condition(SHAPE, RECTANGULAR)],
            category_id=CATEGORY,
            dictionary=demo_attributes(),
        )


def test_two_attributes_narrowed_by_their_own_values_are_buildable() -> None:
    """The shape and the backlight of the old site's pages: values by OR, attributes by AND."""
    ensure_the_narrowing_is_buildable(
        [demo_condition(), demo_condition(BACKLIGHT, CONTOUR)],
        category_id=CATEGORY,
        dictionary=demo_attributes(),
    )
