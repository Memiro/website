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
# variables nor oklch, and every style is inlined for the same reason. The
# fonts are the system stacks: mail clients drop web fonts.
_PAPER = "#ffffff"
_PAPER_2 = "#f4f5f6"
_INK = "#0a0b0d"
_INK_2 = "#313335"
_MUTED = "#66696c"
_RULE = "#d6d8d9"
_RULE_2 = "#e7e8e9"
_ACCENT = "#003c90"
_BODY_FONT = "-apple-system,'Segoe UI',Roboto,Helvetica,Arial,sans-serif"
_MONO_FONT = "ui-monospace,Menlo,Consolas,'Roboto Mono','Courier New',monospace"
_TABLE_ATTRIBUTES = 'role="presentation" cellpadding="0" cellspacing="0" border="0"'
_MONO_PLAIN = f"font-family:{_MONO_FONT};font-variant-numeric:tabular-nums;"
_MONO_CAPS = f"{_MONO_PLAIN}letter-spacing:0.06em;text-transform:uppercase;"
_LABEL = f"{_MONO_CAPS}font-size:11px;line-height:16px;color:{_MUTED};"
_DISPLAY = f"font-weight:800;letter-spacing:-0.02em;text-transform:uppercase;color:{_INK};"
_CELL = f"padding:8px 0;border-top:1px solid {_RULE_2};font-size:14px;line-height:20px;"
_BUTTON_LABEL = f"{_MONO_CAPS}font-size:12px;line-height:16px;font-weight:500;text-decoration:none;display:block;"


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


def _section_label(number: str, words: str) -> str:
    """Render the hanging mono label of a section, "01 / Клиент", the way the storefront heads its sections."""
    return f'<div style="{_LABEL}"><span style="color:{_ACCENT};">{number} /</span> {html.escape(words)}</div>'


def _masthead() -> list[str]:
    """Render the wordmark over the hair rule of the storefront's nav."""
    return [
        f'<tr><td style="padding:22px 32px 18px;border-bottom:1px solid {_RULE};">',
        f'<table {_TABLE_ATTRIBUTES} width="100%"><tr>',
        f'<td style="{_DISPLAY}font-size:15px;line-height:20px;letter-spacing:0.14em;">Memiro</td>',
        f'<td align="right" style="{_LABEL}">Заявка</td>',
        "</tr></table>",
        "</td></tr>",
    ]


def _button(href: str, words: str, *, filled: bool) -> str:
    """Render a small storefront button as a padded cell: the ink-filled primary or the ghost one."""
    box = f"background:{_INK};" if filled else f"border:1px solid {_INK};"
    color = _PAPER if filled else _INK
    return (
        f'<td style="{box}padding:11px 16px;"><a href="{href}" style="{_BUTTON_LABEL}color:{color};">'
        f"{words} &rarr;</a></td>"
    )


def _client_block(inquiry: Inquiry) -> list[str]:
    """Render the client: the name as a display heading, the contacts in mono, the buttons to reach them."""
    tel = f"tel:{html.escape(inquiry.phone.value)}"
    mailto = f"mailto:{html.escape(inquiry.email)}" if inquiry.email else ""
    link = f"color:{_INK};text-decoration:none;"
    email = (
        f'<a href="{mailto}" style="{link}">{html.escape(inquiry.email)}</a>'
        if inquiry.email
        else f'<span style="color:{_MUTED};">{_NO_EMAIL_WORDS}</span>'
    )
    buttons = [_button(tel, "Позвонить", filled=True)]
    if mailto:
        buttons.append(f'<td style="width:8px;"></td>{_button(mailto, "Написать", filled=False)}')
    return [
        '<tr><td style="padding:28px 32px 24px;">',
        _section_label("01", "Клиент"),
        f'<div style="padding-top:8px;{_DISPLAY}font-size:30px;line-height:34px;">{html.escape(inquiry.name)}</div>',
        f'<div style="padding-top:14px;{_MONO_PLAIN}font-size:14px;line-height:22px;color:{_INK};">',
        f'<a href="{tel}" style="{link}">{html.escape(_phone_words(inquiry.phone))}</a><br>{email}',
        "</div>",
        f'<div style="padding-top:6px;{_MONO_PLAIN}font-size:12px;line-height:16px;color:{_MUTED};">',
        f"{_date_words(inquiry.created_at)} &middot; {_source_words(inquiry.source)}",
        "</div>",
        '<div style="padding-top:18px;">',
        f"<table {_TABLE_ATTRIBUTES}><tr>{''.join(buttons)}</tr></table>",
        "</div>",
        "</td></tr>",
    ]


