from access.policy import AccessDenied, RecordRef
from crypto.envelopes import Identity

from .models import SecureRecord


def reference(record, visited=None, budget=None):
    visited = frozenset() if visited is None else visited
    budget = [128] if budget is None else budget
    budget[0] -= 1
    if budget[0] < 0 or record.pk in visited or record.deleted_at or record.purged_at:
        raise AccessDenied()
    visited = visited | {record.pk}
    parents = ()
    if record.kind == "medication_event":
        from journal.models import MedicationLink

        linked = MedicationLink.objects.filter(
            event_id=record.object_id, entry__deleted_at__isnull=True
        ).select_related("entry__current__blob")[:101]
        parents = tuple(reference(link.entry.current.blob, visited, budget) for link in linked)
    return RecordRef(
        Identity(record.owner_id, record.kind, record.object_id, record.pk, record.schema_version),
        record.category,
        record.clinical_date,
        record.visibility,
        reference(record.parent, visited, budget) if record.parent_id and not parents else None,
        tuple(reference(child, visited, budget) for child in record.dependencies.all()[:129]),
        record.owner_only,
        parents,
        record.audience_grant,
    )


def select(context, record_id, action="read"):
    epoch = context.epoch()
    record = SecureRecord.objects.filter(
        pk=record_id, deleted_at__isnull=True, purged_at__isnull=True
    ).first()
    if record is None:
        raise AccessDenied()
    if record.audience_grant:
        from access.policy import BoundGrantContext

        context = BoundGrantContext(context, record.audience_grant)
        epoch = context.epoch()
    metadata = reference(record)
    context.require(metadata, action)
    if context.epoch() != epoch:
        raise AccessDenied()
    return record, metadata, context.envelope_authorizer(metadata, action, selected_epoch=epoch)
