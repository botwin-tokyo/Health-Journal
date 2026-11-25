"""Request limits, authenticated tunnel forwarding and metadata-only logging."""

import hmac
import ipaddress
import logging
import time
import uuid

from django.conf import settings
from django.http import JsonResponse

log = logging.getLogger("health03.requests")


class BoundaryMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        started = time.monotonic()
        request.health03_request_id = str(uuid.uuid4())
        supplied = request.META.pop("HTTP_X_HEALTH03_ORIGIN", "")
        expected = getattr(settings, "TRUSTED_TUNNEL_SECRET", "")
        desktop_secret = getattr(settings, "LOCAL_PROXY_SECRET", "")
        desktop_header = request.META.pop("HTTP_X_HEALTH03_DESKTOP", "")
        request.trusted_desktop = bool(
            desktop_secret
            and request.get_host() == "localhost:8443"
            and request.META.get("REMOTE_ADDR") == "127.0.0.1"
            and hmac.compare_digest(desktop_header.encode(), desktop_secret.encode())
        )
        if request.trusted_desktop:
            request.META["HTTP_X_FORWARDED_PROTO"] = "https"
        elif desktop_secret and request.get_host() == "localhost:8443":
            return self.reject("ingress_denied", 403)
        elif expected:
            if request.META.get("REMOTE_ADDR") not in {
                "127.0.0.1",
                "::1",
            } or not hmac.compare_digest(supplied.encode(), expected.encode()):
                return self.reject("ingress_denied", 403)
            try:
                remote = str(ipaddress.ip_address(request.META.get("HTTP_CF_CONNECTING_IP", "")))
            except ValueError:
                return self.reject("ingress_denied", 403)
            if request.META.get("HTTP_X_FORWARDED_PROTO") != "https":
                return self.reject("https_required", 400)
            request.META["REMOTE_ADDR"] = remote
        else:
            request.META.pop("HTTP_X_FORWARDED_PROTO", None)
        for key in (
            "HTTP_X_FORWARDED_FOR",
            "HTTP_FORWARDED",
            "HTTP_CF_CONNECTING_IP",
            "HTTP_X_FORWARDED_HOST",
        ):
            request.META.pop(key, None)
        if request.headers.get("Content-Encoding", "identity").lower() != "identity":
            return self.reject("compressed_body_not_supported", 415)
        try:
            length = int(request.META.get("CONTENT_LENGTH") or 0)
            if length < 0:
                raise ValueError
        except ValueError:
            return self.reject("invalid_body_length", 400)
        limit = (
            25 * 1024 * 1024
            if (
                request.content_type == "application/pdf"
                or request.path == "/api/v1/ingestion/assets"
            )
            else 5 * 1024 * 1024
        )
        if length > limit:
            return self.reject("body_too_large", 413)
        response = self.get_response(request)
        response["X-Request-ID"] = request.health03_request_id
        response["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
        response["Cross-Origin-Opener-Policy"] = "same-origin"
        response["Content-Security-Policy"] = (
            "default-src 'none'; form-action 'self'; base-uri 'none'; frame-ancestors 'none'"
        )
        match = getattr(request, "resolver_match", None)
        log.info(
            "request",
            extra={
                "route_name": match.url_name if match else "unmatched",
                "request_id": request.health03_request_id,
                "status": response.status_code,
                "duration_ms": round((time.monotonic() - started) * 1000),
            },
        )
        return response

    @staticmethod
    def reject(code, status):
        response = JsonResponse({"code": code}, status=status)
        response["Cache-Control"] = "no-store"
        return response


class MetadataFormatter(logging.Formatter):
    def format(self, record):
        import json

        return json.dumps(
            {
                "event": "request",
                "route": getattr(record, "route_name", None),
                "request_id": getattr(record, "request_id", None),
                "status": getattr(record, "status", None),
                "duration_ms": getattr(record, "duration_ms", None),
            },
            separators=(",", ":"),
        )
