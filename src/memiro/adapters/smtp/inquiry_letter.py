"""The HTML half of the manager email: the words of the text half, laid out for a mail client."""

import html
from datetime import datetime
from zoneinfo import ZoneInfo

from memiro.adapters.common.inquiry_wording import price_words, size_words, specification_words
from memiro.entities.inquiry.entity import Inquiry, InquiryConfiguration, InquiryItem, InquirySource
from memiro.entities.inquiry.phone import Phone

# The aggregate keeps UTC; the studio reads the letter on its own wall clock.
_STUDIO_TIMEZONE = ZoneInfo("Europe/Moscow")

_MONTHS = (
    "января",
    "февраля",
    "марта",
    "апреля",
    "мая",
    "июня",
    "июля",
    "августа",
    "сентября",
    "октября",
    "ноября",
    "декабря",
)
_SELECTION_WORDS = "подборка"
_CONTACT_FORM_WORDS = "форма контактов"
_NO_EMAIL_WORDS = "не указан"
# A Russian number in E.164: the country code and ten national digits.
_RUSSIAN_NUMBER_DIGITS = 11
# Russian plural forms go by the last digit, except the teens, which take the
# form of "many".
_FEW = range(2, 5)
_TEENS = range(11, 15)

# The storefront's tokens.css in hex: a mail client reads neither CSS
# variables nor oklch, and every style is inlined for the same reason.
_PAPER = "#ffffff"
_PAPER_2 = "#f4f5f6"
_INK = "#0a0b0d"
_INK_2 = "#313335"
_MUTED = "#66696c"
_RULE = "#d6d8d9"
_RULE_2 = "#e7e8e9"
_ACCENT = "#003c90"
_FONT = "-apple-system,'Segoe UI',Roboto,Arial,sans-serif"
_TABLE_ATTRIBUTES = 'role="presentation" cellpadding="0" cellspacing="0" border="0"'
_LABEL = f"font-size:12px;letter-spacing:0.08em;text-transform:uppercase;color:{_MUTED};"
_ROW_LABEL = f"padding-right:16px;color:{_MUTED};white-space:nowrap;"
_LINK = f"color:{_ACCENT};text-decoration:none;"
_CELL = f"padding:6px 0;border-top:1px solid {_RULE_2};"


def _phone_words(phone: Phone) -> str:
    """Spell a Russian number the way it is dialled, "+7 921 123-45-67"; any other keeps its digits behind a plus."""
    digits = phone.value.removeprefix("+")
    if len(digits) == _RUSSIAN_NUMBER_DIGITS and digits.startswith("7"):
        return f"+7 {digits[1:4]} {digits[4:7]}-{digits[7:9]}-{digits[9:]}"
    return f"+{digits}"


def _mirror_count_words(count: int) -> str:
    """Spell the number of mirrors with the Russian plural form it takes."""
    if count % 100 not in _TEENS and count % 10 == 1:
        return f"{count} зеркало"
    if count % 100 not in _TEENS and count % 10 in _FEW:
        return f"{count} зеркала"
    return f"{count} зеркал"


def _date_words(moment: datetime) -> str:
    """Spell the instant on the studio's wall clock: "10 сентября 2026, 14:32"."""
    local = moment.astimezone(_STUDIO_TIMEZONE)
    return f"{local.day} {_MONTHS[local.month - 1]} {local.year}, {local:%H:%M}"


def _source_words(source: InquirySource) -> str:
    """Name where the inquiry came from in the manager's words."""
    return _SELECTION_WORDS if source is InquirySource.SELECTION else _CONTACT_FORM_WORDS


def _contact_row(label: str, value: str) -> str:
    """Render one "label — value" row of the client block; ``value`` is already HTML."""
    return f'<tr><td style="{_ROW_LABEL}">{label}</td><td style="color:{_INK};">{value}</td></tr>'


def _client_block(inquiry: Inquiry) -> list[str]:
    """Render the client: the name large, the contacts as links, the date, the source."""
    phone = html.escape(inquiry.phone.value)
    email = (
        f'<a href="mailto:{html.escape(inquiry.email)}" style="{_LINK}">{html.escape(inquiry.email)}</a>'
        if inquiry.email
        else f'<span style="color:{_MUTED};">{_NO_EMAIL_WORDS}</span>'
    )
    return [
        '<tr><td style="padding:28px 32px 8px;">',
        f'<div style="{_LABEL}">Заявка</div>',
        (
            f'<div style="padding-top:6px;font-size:26px;line-height:32px;font-weight:600;color:{_INK};">'
            f"{html.escape(inquiry.name)}</div>"
        ),
        f'<table {_TABLE_ATTRIBUTES} style="margin-top:14px;font-size:15px;line-height:24px;">',
        _contact_row(
            "Телефон", f'<a href="tel:{phone}" style="{_LINK}">{html.escape(_phone_words(inquiry.phone))}</a>'
        ),
        _contact_row("Email", email),
        _contact_row("Дата", _date_words(inquiry.created_at)),
        _contact_row("Источник", _source_words(inquiry.source)),
        "</table>",
        "</td></tr>",
    ]


