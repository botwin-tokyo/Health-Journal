"""Production configuration loaded only with explicit operator inputs."""

import json
import os
from pathlib import Path
from urllib.parse import urlsplit

from django.core.exceptions import ImproperlyConfigured


def required(name):
    value = os.environ.get(name)
    if not value:
        raise ImproperlyConfigured("Missing deployment input: " + name)
    return value


def credential(name):
    path = Path(required("CREDENTIALS_DIRECTORY")) / name
    value = path.read_text().strip()
    if not value:
        raise ImproperlyConfigured("Empty credential: " + name)
    return value


def origin(name):
    value = required(name)
    parsed = urlsplit(value)
    if (
        parsed.scheme != "https"
        or not parsed.hostname
        or parsed.username
        or parsed.password
        or parsed.port not in (None, 443)
        or parsed.path
        or parsed.query
        or parsed.fragment
        or parsed.hostname.endswith((".test", ".invalid", ".localhost", ".example"))
    ):
        raise ImproperlyConfigured("Invalid deployment origin: " + name)
    return value


def configure(values):
    appliance = os.environ.get("HEALTH03_PI_APPLIANCE") == "1"
    upload_host = values["HEALTH03_UPLOAD_HOST"]
    if appliance:
        frontend, api = required("FRONTEND_ORIGIN"), required("API_ORIGIN")
        if (frontend, api) != ("https://localhost:5173", "https://localhost:8443"):
            raise ImproperlyConfigured("Pi dashboard requires the trusted loopback origins")
        if not upload_host or upload_host in {"localhost", "127.0.0.1"}:
            raise ImproperlyConfigured("Pi appliance requires a separate phone hostname")
        if required("PGUSER") == "health03-app":
            values["LOCAL_PROXY_SECRET"] = credential("desktop-proxy-secret")
            if values["LOCAL_PROXY_SECRET"] == credential("tunnel-origin-secret"):
                raise ImproperlyConfigured("Desktop and tunnel credentials must be distinct")
            values["HEALTH03_LOCAL_DESKTOP"] = True
    else:
        frontend, api = origin("FRONTEND_ORIGIN"), origin("API_ORIGIN")
    api_host = urlsplit(api).hostname
    if required("API_HOSTNAME") != api_host:
        raise ImproperlyConfigured("API hostname does not match origin")
    if urlsplit(frontend).hostname.split(".")[1:] != api_host.split(".")[1:]:
        raise ImproperlyConfigured("Dashboard/API must use sibling same-site hostnames")
    evidence = json.loads(Path(required("HEALTH03_RELEASE_GATE")).read_text())
    if (
        evidence.get("release_id") != required("HEALTH03_RELEASE_ID")
        or evidence.get("production_allowed") is not True
        or evidence.get("commit") != required("HEALTH03_DEPLOYED_REVISION")
    ):
        raise ImproperlyConfigured("Release evidence has not authorized production")
    deployment_files = ["KMS_CA_FILE"]
    if values.get("HEALTH03_BACKUPS_ENABLED"):
        deployment_files.extend(["BACKUP_TARGET_CONFIG", "RECOVERY_LOCATIONS_FILE"])
    for key in deployment_files:
        if not Path(required(key)).is_file():
            raise ImproperlyConfigured("Missing deployment file: " + key)
    secret = credential("django-secret")
    if len(secret) < 50:
        raise ImproperlyConfigured("Invalid Django signing secret")
    values.update(
        SECRET_KEY=secret,
        DEBUG=False,
        FRONTEND_ORIGIN=frontend,
        API_ORIGIN=api,
        ALLOWED_HOSTS=list(dict.fromkeys(filter(None, [api_host, upload_host]))),
        HEALTH03_BLOB_FILE_MODE=0o640,
        CORS_ALLOWED_ORIGINS=[frontend],
        CSRF_TRUSTED_ORIGINS=[frontend],
        SECURE_SSL_REDIRECT=True,
        SECURE_HSTS_SECONDS=86400,
        SECURE_HSTS_INCLUDE_SUBDOMAINS=False,
        SECURE_HSTS_PRELOAD=False,
        SECURE_PROXY_SSL_HEADER=("HTTP_X_FORWARDED_PROTO", "https"),
        EMAIL_BACKEND="django.core.mail.backends.smtp.EmailBackend",
        EMAIL_HOST=required("SMTP_HOST"),
        EMAIL_PORT=int(required("SMTP_PORT")),
        EMAIL_USE_TLS=True,
        EMAIL_HOST_USER=required("SMTP_USER"),
        EMAIL_HOST_PASSWORD=credential("smtp-password"),
        EMAIL_TIMEOUT=15,
        DEFAULT_FROM_EMAIL=required("SMTP_FROM"),
        TRUSTED_TUNNEL_SECRET=credential("tunnel-origin-secret"),
        HEALTH03_BLOB_ROOT=Path("/var/lib/health03/blobs"),
        UPLOADER_CLIENT_ID=required("ANDROID_CLIENT_ID"),
    )
    values["DATABASES"]["default"].update(
        NAME=required("PGDATABASE"), USER=required("PGUSER"), HOST="/var/run/postgresql"
    )
    values["HEADLESS_FRONTEND_URLS"] = {
        key: value.replace("https://dashboard.health03.test", frontend)
        for key, value in values["HEADLESS_FRONTEND_URLS"].items()
    }
    values["UPLOADER_CALLBACK"] = api + "/android/oauth/callback"
    values["OAUTH2_PROVIDER"]["OIDC_ISS_ENDPOINT"] = api
