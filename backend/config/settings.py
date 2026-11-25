"""Synthetic local environment. Production is deliberately gated until S03/S06."""

import os
import secrets
import tempfile
from pathlib import Path

from django.core.exceptions import ImproperlyConfigured

BASE_DIR = Path(__file__).resolve().parents[2]
ENVIRONMENT = os.environ.get("HEALTH03_ENV", "development")
if ENVIRONMENT not in {"development", "test", "production", "restore"}:
    raise ImproperlyConfigured("Unknown environment")


def local_secret():
    credentials = os.environ.get("CREDENTIALS_DIRECTORY")
    if credentials:
        value = (Path(credentials) / "django-secret").read_text().strip()
        if len(value) < 50:
            raise ImproperlyConfigured("Invalid local runtime credential")
        return value
    directory = BASE_DIR / ".local"
    directory.mkdir(mode=0o700, exist_ok=True)
    path = directory / "django-secret"
    if not path.exists():
        descriptor, temporary = tempfile.mkstemp(dir=directory)
        try:
            with os.fdopen(descriptor, "w") as output:
                output.write(secrets.token_urlsafe(64))
                output.flush()
                os.fsync(output.fileno())
            try:
                os.link(temporary, path)
            except FileExistsError:
                pass
        finally:
            os.unlink(temporary)
    secret = path.read_text().strip()
    if len(secret) < 50:
        raise ImproperlyConfigured("Local signing key is missing or incomplete")
    return secret


SECRET_KEY = (
    (os.environ.get("DJANGO_SECRET_KEY") or local_secret()) if ENVIRONMENT != "production" else ""
)
DEBUG = False
ALLOWED_HOSTS = ["localhost", "127.0.0.1", "api.health03.test", "testserver"]
HEALTH03_UPLOAD_HOST = os.environ.get("HEALTH03_UPLOAD_HOST", "").lower()
if HEALTH03_UPLOAD_HOST:
    import re

    if not re.fullmatch(r"[a-z0-9](?:[a-z0-9.-]*[a-z0-9])?", HEALTH03_UPLOAD_HOST):
        raise ImproperlyConfigured("Invalid upload hostname")
    ALLOWED_HOSTS.append(HEALTH03_UPLOAD_HOST)
