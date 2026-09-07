from enum import StrEnum

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


class Requisite(StrEnum):
    """The requisites of the seller a marketplace page must carry."""

    NAME = "name"
    OGRN = "ogrn"
    INN = "inn"
    ADDRESS = "address"


class RequisiteModel(BaseModel):
    """One published requisite of the seller: which one it is and what the owner filled in."""

    kind: Requisite
    value: str


class SiteModel(BaseModel):
    """What every page of the storefront needs about the studio behind it."""

    contacts: ContactsModel | None
    seller: list[RequisiteModel]