def _card(body: list[str]) -> list[str]:
    """Frame a card with the hair rule of the storefront, no radius, no shadow."""
    return [
        '<tr><td style="padding:0 32px 12px;">',
        f'<table {_TABLE_ATTRIBUTES} width="100%" style="border:1px solid {_RULE};">',
        *body,
        "</table>",
        "</td></tr>",
    ]


def _comment_card(comment: str) -> list[str]:
    """Render the free-form comment as the only card of the letter."""
    return [
        '<tr><td style="padding:18px 20px 20px;">',
        f'<div style="font-size:16px;line-height:24px;color:{_INK};">{html.escape(comment)}</div>',
        "</td></tr>",
    ]


def _specification(configuration: InquiryConfiguration) -> list[str]:
    """Render the size in mono and the "attribute — value" rows of one mirror."""
    rows = [
        f'<tr><td style="{_CELL}color:{_MUTED};">{html.escape(attribute)}</td>'
        f'<td align="right" style="{_CELL}color:{_INK};font-weight:600;">{html.escape(words)}</td></tr>'
        for attribute, words in map(specification_words, configuration.values)
    ]
    return [
        (
            f'<div style="padding-top:6px;{_MONO_PLAIN}font-size:13px;line-height:20px;color:{_INK};">'
            f"{html.escape(size_words(configuration.dimensions))}</div>"
        ),
        f'<table {_TABLE_ATTRIBUTES} width="100%" style="margin-top:12px;">',
        *rows,
        "</table>",
    ]


def _item_card(index: int, item: InquiryItem) -> list[str]:
    """Render one mirror: its number and name, the size and rows, the price strip, the wish."""
    specification = _specification(item.configuration) if item.configuration is not None else []
    lines = [
        '<tr><td style="padding:16px 20px 14px;">',
        f'<div style="{_LABEL}">Зеркало {index}</div>',
        (
            f'<div style="padding-top:4px;{_DISPLAY}font-weight:700;letter-spacing:0.02em;font-size:16px;'
            f'line-height:22px;">{html.escape(item.product_name)}</div>'
        ),
        *specification,
        "</td></tr>",
        (
            f'<tr><td style="padding:12px 20px;background:{_PAPER_2};{_MONO_PLAIN}font-size:15px;line-height:22px;'
            f'font-weight:500;color:{_INK};">{html.escape(price_words(item.verdict, item.calculated_price))}</td></tr>'
        ),
    ]
    if item.wish:
        lines.append(
            f'<tr><td style="padding:14px 20px 16px;border-top:1px solid {_RULE_2};">'
            f'<div style="{_LABEL}">Пожелание</div>'
            f'<div style="padding-top:4px;font-size:14px;line-height:20px;color:{_INK_2};">{html.escape(item.wish)}'
            "</div></td></tr>"
        )
    return lines


def _mirrors_section(inquiry: Inquiry) -> list[str]:
    """Render the section of mirrors, one card each, or the comment card of a contact-form inquiry."""
    if not inquiry.items:
        head = _section_label("02", "Комментарий")
        cards = _card(_comment_card(inquiry.comment))
    else:
        head = _section_label("02", _mirror_count_words(len(inquiry.items)))
        cards = [line for index, item in enumerate(inquiry.items, start=1) for line in _card(_item_card(index, item))]
    return [
        f'<tr><td style="padding:18px 32px 12px;border-top:1px solid {_RULE};">{head}</td></tr>',
        *cards,
    ]


def _footer(inquiry: Inquiry) -> str:
    """Render the legal-line footer of the storefront: the inquiry number, small and muted."""
    return (
        f'<tr><td style="padding:16px 32px 22px;border-top:1px solid {_RULE};{_MONO_PLAIN}font-size:11px;'
        f'line-height:16px;color:{_MUTED};">Заявка {inquiry.id}</td></tr>'
    )


def letter_subject(inquiry: Inquiry) -> str:
    """Name the client and the number of mirrors, so the manager tells inquiries apart in the list."""
    subject = f"Заявка от {inquiry.name}, {_phone_words(inquiry.phone)}"
    if inquiry.items:
        return f"{subject} · {_mirror_count_words(len(inquiry.items))}"
    return subject


def letter_html(inquiry: Inquiry) -> str:
    """Render the saved snapshot as the letter in the storefront's DNA: masthead, client, mirrors, footer."""
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
                f'font-family:{_BODY_FONT};color:{_INK};">'
            ),
            *_masthead(),
            *_client_block(inquiry),
            *_mirrors_section(inquiry),
            '<tr><td style="height:16px;font-size:0;line-height:0;">&nbsp;</td></tr>',
            _footer(inquiry),
            "</table>",
            "</td></tr>",
            "</table>",
            "</body>",
            "</html>",
        ]
    )
