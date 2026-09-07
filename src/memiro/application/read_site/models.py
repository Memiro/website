from pydantic import BaseModel


class ContactsModel(BaseModel):
    """The studio as a visitor may reach it: one row per site, the owner's data.

    City and street are kept apart because ``LocalBusiness`` markup needs them
    apart while the storefront prints one line. An empty link means "do not
    show": the site draws no icon into nowhere.
    """

    city: str
    street: str
    phone: str
    phone_display: str
    email: str
    hours: str
    max_link: str
    telegram: str
    vk: str
    map_embed: str


class RequisiteModel(BaseModel):
    """One published requisite of the seller, with the caption it is printed under."""

    label: str
    value: str


class SiteModel(BaseModel):
    """What every page of the storefront needs about the studio behind it."""

    contacts: ContactsModel | None
    seller: list[RequisiteModel]
