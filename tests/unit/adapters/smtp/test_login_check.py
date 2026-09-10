import smtplib

from memiro.adapters.smtp.config import EmailConfig
from memiro.adapters.smtp.login_check import check_login

_CONFIG = EmailConfig(username="site@example.test", password="app-password")


def _accepting_login(_config: EmailConfig) -> None:
    """Stand in for a host that accepts the credentials."""


def _refusing_login(_config: EmailConfig) -> None:
    """Stand in for Yandex refusing an account password where an app password is required."""
    raise smtplib.SMTPAuthenticationError(535, b"5.7.8 Error: authentication failed")


def _unreachable_login(_config: EmailConfig) -> None:
    """Stand in for a host the server cannot reach at all."""
    msg = "[Errno 111] Connection refused"
    raise ConnectionRefusedError(msg)


def test_accepted_credentials_report_ok() -> None:
    """A login the host accepts is reported as the single word OK."""
    verdict = check_login(_CONFIG, login=_accepting_login)

    assert verdict == "OK"


def test_refused_credentials_report_the_server_reply() -> None:
    """A login the host refuses is reported by the host's own code and words."""
    verdict = check_login(_CONFIG, login=_refusing_login)

    assert verdict == "535 5.7.8 Error: authentication failed"


def test_an_unreachable_host_is_reported_in_words() -> None:
    """A host that cannot be reached is reported by the failure's own words, not by a traceback."""
    verdict = check_login(_CONFIG, login=_unreachable_login)

    assert verdict == "[Errno 111] Connection refused"
