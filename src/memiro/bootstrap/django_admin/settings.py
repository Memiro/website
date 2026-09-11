"""The settings module Django loads for the admin process (§11.1).

The assembly itself is a plain function of ``Config``; this module is only the
place where the process reads its TOML and lets Django see the result under
the module-level names the framework expects.
"""

from memiro.bootstrap.config_loader import Config
from memiro.bootstrap.django_admin.assembly import admin_settings
from memiro_common.observability.logs import setup_logging

_config = Config.load()

# The admin logs through the same JSON chain as the API. Without this call the
# process keeps Django's defaults, where the console handler is filtered by
# ``require_debug_true`` and the only other handler mails ADMINS: with
# ``DEBUG`` off and no ADMINS, a 500 leaves no trace at all.
setup_logging(level=_config.observability.log_level)

globals().update(admin_settings(_config))
