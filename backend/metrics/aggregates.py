"""Immutable encrypted aggregates, published only while the source epoch is current."""

import json
from datetime import timedelta

from access.policy import AccessDenied, AggregateAuthorizationContext, RecordRef
from artifacts import store
from artifacts.models import SecureRecord
from artifacts.selectors import select
from crypto.envelopes import Identity
from django.db import transaction
from django.utils import timezone
from jobs.models import Job
from records.models import Patient, Record
from records.validation import DomainError

from .calculations import baseline
from .models import AggregateSnapshot, AggregateState
from .series import contributors


def rebuild(job):
    changed = Record.objects.select_related("patient").filter(pk=job.reference).first()
    if changed is None:
        return
    patient = changed.patient
    context = AggregateAuthorizationContext(patient.owner_id)
    context.current()
    epoch = patient.source_epoch
    days = set(
        changed.revisions.exclude(blob__clinical_date=None).values_list(
            "blob__clinical_date", flat=True
        )
    )
    # Both corrected dates and all affected trailing windows must be refreshed.
    dates = sorted({day + timedelta(days=offset) for day in days for offset in range(29)})
    metrics = [("weight", "", "recent"), ("weight", "", "weight_mean")]
    if changed.kind == "pulmonary":
        metrics = [
            (metric, slot, "recent")
            for metric in ["fvc", "fev1", "fev6", "pef", "fef2575", "fet"]
            for slot in ["morning", "noon", "evening"]
        ]
    elif changed.kind != "weight":
        return
    for day in dates:
        for metric, slot, method in metrics:
            if AggregateSnapshot.objects.filter(
                patient=patient,
                clinical_date=day,
                metric=metric,
                slot=slot,
                method=method,
                source_epoch=epoch,
            ).exists():
                continue
            start, end = (
                (day - timedelta(days=6), day)
                if method == "weight_mean"
                else (day - timedelta(days=28), day - timedelta(days=1))
            )
            try:
                rows, deps, definitions = contributors(
                    context, patient, metric, start, end, slot or None
                )
                payload = baseline(rows, day, method)
                payload["series_definitions"] = definitions
            except DomainError as error:
                if error.code != "series_selection_required":
                    raise
                payload, deps = {"value": None, "absent_reason": "source_conflict"}, []
            payload.update(
                calculated_at=timezone.now().isoformat(),
                clinical_date=day.isoformat(),
                source_epoch=epoch,
            )
            blob = SecureRecord(
                owner_id=patient.owner_id,
                kind="derived_snapshot",
                category="body" if metric == "weight" else "breathing",
                clinical_date=day,
            )
            identity = Identity(blob.owner_id, blob.kind, blob.object_id, blob.pk, 1)
            blob.blob_name, blob.ciphertext_sha256, blob.ciphertext_bytes = store.write(
                json.dumps(payload).encode(),
                identity,
                context.envelope_authorizer(RecordRef(identity, blob.category, day), "write"),
            )
            with transaction.atomic():
                locked = Patient.objects.select_for_update().get(pk=patient.pk)
                lease = Job.objects.select_for_update().get(pk=job.pk)
                if (
                    lease.state != "running"
                    or lease.lease_token != job.lease_token
                    or lease.lease_until <= timezone.now()
                ):
                    raise DomainError("lease_lost", 503)
                context.current()
                if locked.source_epoch != epoch:
                    from jobs.service import enqueue

                    enqueue("invalidate", changed.pk, locked.source_epoch)
                    return
                if not AggregateSnapshot.objects.filter(
                    patient=patient,
                    clinical_date=day,
                    metric=metric,
                    slot=slot,
                    method=method,
                    source_epoch=epoch,
                ).exists():
                    blob.save()
                    blob.dependencies.set(deps)
                    AggregateSnapshot.objects.create(
                        patient=patient,
                        clinical_date=day,
                        metric=metric,
                        slot=slot,
                        method=method,
                        source_epoch=epoch,
                        blob=blob,
                    )
    AggregateState.objects.update_or_create(patient=patient, defaults={"computed_epoch": epoch})


def read(context, patient, metric, day, method="recent", slot=""):
    snapshot = (
        AggregateSnapshot.objects.filter(
            patient_id=patient.pk, clinical_date=day, metric=metric, slot=slot, method=method
        )
        .select_related("blob")
        .order_by("-source_epoch")
        .first()
    )
    if snapshot is None:
        return None
    try:
        blob, metadata, authorize = select(context, snapshot.blob_id)
        payload = json.loads(store.read(blob, metadata.identity, authorize))
    except AccessDenied:
        return {"value": None, "absent_reason": "not_in_shared_scope"}
    current = snapshot.source_epoch == Patient.objects.get(pk=patient.pk).source_epoch
    if not current:
        start, end = (
            (day - timedelta(days=6), day)
            if method == "weight_mean"
            else (day - timedelta(days=28), day - timedelta(days=1))
        )
        try:
            _, dependencies, definitions = contributors(
                context, patient, metric, start, end, slot or None
            )
            current = (
                {item.pk for item in dependencies}
                == set(snapshot.blob.dependencies.values_list("pk", flat=True))
                and definitions == payload.get("series_definitions", {})
                and payload.get("absent_reason") != "source_conflict"
            )
        except AccessDenied:
            return {"value": None, "absent_reason": "not_in_shared_scope"}
        except DomainError as error:
            if error.code != "series_selection_required":
                raise
    payload["calculation_state"] = "current" if current else "updating"
    payload["aggregate_revision_id"] = str(snapshot.blob_id)
    return payload
