import json

from access.policy import AccessDenied
from crypto.envelopes import KMSUnavailable
from django.http import JsonResponse, StreamingHttpResponse
from django.views.decorators.http import require_GET, require_POST

from . import tickets


@require_POST
def ticket(request, record_id):
    try:
        body = json.loads(request.body)
        secret = tickets.issue(request, record_id, body.get("action", "download_report"))
        return JsonResponse({"ticket": secret, "start_deadline_seconds": 60})
    except (AccessDenied, ValueError, AttributeError):
        return JsonResponse({"code": "not_found"}, status=404)


@require_GET
def content(request, record_id):
    if request.GET:
        return JsonResponse({"code": "invalid_download_request"}, status=400)
    try:
        chunks = tickets.content(request, record_id, request.headers.get("X-Download-Ticket", ""))
    except AccessDenied:
        return JsonResponse({"code": "not_found"}, status=404)
    except KMSUnavailable:
        response = JsonResponse({"code": "key_service_unavailable"}, status=503)
        response["Retry-After"] = "30"
        return response
    response = StreamingHttpResponse(chunks, content_type="application/pdf")
    response["Content-Disposition"] = 'attachment; filename="document.pdf"'
    response["Cache-Control"] = "no-store"
    return response
