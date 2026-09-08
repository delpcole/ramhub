"""
Settings shared by every environment.

Environment-specific modules (dev.py, prod.py) import * from here and override.
Never put a secret or a connection string in this file — read it from the
environment via django-environ.
"""

from pathlib import Path

import environ

# config/settings/base.py -> config/settings -> config -> repo root
BASE_DIR = Path(__file__).resolve().parent.parent.parent

env = environ.Env()
environ.Env.read_env(BASE_DIR / ".env")

# --------------------------------------------------------------------------
# Core
# --------------------------------------------------------------------------
# `or` (not just a default) so a blank SECRET_KEY= line in .env still boots.
SECRET_KEY = env.str("SECRET_KEY", default="") or "django-insecure-dev-only-change-me"
DEBUG = env.bool("DEBUG", default=False)
ALLOWED_HOSTS = env.list("ALLOWED_HOSTS", default=["localhost", "127.0.0.1"])

# RamHub: only email addresses at this domain may register (enforced in Phase 2).
COLLEGE_EMAIL_DOMAIN = env.str("COLLEGE_EMAIL_DOMAIN", default="farmingdale.edu")

# --------------------------------------------------------------------------
# Applications
# --------------------------------------------------------------------------
INSTALLED_APPS = [
    # Must be installed so its makemigrations/migrate overrides (which use the
    # MongoDB-aware MigrationAutodetector) take effect.
    "django_mongodb_backend",
    # Subclassed to use ObjectIdAutoField — see config/mongo_apps.py.
    "config.mongo_apps.MongoAdminConfig",
    "config.mongo_apps.MongoAuthConfig",
    "config.mongo_apps.MongoContentTypesConfig",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    # Third party
    "rest_framework",
    # RamHub
    "apps.accounts",
    "apps.catalog",
    "apps.ratings",
    "apps.community",
    "apps.campus",
    "apps.saved",
    "apps.assistant",
    "apps.moderation",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"
WSGI_APPLICATION = "config.wsgi.application"
ASGI_APPLICATION = "config.asgi.application"

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
                "config.context_processors.navigation",
            ],
        },
    },
]

# --------------------------------------------------------------------------
# Database — MongoDB via django-mongodb-backend
# --------------------------------------------------------------------------
# In django-mongodb-backend 6.1 the whole connection string is the HOST value.
# (The parse_uri() helper that older tutorials use was removed — do not add it.)
DATABASES = {
    "default": {
        "ENGINE": "django_mongodb_backend",
        "HOST": env.str("MONGODB_URI"),
        "NAME": env.str("MONGODB_NAME", default="ramhub"),
    }
}

# Keeps embedded models (which have no collection of their own) out of migrate
# and dumpdata.
DATABASE_ROUTERS = ["django_mongodb_backend.routers.MongoRouter"]

# MongoDB has no AutoField. Every model gets an ObjectId primary key.
DEFAULT_AUTO_FIELD = "django_mongodb_backend.fields.ObjectIdAutoField"

# --------------------------------------------------------------------------
# Auth
# --------------------------------------------------------------------------
AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

# --------------------------------------------------------------------------
# Django REST Framework
# --------------------------------------------------------------------------
REST_FRAMEWORK = {
    # Locked down by default; a view must opt out deliberately.
    "DEFAULT_PERMISSION_CLASSES": ["rest_framework.permissions.IsAuthenticated"],
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "rest_framework.authentication.SessionAuthentication",
    ],
    "DEFAULT_RENDERER_CLASSES": ["rest_framework.renderers.JSONRenderer"],
    "DEFAULT_PAGINATION_CLASS": "rest_framework.pagination.PageNumberPagination",
    "PAGE_SIZE": 25,
}

# --------------------------------------------------------------------------
# I18N / static
# --------------------------------------------------------------------------
LANGUAGE_CODE = "en-us"
TIME_ZONE = "America/New_York"
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
STATICFILES_DIRS = [BASE_DIR / "static"]
STATIC_ROOT = BASE_DIR / "staticfiles"
