import json

from artifacts import store
from crypto.envelopes import Identity, KMSUnavailable
from django.db import transaction
from django.utils import timezone
from jobs.models import Job
from records.validation import DomainError

from .canonical import authorizer, commit_item, source_active
from .models import IngestBatch, ItemReceipt, SourceVersion


def process(job):
    batch = IngestBatch.objects.select_related("source__device__owner", "evidence").get(
        pk=job.reference
    )
    if not source_active(batch.source):
        raise DomainError("source_revoked", 403)
    blob = batch.evidence
    identity = Identity(blob.owner_id, blob.kind, blob.object_id, blob.pk, 1)
    body = json.loads(store.read(blob, identity, authorizer(batch.source, identity)))
    retry = False
    for ordinal, item in enumerate(body["items"]):
        if (
            ItemReceipt.objects.filter(batch=batch, ordinal=ordinal)
            .exclude(outcome="retryable")
            .exists()
        ):
            continue
        record_id = revision_id = None
        reason = ""
        disposition = "none"
        try:
            outcome, record_id, revision_id = commit_item(batch.source, item, job)
            if revision_id:
                disposition = (
                    SourceVersion.objects.filter(revision_id=revision_id)
                    .values_list("disposition", flat=True)
                    .first()
                    or "clinical"
                )
            elif item.get("operation") == "tombstone" and outcome == "accepted":
                disposition = "deleted"
        except KMSUnavailable:
            outcome, reason = "retryable", "key_service_unavailable"
            retry = True
        except DomainError as error:
            if error.status == 503:
                outcome, reason = "retryable", error.code
                retry = True
            else:
                outcome, reason = "rejected", error.code
        except (ValueError, TypeError, KeyError):
            outcome, reason = "rejected", "invalid_item_schema"
        with transaction.atomic():
            lease = Job.objects.select_for_update().get(pk=job.pk)
            if lease.lease_token != job.lease_token or lease.lease_until <= timezone.now():
                raise DomainError("lease_lost", 503)
            ItemReceipt.objects.update_or_create(
                batch=batch,
                ordinal=ordinal,
                defaults={
                    "outcome": outcome,
                    "disposition": disposition,
                    "reason": reason,
                    "record_id": record_id,
                    "revision_id": revision_id,
                },
            )
    batch.state = "retryable" if retry else "processed"
    batch.save(update_fields=["state"])
    if retry:
        raise DomainError("batch_retryable", 503)
