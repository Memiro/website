"""Use case: Manage the attribute dictionary.

Actor: the owner established by the Django presentation.
"""

from memiro.application.manage_attributes.change_attribute import ChangeAttribute, ChangeAttributeForm
from memiro.application.manage_attributes.create_attribute import (
    CreateAttribute,
    CreateAttributeForm,
    CreatedAttribute,
)
from memiro.application.manage_attributes.remove_attribute import RemoveAttribute
from memiro.application.manage_attributes.replace_values import ReplaceValues, ReplaceValuesForm
from memiro.application.manage_attributes.shared import AttributeRootForm, AttributeValueForm, ValueSetForm

__all__ = [
    "AttributeRootForm",
    "AttributeValueForm",
    "ChangeAttribute",
    "ChangeAttributeForm",
    "CreateAttribute",
    "CreateAttributeForm",
    "CreatedAttribute",
    "RemoveAttribute",
    "ReplaceValues",
    "ReplaceValuesForm",
    "ValueSetForm",
]