ROOT_URLCONF = "config.urls"
WSGI_APPLICATION = "config.wsgi.application"
INSTALLED_APPS = [
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.sites",
    "corsheaders",
    "accounts.apps.AccountsConfig",
    "operations",
    "allauth",
    "allauth.account",
    "allauth.headless",
    "allauth.usersessions",
]
MIDDLEWARE = [
    "uploader.public_boundary.UploadHostBoundaryMiddleware",
    "django.middleware.security.SecurityMiddleware",
    "corsheaders.middleware.CorsMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "allauth.account.middleware.AccountMiddleware",
    "accounts.middleware.SecurityBoundaryMiddleware",
]
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": os.environ.get("PGDATABASE", "health03_dev"),
        "USER": os.environ.get("PGUSER") or os.environ.get("USER", "journal"),
        "HOST": os.environ.get("PGHOST", "/var/run/postgresql"),
        "PORT": os.environ.get("PGPORT", "5432"),
        "CONN_MAX_AGE": 60,
    }
}
AUTH_USER_MODEL = "accounts.Account"
AUTHENTICATION_BACKENDS = ["allauth.account.auth_backends.AuthenticationBackend"]
AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
        "OPTIONS": {"min_length": 12},
    },
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]
SITE_ID = 1
USE_TZ = True
TIME_ZONE = os.environ.get("JOURNAL_TIMEZONE") or "UTC"
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
SESSION_ENGINE = "django.contrib.sessions.backends.db"
SESSION_COOKIE_NAME = "__Host-health03_session"
SESSION_COOKIE_SECURE = True
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = "Lax"
SESSION_COOKIE_PATH = "/"
SESSION_COOKIE_DOMAIN = None
SESSION_COOKIE_AGE = 12 * 60 * 60
SESSION_SAVE_EVERY_REQUEST = False
CSRF_COOKIE_NAME = "__Host-health03_csrf"
CSRF_COOKIE_SECURE = True
CSRF_COOKIE_HTTPONLY = True
CSRF_FAILURE_VIEW = "accounts.views.csrf_failure"
FRONTEND_ORIGIN = os.environ.get("FRONTEND_ORIGIN", "https://dashboard.health03.test")
API_ORIGIN = os.environ.get("API_ORIGIN", "https://api.health03.test")
CORS_ALLOWED_ORIGINS = [FRONTEND_ORIGIN]
CORS_ALLOW_CREDENTIALS = True
CORS_EXPOSE_HEADERS = ["X-Permission-Epoch", "X-Request-ID"]
CSRF_TRUSTED_ORIGINS = [FRONTEND_ORIGIN]
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_REFERRER_POLICY = "no-referrer"
ACCOUNT_ADAPTER = "accounts.adapter.InvitationAccountAdapter"
ACCOUNT_USER_MODEL_USERNAME_FIELD = None
ACCOUNT_LOGIN_METHODS = {"email"}
ACCOUNT_SIGNUP_FIELDS = ["email*", "password1*", "password2*"]
ACCOUNT_EMAIL_VERIFICATION = "mandatory"
ACCOUNT_LOGIN_BY_CODE_ENABLED = False
ACCOUNT_LOGIN_ON_EMAIL_CONFIRMATION = False
ACCOUNT_LOGIN_ON_PASSWORD_RESET = False
ACCOUNT_SESSION_REMEMBER = False
ACCOUNT_REAUTHENTICATION_TIMEOUT = 300
ACCOUNT_PREVENT_ENUMERATION = True
HEADLESS_ONLY = True
HEADLESS_CLIENTS = ("browser",)
HEADLESS_FRONTEND_URLS = {
    "account_confirm_email": FRONTEND_ORIGIN + "/verify-email/{key}",
    "account_reset_password": FRONTEND_ORIGIN + "/reset-password",
    "account_reset_password_from_key": FRONTEND_ORIGIN + "/reset-password/{key}",
    "account_signup": FRONTEND_ORIGIN + "/enroll",
}
EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"
DEFAULT_FROM_EMAIL = "health03@example.invalid"
CACHES = {"default": {"BACKEND": "operations.cache.PostgresJSONCache", "LOCATION": "auth"}}
TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "APP_DIRS": True,
        "OPTIONS": {"context_processors": ["django.template.context_processors.request"]},
    }
]

ACCOUNT_RATE_LIMITS = {"enrollment": "10/m/ip"}
ACCOUNT_EMAIL_UNKNOWN_ACCOUNTS = False
PASSWORD_RESET_TIMEOUT = 3600

INSTALLED_APPS += ["oauth2_provider", "uploader", "access", "artifacts"]
UPLOADER_CLIENT_ID = "health03-android-synthetic"
UPLOADER_CALLBACK = API_ORIGIN + "/android/oauth/callback"
OAUTH2_PROVIDER = {
    "OAUTH2_VALIDATOR_CLASS": "uploader.validator.UploaderValidator",
    "OAUTH2_BACKEND_CLASS": "uploader.backend.UploaderCore",
    "SCOPES": {
        "ingest:write": "Upload this device's readings",
        "ingest:status": "Read this device's receipt metadata",
    },
    "DEFAULT_SCOPES": ["ingest:write", "ingest:status"],
    "PKCE_REQUIRED": True,
    "ROTATE_REFRESH_TOKEN": True,
    "REFRESH_TOKEN_REUSE_PROTECTION": True,
    "REFRESH_TOKEN_GRACE_PERIOD_SECONDS": 0,
    "REFRESH_TOKEN_EXPIRE_SECONDS": 30 * 86400,
    "ALLOW_URI_WILDCARDS": False,
    "ALLOWED_REDIRECT_URI_SCHEMES": ["https"],
    "ACCESS_TOKEN_EXPIRE_SECONDS": 300,
    "AUTHORIZATION_CODE_EXPIRE_SECONDS": 60,
    "OIDC_ENABLED": False,
    "OIDC_ISS_ENDPOINT": API_ORIGIN,
    "DCR_ENABLED": False,
    "CIMD_ENABLED": False,
    **{
        ("COMPLIANT_BCP_RFC9700_" + flag): True
        for flag in [
            "IMPLICIT_GRANT",
            "PASSWORD_GRANT",
            "PKCE_METHOD",
            "ACCESS_TOKEN_TRANSPORT",
            "AUTHZ_RESPONSE_ISS",
            "TOKEN_STORAGE",
            "REFRESH_TOKEN",
            "REDIRECT_URI_SCHEME",
            "REDIRECT_URI_MATCHING",
            "PKCE_REQUIRED",
        ]
    },
}
ACCOUNT_RATE_LIMITS.update({"native_authorization": "20/m/ip", "native_token": "60/m/ip"})

