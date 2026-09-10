from pathlib import Path

from memiro.bootstrap.config_loader import Config

_SECTIONS_WITHOUT_EMAIL = """
[db]
host = "localhost"
port = 5432
user = "memiro"
password = "memiro"
database = "memiro"

[observability]
enabled = false

[legal]
consent_version = "2026-08-31"

[media]
root = "media"
"""


def _config_file(directory: Path, email_section: str) -> Path:
    """Write a complete TOML config with the given ``[email]`` section next to the secret."""
    path = directory / "config.toml"
    path.write_text(_SECTIONS_WITHOUT_EMAIL + email_section, encoding="utf-8")
    return path


def test_the_smtp_password_is_read_from_the_file_named_next_to_the_config(tmp_path: Path) -> None:
    """A relative ``password_file`` resolves against the config's own directory and its line is stripped."""
    (tmp_path / "smtp_password").write_text("  app-password\n", encoding="utf-8")
    path = _config_file(tmp_path, '[email]\npassword_file = "smtp_password"\n')

    config = Config.from_file(path)

    assert config.email.password == "app-password"


def test_a_missing_password_file_leaves_the_password_empty(tmp_path: Path) -> None:
    """A ``password_file`` that does not exist yet yields an empty password, so one config serves every contour."""
    path = _config_file(tmp_path, '[email]\npassword_file = "smtp_password"\n')

    config = Config.from_file(path)

    assert config.email.password == ""
    assert config.email.password_file == "smtp_password"
