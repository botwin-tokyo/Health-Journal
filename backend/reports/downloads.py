from access.policy import AccessDenied, AuthorizationContext
from artifacts import tickets
from artifacts.models import SecurityJob
from artifacts.selectors import select
from django.http import StreamingHttpResponse
from django.utils import timezone
from records.http import endpoint
from records.validation import DomainError, parse_json

from .models import ExportBundle, ExportPart


def resolve(request, identifier, part_id=None):
    context = AuthorizationContext(request)
    bundle = ExportBundle.objects.filter(pk=identifier).first()
    if bundle:
        user, owner, grant = context.current()
        if not owner or bundle.owner_id != owner.pk or user.pk != owner.pk or grant:
            raise AccessDenied()
        if bundle.state != "ready" or bundle.expires_at <= timezone.now():
            raise DomainError("export_not_ready", 409)
        part = ExportPart.objects.filter(bundle=bundle, pk=part_id).first()
        if not part:
            raise AccessDenied()
        blob = part.blob
    else:
        job = SecurityJob.objects.filter(
            pk=identifier, state="ready", purpose="render_report", expires_at__gt=timezone.now()
        ).first()
        if not job or (part_id and str(part_id) != str(job.output_record_id)):
            raise AccessDenied()
        blob = job.output_record
    select(context, blob.pk, "download_report")
    return blob


@endpoint({"POST"})
def ticket(request, export_id):
    body = parse_json(request.body)
    blob = resolve(request, export_id, body.get("part_id"))
    secret = tickets.issue(request, blob.pk, "download_report")
    return {
        "ticket": secret,
        "part_id": str(body.get("part_id") or blob.pk),
        "start_deadline_seconds": 60,
    }


@endpoint({"GET"})
def content(request, export_id):
    if set(request.GET) - {"part_id"}:
        raise DomainError("invalid_download_request", 400)
    blob = resolve(request, export_id, request.GET.get("part_id"))
    chunks = tickets.content(request, blob.pk, request.headers.get("X-Download-Ticket", ""))
    response = StreamingHttpResponse(chunks, content_type=blob.mime_type)
    extension = {"application/pdf": "pdf", "application/json": "json", "text/csv": "csv"}.get(
        blob.mime_type, "bin"
    )
    response["Content-Disposition"] = 'attachment; filename="health-export.' + extension + '"'
    return response