def _card(body: list[str], *, first: bool) -> list[str]:
    """Frame a card; the first one stands clear of the client block, the rest of each other."""
    top = 20 if first else 12
    return [
        f'<tr><td style="padding:{top}px 32px 0;">',
        f'<table {_TABLE_ATTRIBUTES} width="100%" style="border:1px solid {_RULE};">',
        '<tr><td style="padding:18px 20px 16px;">',
        *body,
        "</td></tr>",
        "</table>",
        "</td></tr>",
    ]


def _comment_card(comment: str) -> list[str]:
    """Render the free-form comment as the only card of the letter."""
    return [
        f'<div style="{_LABEL}">Комментарий</div>',
        f'<div style="padding-top:6px;font-size:15px;line-height:22px;color:{_INK};">{html.escape(comment)}</div>',
    ]


def _specification(configuration: InquiryConfiguration) -> list[str]:
    """Render the size and the "attribute — value" rows of one mirror."""
    rows = [
        f'<tr><td style="{_CELL}color:{_MUTED};">{html.escape(attribute)}</td>'
        f'<td align="right" style="{_CELL}color:{_INK};">{html.escape(words)}</td></tr>'
        for attribute, words in map(specification_words, configuration.values)
    ]
    return [
        (
            f'<div style="padding-top:4px;font-size:15px;line-height:22px;color:{_INK_2};">'
            f"{html.escape(size_words(configuration.dimensions))}</div>"
        ),
        f'<table {_TABLE_ATTRIBUTES} width="100%" style="margin-top:12px;font-size:14px;line-height:20px;">',
        *rows,
        "</table>",
    ]


def _item_card(index: int, item: InquiryItem) -> list[str]:
    """Render one mirror: name, size, the specification as rows, the price in words, the wish."""
    lines = [
        f'<div style="{_LABEL}">Зеркало {index}</div>',
        (
            f'<div style="padding-top:4px;font-size:18px;line-height:24px;font-weight:600;color:{_INK};">'
            f"{html.escape(item.product_name)}</div>"
        ),
    ]
    if item.configuration is not None:
        lines.extend(_specification(item.configuration))
    lines.append(
        f'<div style="margin-top:8px;padding-top:12px;border-top:1px solid {_RULE};font-size:15px;line-height:22px;'
        f'font-weight:600;color:{_INK};">{html.escape(price_words(item.verdict, item.calculated_price))}</div>'
    )
    if item.wish:
        lines.append(
            f'<div style="padding-top:10px;font-size:14px;line-height:20px;color:{_INK_2};">'
            f'<span style="color:{_MUTED};">Пожелание:</span> {html.escape(item.wish)}</div>'
        )
    return lines


def _cards(inquiry: Inquiry) -> list[str]:
    """Render one card per mirror, or the comment card of a contact-form inquiry."""
    if not inquiry.items:
        return _card(_comment_card(inquiry.comment), first=True)
    return [
        line
        for index, item in enumerate(inquiry.items, start=1)
        for line in _card(_item_card(index, item), first=index == 1)
    ]


def letter_subject(inquiry: Inquiry) -> str:
    """Name the client and the number of mirrors, so the manager tells inquiries apart in the list."""
    subject = f"Заявка от {inquiry.name}, {_phone_words(inquiry.phone)}"
    if inquiry.items:
        return f"{subject} · {_mirror_count_words(len(inquiry.items))}"
    return subject


def letter_html(inquiry: Inquiry) -> str:
    """Render the saved snapshot as the approved letter: header, client, one card per mirror, footer."""
    cards = _cards(inquiry)
    return "\n".join(
        [
            "<!DOCTYPE html>",
            '<html lang="ru">',
            '<head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">',
            f"<title>{html.escape(letter_subject(inquiry))}</title></head>",
            f'<body style="margin:0;padding:0;background:{_PAPER_2};">',
            f'<table {_TABLE_ATTRIBUTES} width="100%" style="background:{_PAPER_2};">',
            '<tr><td align="center" style="padding:24px 12px;">',
            (
                f'<table {_TABLE_ATTRIBUTES} width="100%" style="max-width:600px;background:{_PAPER};'
                f'font-family:{_FONT};color:{_INK};">'
            ),
            (
                f'<tr><td style="padding:28px 32px 20px;border-bottom:1px solid {_RULE};font-size:13px;font-weight:600;'
                f'letter-spacing:0.3em;text-transform:uppercase;color:{_INK};">Memiro</td></tr>'
            ),
            *_client_block(inquiry),
            *cards,
            '<tr><td style="height:28px;font-size:0;line-height:0;">&nbsp;</td></tr>',
            (
                f'<tr><td style="padding:24px 32px;border-top:1px solid {_RULE};font-size:12px;line-height:18px;'
                f'color:{_MUTED};">Заявка {inquiry.id}</td></tr>'
            ),
            "</table>",
            "</td></tr>",
            "</table>",
            "</body>",
            "</html>",
        ]
    )
