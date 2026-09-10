"""Reading a delivered manager email the way the manager's client would."""

from email.message import EmailMessage


def text_half(message: EmailMessage) -> str:
    """Read the plain-text part the manager's client falls back to."""
    text = message.get_body(preferencelist=("plain",))
    assert text is not None
    return str(text.get_content())
