import smtplib
from collections.abc import Callable

from memiro.adapters.smtp.client import smtp_client
from memiro.adapters.smtp.config import EmailConfig

type Login = Callable[[EmailConfig], None]


def smtp_login(config: EmailConfig) -> None:
    """Log in to the configured SMTP host and hang up without sending anything."""
    with smtp_client(config) as client:
        client.login(config.username, config.password)


def check_login(config: EmailConfig, login: Login = smtp_login) -> str:
    """Report "OK" or the host's refusal in its own words, so a wrong password surfaces before the first inquiry."""
    try:
        login(config)
    except smtplib.SMTPResponseException as error:
        reply = error.smtp_error
        words = reply.decode(errors="replace") if isinstance(reply, bytes) else reply
        return f"{error.smtp_code} {words}"
    except (smtplib.SMTPException, OSError) as error:
        return str(error)
    return "OK"
