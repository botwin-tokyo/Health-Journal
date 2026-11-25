"""The phone's public hostname exposes machine endpoints only."""

import re

from django.conf import settings
from django.http import JsonResponse

UPLOAD_PATH = re.compile(
    r"^(?:/api/v1/ingestion/(?:config|assets|batches(?:/[0-9a-f-]{36})?|commands/[0-9a-f-]{36}/ack)|/o/(?:token|revoke_token)/)$"
)


class UploadHostBoundaryMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        hostname = settings.HEALTH03_UPLOAD_HOST
        if hostname and request.get_host().split(":", 1)[0].lower() == hostname:
            if not UPLOAD_PATH.fullmatch(request.path):
                return self.denied()
            if request.headers.get("X-Forwarded-Proto") != "https":
                return self.denied(400, "https_required")
        return self.get_response(request)

    @staticmethod
    def denied(status=404, code="not_found"):
        response = JsonResponse({"code": code}, status=status)
        response["Cache-Control"] = "no-store, private"
        response["X-Content-Type-Options"] = "nosniff"
        return response
