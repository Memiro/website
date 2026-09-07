from fastapi import status
from sqlalchemy.ext.asyncio import AsyncEngine

from memiro.application.read_site import ContactsModel, Requisite, RequisiteModel, SiteModel
from tests.integration.api_client import ApiClient
from tests.integration.prime import prime_site_data

EXPECTED_CONTACTS = ContactsModel(
    city="Санкт-Петербург",
    street="Александра Матросова, 4к2ж",
    phone="+79812304050",
    phone_display="+7 981 230-40-50",
    email="memiro.ru@yandex.ru",
    hours="Ежедневно, по предварительной записи",
    max_link="",
    telegram="https://t.me/memiro_shop",
    vk="https://vk.com/memirospb",
    map_embed="",
)


async def test_the_storefront_reads_the_studio_contacts_the_owner_entered(
    api_client: ApiClient,
    engine: AsyncEngine,
) -> None:
    """Contacts are the owner's data, so the storefront asks for them instead of carrying them."""
    await prime_site_data(engine)

    assert (await api_client.read_site()).assert_status(status.HTTP_200_OK).ensure_content() == SiteModel(
        contacts=EXPECTED_CONTACTS,
        seller=[],
    )


async def test_a_filled_requisite_arrives_named_by_what_it_is(
    api_client: ApiClient,
    engine: AsyncEngine,
) -> None:
    """The storefront gets the requisite it asked for and writes the caption itself."""
    await prime_site_data(engine, seller_name="ИП Иванов Иван Иванович", ogrn="321784700000000")

    seller = (await api_client.read_site()).assert_status(status.HTTP_200_OK).ensure_content().seller

    assert seller == [
        RequisiteModel(kind=Requisite.NAME, value="ИП Иванов Иван Иванович"),
        RequisiteModel(kind=Requisite.OGRN, value="321784700000000"),
    ]


async def test_a_seller_nobody_named_prints_no_requisites(api_client: ApiClient) -> None:
    """An empty requisite is not printed: a wrong OGRN is worse than a missing one."""
    site = (await api_client.read_site()).assert_status(status.HTTP_200_OK).ensure_content()

    assert site.seller == []
