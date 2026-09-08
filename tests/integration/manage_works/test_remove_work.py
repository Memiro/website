from uuid import uuid4

import pytest
from dishka import AsyncContainer

from memiro.application.errors.catalog import WorkNotFoundError
from memiro.bootstrap.config_loader import Config
from tests.integration.manage_works.arrange import create_form, create_work, load_work, remove_work

pytestmark = pytest.mark.usefixtures("catalog")


async def test_the_owner_takes_a_work_out_of_the_gallery(container: AsyncContainer, config: Config) -> None:
    """A removed work leaves the gallery, and its photo leaves the storage with it."""
    created = await create_work(container, create_form())
    work = await load_work(container, created.id)
    assert work is not None

    await remove_work(container, created.id)

    assert await load_work(container, created.id) is None
    assert not (config.media.root / work.photo_key).exists()


async def test_a_work_nobody_entered_is_refused(container: AsyncContainer) -> None:
    """WORK_NOT_FOUND: there is nothing to take out of the gallery."""
    with pytest.raises(WorkNotFoundError):
        await remove_work(container, uuid4())
