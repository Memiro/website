"""Use case: Manage products.

Actor: the owner established by the Django presentation.
"""

from memiro.application.manage_products.add_variant import AddVariant, AddVariantForm
from memiro.application.manage_products.change_product import ChangeProduct, ChangeProductForm
from memiro.application.manage_products.change_variant import ChangeVariant, ChangeVariantForm
from memiro.application.manage_products.create_product import CreatedProduct, CreateProduct, CreateProductForm
from memiro.application.manage_products.declare_values import DeclareValues, DeclareValuesForm
from memiro.application.manage_products.duplicate_variant_with_size import (
    DuplicateVariantWithSize,
    DuplicateVariantWithSizeForm,
)
from memiro.application.manage_products.list_pricing_gaps import ListPricingGaps, ProductPricingGaps
from memiro.application.manage_products.remove_product import RemoveProduct
from memiro.application.manage_products.remove_variant import RemoveVariant
from memiro.application.manage_products.shared import (
    SLUG_PATTERN,
    CreatedVariant,
    DeclarationForm,
    ProductForm,
    VariantForm,
    VariantOverrideForm,
)

__all__ = [
    "SLUG_PATTERN",
    "AddVariant",
    "AddVariantForm",
    "ChangeProduct",
    "ChangeProductForm",
    "ChangeVariant",
    "ChangeVariantForm",
    "CreateProduct",
    "CreateProductForm",
    "CreatedProduct",
    "CreatedVariant",
    "DeclarationForm",
    "DeclareValues",
    "DeclareValuesForm",
    "DuplicateVariantWithSize",
    "DuplicateVariantWithSizeForm",
    "ListPricingGaps",
    "ProductForm",
    "ProductPricingGaps",
    "RemoveProduct",
    "RemoveVariant",
    "VariantForm",
    "VariantOverrideForm",
]
