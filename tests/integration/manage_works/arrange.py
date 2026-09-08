"""Forms and readings the three work scenarios share."""

from dishka import AsyncContainer

from memiro.application.common.gateway.work import WorkGateway, WorkRow
from memiro.application.manage_works import (
    ChangeWork,
    ChangeWorkForm,
    CreatedWork,
    CreateWork,
    CreateWorkForm,
    RemoveWork,
)
from memiro.entities.common.identifiers import WorkId
from tests.common.factory.catalog import PRODUCT

# The smallest file that is still a file: what these tests upload is a photo
# only by its name, and nothing in the slice looks inside it.
PHOTO = b"\xff\xd8\xff\xd9"
SECOND_PHOTO = b"\xff\xd8\x00\xd9"

WORK_TITLE = "Круглое зеркало в прихожей"


def photo_form(**overrides: object) -> dict[str, object]:
    """Build the file half of the card."""
    return {"filename": "installed.JPG", "content": PHOTO} | overrides


def create_form(**overrides: object) -> CreateWorkForm:
    """Build the owner's card for one installed mirror."""
    fields: dict[str, object] = {
        "photo": photo_form(),
        "product_id": PRODUCT,
        "title": WORK_TITLE,
        "description": "Поставили в прихожей квартиры на Ленина.",
        "is_published": True,
        "sort_order": 1,
    }
    return CreateWorkForm.model_validate(fields | overrides)


def change_form(**overrides: object) -> ChangeWorkForm:
    """Build the card of a saved work: the same fields, the photo optional."""
    fields = create_form(**overrides).model_dump()
    fields["photo"] = None
    return ChangeWorkForm.model_validate(fields | overrides)


async def load_work(container: AsyncContainer, work_id: WorkId) -> WorkRow | None:
    """Read one work back in a fresh transaction after a command."""
    async with container() as request:
        gateway: WorkGateway = await request.get(WorkGateway)
        return await gateway.get(work_id)


async def create_work(container: AsyncContainer, form: CreateWorkForm) -> CreatedWork:
    """Execute one creation in its own production REQUEST scope."""
    async with container() as request:
        interactor = await request.get(CreateWork)
        return await interactor.execute(form)


async def change_work(container: AsyncContainer, work_id: WorkId, form: ChangeWorkForm) -> None:
    """Execute one edit in its own production REQUEST scope."""
    async with container() as request:
        interactor = await request.get(ChangeWork)
        await interactor.execute(work_id, form)


async def remove_work(container: AsyncContainer, work_id: WorkId) -> None:
    """Execute one removal in its own production REQUEST scope."""
    async with container() as request:
        interactor = await request.get(RemoveWork)
        await interactor.execute(work_id)