OAUTH2_PROVIDER_APPLICATION_MODEL = "oauth2_provider.Application"
OAUTH2_PROVIDER_GRANT_MODEL = "oauth2_provider.Grant"
OAUTH2_PROVIDER_ACCESS_TOKEN_MODEL = "oauth2_provider.AccessToken"
OAUTH2_PROVIDER_REFRESH_TOKEN_MODEL = "oauth2_provider.RefreshToken"

DATA_UPLOAD_MAX_MEMORY_SIZE = 25 * 1024 * 1024
FILE_UPLOAD_MAX_MEMORY_SIZE = 0
DATA_UPLOAD_MAX_NUMBER_FIELDS = 1000
DATA_UPLOAD_MAX_NUMBER_FILES = 1
# Validate the upload host before the general boundary strips forwarding headers.
MIDDLEWARE.insert(1, "operations.http.BoundaryMiddleware")
CORS_ALLOW_HEADERS = [
    "accept",
    "content-type",
    "x-csrftoken",
    "if-match",
    "idempotency-key",
    "x-download-ticket",
    "range",
    "x-email-verification-key",
    "x-password-reset-key",
]
CORS_EXPOSE_HEADERS = [
    "ETag",
    "X-Permission-Epoch",
    "Retry-After",
    "X-Request-ID",
    "Content-Range",
    "Accept-Ranges",
    "Content-Length",
]
ACCOUNT_RATE_LIMITS.update(
    {
        "login": "10/m/ip",
        "login_failed": "5/m/key,10/m/ip,30/h/key",
        "reauthenticate": "10/m/ip,30/h/user",
        "reset_password": "10/m/ip,5/15m/key",
        "reset_password_from_key": "5/15m/ip",
    }
)
HEALTH03_BLOB_FILE_MODE = 0o640 if os.environ.get("HEALTH03_SHARED_BLOBS") == "1" else 0o600
HEALTH03_BLOB_ROOT = Path(os.environ.get("HEALTH03_BLOB_ROOT", str(BASE_DIR / ".local/blobs")))
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {"metadata": {"()": "operations.http.MetadataFormatter"}},
    "handlers": {
        "metadata": {"class": "logging.StreamHandler", "formatter": "metadata"},
        "discard": {"class": "logging.NullHandler"},
    },
    "loggers": {
        "health03.requests": {"handlers": ["metadata"], "level": "INFO", "propagate": False},
        "django.request": {"handlers": ["discard"], "propagate": False},
        "django.security": {"handlers": ["discard"], "propagate": False},
    },
}
HEALTH03_BACKUPS_ENABLED = os.environ.get("HEALTH03_BACKUPS_ENABLED", "0") == "1"

HEALTH03_LOCAL_DESKTOP = os.environ.get("HEALTH03_LOCAL_DESKTOP") == "1"
if HEALTH03_LOCAL_DESKTOP and ENVIRONMENT != "development":
    raise RuntimeError("Local desktop access is development-only")

if ENVIRONMENT == "production":
    from .production import configure

    configure(globals())

INSTALLED_APPS += ["records", "jobs"]

INSTALLED_APPS += ["ingest"]

INSTALLED_APPS += ["labs"]

INSTALLED_APPS += ["breathing"]

INSTALLED_APPS += ["metrics"]

INSTALLED_APPS += ["journal"]

INSTALLED_APPS += ["reports"]

# Dual source-identity indexes can be populated before a lookup-key migration.
# Legacy transport receipts/tombstones continue to require v1; retirement is blocked.
HEALTH03_SOURCE_LOOKUP_VERSIONS = tuple(
    int(value) for value in os.environ.get("HEALTH03_SOURCE_LOOKUP_VERSIONS", "1").split(",")
)

HEALTH03_DEPLOYED_REVISION = os.environ.get("HEALTH03_DEPLOYED_REVISION", "development")
