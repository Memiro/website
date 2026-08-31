from dishka import Provider, Scope, provide_all

from memiro.application.browse_catalog import ListCategories, ListCategoryProducts, ReadProduct
from memiro.application.calculate_price import CalculatePrice
from memiro.application.manage_products import (
    AddVariant,
    ChangeVariant,
    DuplicateVariantWithSize,
    RemoveVariant,
)
from memiro.application.submit_inquiry import SubmitInquiry


class InteractorProvider(Provider):
    """One explicit ``provide_all(...)`` list of interactors (§9.3)."""

    scope = Scope.REQUEST

    interactors = provide_all(
        AddVariant,
        ListCategories,
        ListCategoryProducts,
        ReadProduct,
        CalculatePrice,
        ChangeVariant,
        DuplicateVariantWithSize,
        RemoveVariant,
        SubmitInquiry,
    )
