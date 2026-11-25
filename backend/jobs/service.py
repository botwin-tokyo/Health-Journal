import uuid
from datetime import timedelta

from django.db import transaction
from django.utils import timezone

from .models import Job


def enqueue(kind, reference, version):
    return Job.objects.get_or_create(
        deduplication_key=f"{kind}:{reference}:{version}",
        defaults={"kind": kind, "reference": reference},
    )[0]


@transaction.atomic
def claim():
    now = timezone.now()
    Job.objects.filter(state="running", lease_until__lte=now, attempts__lt=5).update(
        state="queued", available_at=now
    )
    Job.objects.filter(state="running", lease_until__lte=now, attempts__gte=5).update(
        state="failed", error_code="lease_exhausted"
    )
    job = (
        Job.objects.select_for_update(skip_locked=True)
        .filter(state="queued", available_at__lte=now, attempts__lt=5)
        .order_by("available_at", "id")
        .first()
    )
    if job:
        job.state, job.lease_token = "running", uuid.uuid4()
        job.lease_until, job.attempts = now + timedelta(seconds=300), job.attempts + 1
        job.save()
    return job


def heartbeat(job):
    return (
        Job.objects.filter(
            pk=job.pk, state="running", lease_token=job.lease_token, lease_until__gt=timezone.now()
        ).update(lease_until=timezone.now() + timedelta(seconds=300))
        == 1
    )


def finish(job, error=None, terminal=False):
    with transaction.atomic():
        current = Job.objects.select_for_update().get(pk=job.pk)
        if (
            current.state != "running"
            or current.lease_token != job.lease_token
            or current.lease_until <= timezone.now()
        ):
            raise RuntimeError("lease_lost")
        if error and not terminal and current.attempts < 5:
            current.state = "queued"
            current.available_at = timezone.now() + timedelta(
                seconds=[30, 120, 600, 3600][current.attempts - 1]
            )
        else:
            current.state = "failed" if error else "complete"
        current.error_code = error or ""
        current.save()
