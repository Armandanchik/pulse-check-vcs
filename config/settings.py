"""
Django settings for Pulse Check VCS.

Locally everything works with the defaults below (SQLite, DEBUG on).
On a server, set the environment variables listed in .env.example.
On Vercel, see DEPLOY.md: the database comes from the Supabase integration.
"""

import os
import urllib.parse
from pathlib import Path

import dj_database_url
from django.core.exceptions import ImproperlyConfigured

BASE_DIR = Path(__file__).resolve().parent.parent

# Vercel sets VERCEL=1 in builds and functions.
ON_VERCEL = os.environ.get("VERCEL") == "1"

DEBUG = os.environ.get("DJANGO_DEBUG", "0" if ON_VERCEL else "1") == "1"

SECRET_KEY = os.environ.get("DJANGO_SECRET_KEY", "")
if not SECRET_KEY:
    if not DEBUG:
        raise ImproperlyConfigured("Set DJANGO_SECRET_KEY when DJANGO_DEBUG=0.")
    SECRET_KEY = "django-insecure-local-development-only"

# Public address of the site, used to build the student links shown in the admin.
_vercel_production_host = os.environ.get("VERCEL_PROJECT_PRODUCTION_URL", "")
PUBLIC_BASE_URL = os.environ.get(
    "PUBLIC_BASE_URL",
    f"https://{_vercel_production_host}" if _vercel_production_host else "http://localhost:8000",
).rstrip("/")

ALLOWED_HOSTS = os.environ.get("DJANGO_ALLOWED_HOSTS", "localhost,127.0.0.1").split(",")
ALLOWED_HOSTS += [host for host in (_vercel_production_host, os.environ.get("VERCEL_URL", "")) if host]
CSRF_TRUSTED_ORIGINS = [PUBLIC_BASE_URL]
if os.environ.get("VERCEL_URL"):
    CSRF_TRUSTED_ORIGINS.append(f"https://{os.environ['VERCEL_URL']}")

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'feedback',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'config.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'config.wsgi.application'


def database_config():
    """SQLite locally; PostgreSQL from DATABASE_URL (Docker) or POSTGRES_URL (Vercel + Supabase)."""
    url = os.environ.get("DATABASE_URL") or os.environ.get("POSTGRES_URL")
    if not url:
        return dj_database_url.parse(f"sqlite:///{BASE_DIR / 'db.sqlite3'}")
    # Supabase URLs can carry extra query parameters (e.g. "supa=...") that psycopg rejects.
    parts = urllib.parse.urlsplit(url)
    query = [(key, value) for key, value in urllib.parse.parse_qsl(parts.query) if key == "sslmode"]
    url = urllib.parse.urlunsplit(parts._replace(query=urllib.parse.urlencode(query)))
    if not ON_VERCEL:
        return dj_database_url.parse(url, conn_max_age=600)
    # Serverless functions connect through Supabase's transaction pooler:
    # no persistent connections and no server-side cursors.
    config = dj_database_url.parse(url, conn_max_age=0, ssl_require=True)
    config["DISABLE_SERVER_SIDE_CURSORS"] = True
    return config


DATABASES = {"default": database_config()}

AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

LANGUAGE_CODE = 'lt'
TIME_ZONE = 'Europe/Vilnius'
USE_I18N = True
USE_TZ = True

STATIC_URL = 'static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'
STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {
        "BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"
        if DEBUG
        else "whitenoise.storage.CompressedManifestStaticFilesStorage"
    },
}

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

if not DEBUG:
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True

# --- Pulse Check ---
# Results for a session/module are hidden until it has at least this many responses.
PULSE_MIN_RESPONSES = 3
# A finished module raises an alert if any 1–5 average is below this...
PULSE_ALERT_MIN_AVERAGE = 3.5
# ...or if at least this share of pace answers is "too slow" or "too fast".
PULSE_ALERT_PACE_SHARE = 0.4
