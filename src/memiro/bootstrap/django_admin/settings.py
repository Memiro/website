"""The settings module Django loads for the admin process (§11.1).

The assembly itself is a plain function of ``Config``; this module is only the
place where the process reads its TOML and lets Django see the result under
the module-level names the framework expects.
"""

from memiro.bootstrap.config_loader import Config
from memiro.bootstrap.django_admin.assembly import admin_settings

globals().update(admin_settings(Config.load()))
