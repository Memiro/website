"""Forms and readings the three work scenarios share."""

from typing import override

from dishka import AsyncContainer

from memiro.application.common.gateway.image_upload import ImageUpload
from memiro.application.common.gateway.work import WorkGateway, WorkPhotoStorage, WorkRow
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
from tests.common.photograph import photograph

# The smallest file that is still a file: what these tests upload is a photo
# only by its name, and nothing in the slice looks inside it.
PHOTO = photograph()
SECOND_PHOTO = photograph(shade=200)

WORK_TITLE = "Круглое зеркало в прихожей"

# The column the issued key is stored in: a longer one is what the database
# refuses after the file has already been written.
STORED_KEY_LENGTH = 255


class FakeWorkPhotoStorage(WorkPhotoStorage):
    """Storage that issues one key over and over and remembers what was dropped."""

    def __init__(self, key: str) -> None:
        """Keep the one key this storage answers with and the log of removals."""
        self.key = key
        self.removed: list[str] = []

    @override
    async def put(self, upload: ImageUpload) -> str:
        """Answer with the key this storage was built around."""
        return self.key

    @override
    async def remove(self, key: str) -> None:
        """Remember which key the caller dropped."""
        self.removed.append(key)


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
