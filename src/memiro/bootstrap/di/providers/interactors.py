from dishka import Provider, Scope, provide_all

from memiro.application.browse_catalog import (
    ListCategories,
    ListCategoryProducts,
    ListLandings,
    ListWorks,
    ReadLanding,
    ReadProduct,
)
from memiro.application.calculate_price import CalculatePrice
from memiro.application.export_pricing_workbook import ExportPricingWorkbook
from memiro.application.manage_attributes import (
    ChangeAttribute,
    CreateAttribute,
    RemoveAttribute,
    ReplaceValues,
)
from memiro.application.manage_landings import ChangeLanding, CreateLanding, RemoveLanding
from memiro.application.manage_pricing_settings import ChangePricingSettings
from memiro.application.manage_products import (
    AddImage,
    AddVariant,
    ChangeProduct,
    ChangeVariant,
    CreateProduct,
    DeclareValues,
    DuplicateVariantWithSize,
    ListPricingGaps,
    ListVariants,
    QuoteVariant,
    RemoveImage,
    RemoveProduct,
    RemoveVariant,
)
from memiro.application.manage_works import ChangeWork, CreateWork, RemoveWork
from memiro.application.read_site import ReadSite
from memiro.application.reprice_products import RepriceProducts
from memiro.application.submit_inquiry import PreviewInquiry, SubmitInquiry


class InteractorProvider(Provider):
    """One explicit ``provide_all(...)`` list of interactors (§9.3)."""

    scope = Scope.REQUEST

    interactors = provide_all(
        AddImage,
        AddVariant,
        ChangeAttribute,
        ChangeLanding,
        ChangePricingSettings,
        ChangeProduct,
        CreateAttribute,
        CreateLanding,
        CreateProduct,
        DeclareValues,
        RemoveAttribute,
        RemoveLanding,
        RemoveImage,
        RemoveProduct,
        ReplaceValues,
        ListCategories,
        ListCategoryProducts,
        ListLandings,
        ReadLanding,
        ReadProduct,
        CalculatePrice,
        ChangeVariant,
        ChangeWork,
        CreateWork,
        DuplicateVariantWithSize,
        ExportPricingWorkbook,
        ListPricingGaps,
        ListVariants,
        ListWorks,
        QuoteVariant,
        ReadSite,
        RemoveVariant,
        RemoveWork,
        RepriceProducts,
        PreviewInquiry,
        SubmitInquiry,
    )
