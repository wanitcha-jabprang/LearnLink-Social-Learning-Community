
"""
Django settings for config project.
"""

import os
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent

load_dotenv(BASE_DIR.parent / ".env")

IS_RAILWAY = bool(
    os.getenv("RAILWAY_ENVIRONMENT_ID")
    or os.getenv("RAILWAY_ENVIRONMENT_NAME")
)

# ==================================================
# Core Security
# ==================================================

SECRET_KEY = os.getenv("SECRET_KEY")

DEBUG = not IS_RAILWAY and (
    os.getenv("DEBUG", "False").strip().lower()
    in ("true", "1", "yes")
)

ALLOWED_HOSTS = [
    host.strip()
    for host in os.getenv(
        "ALLOWED_HOSTS",
        "localhost,127.0.0.1,web,.trycloudflare.com,"
        "learnlink-social-learning-community-production.up.railway.app",
    ).split(",")
    if host.strip()
]

CSRF_TRUSTED_ORIGINS = [
    origin.strip()
    for origin in os.getenv(
        "CSRF_TRUSTED_ORIGINS",
        "https://*.trycloudflare.com,"
        "https://learnlink-social-learning-community-production.up.railway.app",
    ).split(",")
    if origin.strip()
]


# ==================================================
# Application Definition
# ==================================================

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "users.apps.UsersConfig",
    "feed.apps.FeedConfig",
    "community.apps.CommunityConfig",
    "post.apps.PostConfig",
    "core.apps.CoreConfig",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "core.security_middleware.SecurityHeadersMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "core.middleware.AuditLogMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"


# ==================================================
# Database
# ==================================================

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.mysql",
        "NAME": os.getenv("DB_NAME"),
        "USER": os.getenv("DB_USER"),
        "PASSWORD": os.getenv("DB_PASSWORD"),
        "HOST": os.getenv("DB_HOST") or "localhost",
        "PORT": os.getenv("DB_PORT") or "3306",
        "OPTIONS": {"charset": "utf8mb4"},
    }
}

CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
        "LOCATION": "learnlink-default-cache",
    }
}


# ==================================================
# Password Validation
# ==================================================

AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": (
            "django.contrib.auth.password_validation."
            "UserAttributeSimilarityValidator"
        ),
    },
    {
        "NAME": (
            "django.contrib.auth.password_validation.MinimumLengthValidator"
        ),
    },
    {
        "NAME": (
            "django.contrib.auth.password_validation.CommonPasswordValidator"
        ),
    },
    {
        "NAME": (
            "django.contrib.auth.password_validation.NumericPasswordValidator"
        ),
    },
]

PASSWORD_HASHERS = [
    "django.contrib.auth.hashers.Argon2PasswordHasher",
    "django.contrib.auth.hashers.PBKDF2PasswordHasher",
]


# ==================================================
# Internationalization
# ==================================================

LANGUAGE_CODE = "th"

TIME_ZONE = "Asia/Bangkok"

USE_I18N = True

USE_TZ = True


# ==================================================
# Static and Media Files
# ==================================================

STATIC_URL = "static/"

STATICFILES_DIRS = [
    BASE_DIR / "static",
]

STATIC_ROOT = BASE_DIR / "staticfiles"

MEDIA_URL = "/media/"

MEDIA_ROOT = BASE_DIR / "media"

DATA_UPLOAD_MAX_MEMORY_SIZE = 120 * 1024 * 1024

FILE_UPLOAD_MAX_MEMORY_SIZE = 10 * 1024 * 1024


# ==================================================
# Email
# ==================================================

MAILERS = {
    "default": {
        "BACKEND": "django.core.mail.backends.console.EmailBackend",
    },
}


# ==================================================
# Custom User Model
# ==================================================

AUTH_USER_MODEL = "users.User"

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "audit": {
            "format": "{asctime} {levelname} {name} {message}",
            "style": "{",
        },
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "audit",
        },
    },
    "loggers": {
        "core.audit": {
            "handlers": ["console"],
            "level": "INFO",
            "propagate": False,
        },
    },
}


# ==================================================
# Security Headers
# ==================================================

SECURE_CONTENT_TYPE_NOSNIFF = True

SECURE_REFERRER_POLICY = "strict-origin-when-cross-origin"

X_FRAME_OPTIONS = "DENY"


# ==================================================
# Cookie Security
# ==================================================

SESSION_COOKIE_HTTPONLY = True

SESSION_COOKIE_SAMESITE = "Lax"

CSRF_COOKIE_HTTPONLY = True

CSRF_COOKIE_SAMESITE = "Lax"

SESSION_COOKIE_SECURE = not DEBUG

CSRF_COOKIE_SECURE = not DEBUG


# ==================================================
# HTTPS / Railway Proxy / HSTS
# ==================================================

# Railway terminates HTTPS and forwards the original scheme to Django.
SECURE_PROXY_SSL_HEADER = (
    "HTTP_X_FORWARDED_PROTO",
    "https",
)

# Enable only when the proxy forwards the original HTTPS scheme.
SECURE_SSL_REDIRECT = (
    os.getenv("SECURE_SSL_REDIRECT", "False").strip().lower()
    == "true"
)

ENABLE_HSTS = IS_RAILWAY or (
    os.getenv("ENABLE_HSTS", "False").strip().lower() == "true"
)

SECURE_HSTS_SECONDS = (
    31536000 if ENABLE_HSTS and not DEBUG else 0
)

SECURE_HSTS_INCLUDE_SUBDOMAINS = False

SECURE_HSTS_PRELOAD = False

WHITENOISE_ALLOW_ALL_ORIGINS = False
