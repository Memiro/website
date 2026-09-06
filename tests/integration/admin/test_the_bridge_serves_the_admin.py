"""The bridge the admin writes through: one loop, one engine, and a best-effort Django half."""

import asyncio
from http import HTTPStatus
from typing import Any, cast

import pytest
from dishka import AsyncContainer
from django.apps import apps
from django.contrib.messages import get_messages
from django.contrib.messages.storage.cookie import CookieStorage
from django.db.models import Manager
from django.http import HttpRequest, HttpResponse
from django.test import RequestFactory
from sqlalchemy.ext.asyncio import AsyncEngine

from memiro.presentation.django_admin.attribute_card import create_attribute
from memiro.presentation.django_admin.bridge import bridge
from memiro.presentation.django_admin.writes import HISTORY_LOST, guarded_write
from tests.integration.admin.arrange import card_fields

pytestmark = pytest.mark.usefixtures("admin_site", "primed_catalog")

CARD_URL = "/admin/memiro/attribute/add/"
SAVED_NAME = "Сохранён без истории"


async def _home_of_the_command(scope: AsyncContainer) -> tuple[int, int]:
    """Name the loop a command runs in and the engine its container holds in APP scope."""
    return id(asyncio.get_running_loop()), id(await scope.get(AsyncEngine))


def _request() -> HttpRequest:
    """Build one admin POST that can carry the messages a write leaves behind."""
    request = RequestFactory().post(CARD_URL)
    # The storage the message middleware installs in production, put where it
    # puts it: a request built by hand has been through no middleware.
    request._messages = CookieStorage(request)  # type: ignore[attr-defined]  # noqa: SLF001

    return request


def _fails_after_the_commit() -> HttpResponse:
    """Send a whole card to the interactors, then fall over the way the Django half can."""
    root, rows = card_fields(name=SAVED_NAME)
    create_attribute(root, rows)
    message = "LogEntry could not be written"
    raise RuntimeError(message)


def _fails_before_any_command() -> HttpResponse:
    """Stand in for a defect that strikes before anything reaches the domain."""
    message = "The card could not be rendered"
    raise RuntimeError(message)


async def test_two_commands_in_a_row_are_served_by_one_loop_and_one_container() -> None:
    """The bridge is the process's own: its loop and its engine outlive a single command (ADR-0012)."""
    first = bridge().call(_home_of_the_command)
    second = bridge().call(_home_of_the_command)

    assert first == second


async def test_the_admin_process_has_exactly_one_bridge() -> None:
    """Every screen asking for the bridge is handed the same one."""
    assert bridge() is bridge()


async def test_a_failure_after_the_commit_becomes_a_warning_and_the_domain_keeps_the_write() -> None:
    """The Django half is best-effort: its failure warns the owner and the attribute stays written."""
    request = _request()

    response = await asyncio.to_thread(guarded_write, request, _fails_after_the_commit)

    assert response.status_code == HTTPStatus.FOUND
    assert [str(message) for message in get_messages(request)] == [HISTORY_LOST]
    assert await _attributes().filter(name=SAVED_NAME).aexists()


def _attributes() -> Manager[Any]:
    """Reach the attribute mirror; the app registry is only ready once Django is configured."""
    return cast("Manager[Any]", apps.get_model("memiro", "Attribute").objects)


async def test_a_failure_before_any_command_is_not_swallowed() -> None:
    """A defect that strikes before the domain is written is a defect, not a warning."""
    with pytest.raises(RuntimeError):
        guarded_write(_request(), _fails_before_any_command)
