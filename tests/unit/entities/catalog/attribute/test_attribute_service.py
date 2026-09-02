from dataclasses import replace
from uuid import uuid4

import pytest

from memiro.entities.catalog.attribute.attribute_service import (
    ensure_parents_are_usable,
    names_depending_on,
)
from memiro.entities.common.identifiers import AttributeId
from memiro.entities.errors.attribute import InvalidAttributeParentError
from tests.common.factory.catalog import (
    BACKLIGHT,
    BLADE,
    CATEGORY,
    HEATING,
    SECOND_CATEGORY,
    demo_attributes,
    demo_blade,
    demo_heating,
)

_STRANGER: AttributeId = uuid4()


def test_a_parent_of_the_same_category_is_usable() -> None:
    """Heating may depend on backlight: both describe products of one category."""
    ensure_parents_are_usable(
        (BACKLIGHT,),
        attribute_id=HEATING,
        category_id=CATEGORY,
        dictionary=demo_attributes(),
    )


def test_a_parentage_fails_if_the_parent_does_not_exist() -> None:
    """INVALID_ATTRIBUTE_PARENT: an attribute cannot depend on a row of the dictionary that is not there."""
    with pytest.raises(InvalidAttributeParentError):
        ensure_parents_are_usable(
            (_STRANGER,),
            attribute_id=HEATING,
            category_id=CATEGORY,
            dictionary=demo_attributes(),
        )


def test_a_parentage_fails_if_the_parent_belongs_to_another_category() -> None:
    """INVALID_ATTRIBUTE_PARENT: dependence is read inside one category and nowhere across."""
    foreign = replace(demo_blade(), category_id=SECOND_CATEGORY)

    with pytest.raises(InvalidAttributeParentError):
        ensure_parents_are_usable(
            (BLADE,),
            attribute_id=HEATING,
            category_id=CATEGORY,
            dictionary=[foreign, demo_heating()],
        )


def test_an_attribute_fails_if_it_is_made_its_own_parent() -> None:
    """INVALID_ATTRIBUTE_PARENT: an attribute cannot depend on itself."""
    with pytest.raises(InvalidAttributeParentError):
        ensure_parents_are_usable(
            (HEATING,),
            attribute_id=HEATING,
            category_id=CATEGORY,
            dictionary=demo_attributes(),
        )


def test_a_parentage_fails_if_it_closes_a_circle() -> None:
    """INVALID_ATTRIBUTE_PARENT: backlight already depends on heating, so heating cannot depend on backlight."""
    circular = replace(demo_attributes()[3], parent_ids=(HEATING,))

    with pytest.raises(InvalidAttributeParentError):
        ensure_parents_are_usable(
            (BACKLIGHT,),
            attribute_id=HEATING,
            category_id=CATEGORY,
            dictionary=[circular, demo_heating()],
        )


def test_a_new_attribute_may_name_parents_before_it_has_an_identifier() -> None:
    """Creation has no identifier yet, and a circle through a nameless attribute cannot exist."""
    ensure_parents_are_usable(
        (BACKLIGHT,),
        attribute_id=None,
        category_id=CATEGORY,
        dictionary=demo_attributes(),
    )


def test_nothing_depends_on_an_attribute_no_one_named_a_parent() -> None:
    """Heating is nobody's parent, so removing it would leave no dangling dependence."""
    assert names_depending_on(HEATING, dictionary=demo_attributes()) == ()


def test_an_attribute_names_the_dependants_that_keep_it_in_place() -> None:
    """Heating depends on backlight, so backlight is told who still needs it."""
    assert names_depending_on(BACKLIGHT, dictionary=demo_attributes()) == ("Подогрев",)
