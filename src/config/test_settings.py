from .settings import *

SECRET_KEY = "test-only-key"
DEBUG = True
ALLOWED_HOSTS = ["testserver", "localhost"]
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": ":memory:",
    }
}
AUTH_PASSWORD_VALIDATORS = []
