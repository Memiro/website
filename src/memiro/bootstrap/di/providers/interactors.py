from dishka import Provider, Scope, provide_all

from memiro.application.browse_catalog import ListCategories, ListCategoryProducts, ReadProduct
from memiro.application.calculate_price import CalculatePrice
from memiro.application.manage_attributes import (
    ChangeAttribute,
    CreateAttribute,
    RemoveAttribute,
    ReplaceValues,
)
from memiro.application.manage_pricing_settings import ChangePricingSettings
from memiro.application.manage_products import (
    AddVariant,
    ChangeProduct,
    ChangeVariant,
    CreateProduct,
    DeclareValues,
    DuplicateVariantWithSize,
    RemoveProduct,
    RemoveVariant,
)
from memiro.application.reprice_products import RepriceProducts
from memiro.application.submit_inquiry import SubmitInquiry


class InteractorProvider(Provider):
    """One explicit ``provide_all(...)`` list of interactors (§9.3)."""

    scope = Scope.REQUEST

    interactors = provide_all(
        AddVariant,
        ChangeAttribute,
        ChangeProduct,
        CreateProduct,
        DeclareValues,
        RemoveProduct,
        ChangePricingSettings,
        CreateAttribute,
        RemoveAttribute,
        ReplaceValues,
        ListCategories,
        ListCategoryProducts,
        ReadProduct,
        CalculatePrice,
        ChangeVariant,
        DuplicateVariantWithSize,
        RemoveVariant,
        RepriceProducts,
        SubmitInquiry,
    )
