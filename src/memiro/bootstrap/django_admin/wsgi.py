from django.core.handlers.wsgi import WSGIHandler
from django.core.wsgi import get_wsgi_application

from memiro.bootstrap.django_admin.setup import announce_settings

announce_settings()

# gunicorn imports this module and serves the callable it finds here.
application: WSGIHandler = get_wsgi_application()
