from access import views as sharing
from accounts import local, views
from artifacts import views as artifacts
from body import views as body
from breathing import imports as breathing_imports
from breathing import views as breathing
from django.urls import include, path
from ingest import evidence as phone_evidence
from ingest import views as ingest
from journal import views as journal
from labs import views as labs
from metrics import views as metrics
from operations import views as operations
from patients import views as patients
from patients.sessions import sessions
from reports import archives, downloads
from reports import views as reports
from sleep_activity import blood_pressure
from sleep_activity import views as sleep_activity
from uploader import views as native

urlpatterns = [
    path("api/v1/phone/records", phone_evidence.records),
    path("api/v1/phone/records/<uuid:record_id>/assets/<uuid:asset_id>", phone_evidence.asset),
    path("internal/local-session", local.enter),
    path("internal/health/ready", operations.ready),
    path("api/v1/account/deletion-requests", operations.deletion_requests),
    path("api/v1/account/deletion-requests/<uuid:request_id>", operations.deletion_requests),
    path("api/v1/security/sessions/<str:session_id>/revoke", sessions),
    path("api/v1/security/sessions", sessions),
    path("api/v1/security/sessions/revoke", sessions),
    path("api/v1/exports", archives.create),
    path("api/v1/exports/<uuid:export_id>/download-tickets", downloads.ticket),
    path("api/v1/exports/<uuid:export_id>/content", downloads.content),
    path("api/v1/activity/workouts/<uuid:record_id>", sleep_activity.workout),
    path("api/v1/baselines/<uuid:record_id>/retire", metrics.retire),
    path("api/v1/breathing/imports", breathing_imports.imports),
    path("api/v1/breathing/imports/<uuid:import_id>", breathing_imports.imports),
    path("api/v1/breathing/imports/<uuid:import_id>/review", breathing_imports.review),
    path("api/v1/breathing/imports/<uuid:import_id>/commit", breathing_imports.commit),
    path("api/v1/breathing/sessions/<uuid:record_id>/designation", breathing.designation),
    path("api/v1/ingestion/assets", ingest.assets),
    path("api/v1/ingestion/commands/<uuid:command_id>/ack", ingest.acknowledge),
    path("api/v1/labs/reports/<uuid:report_id>/publish", labs.publish),
    path("api/v1/labs/trends", labs.trends),
    path("api/v1/sharing/grants/<uuid:grant_id>/invite", sharing.invite),
    path("api/v1/sharing/accept", sharing.accept),
    path("api/v1/settings", patients.settings),
    path("api/v1/security/status", patients.security_status),
    path("api/v1/security/access-events", patients.events),
    path("api/v1/review/drafts", reports.drafts),
    path("api/v1/review/drafts/<uuid:record_id>", reports.drafts),
    path("api/v1/review/drafts/<uuid:record_id>/snapshots", reports.snapshots),
    path("api/v1/review/snapshots/<uuid:record_id>", reports.snapshots),
    path("api/v1/review/snapshots/<uuid:record_id>/exports", reports.export),
    path("api/v1/exports/<uuid:job_id>", reports.export_status),
    path("api/v1/sharing/grants", sharing.grants),
    path("api/v1/sharing/grants/<uuid:grant_id>", sharing.grants),
    path("api/v1/sharing/grants/<uuid:grant_id>/revoke", sharing.revoke),
    path("api/v1/labs/uploads", labs.upload),
    path("api/v1/labs/reports", labs.reports),
    path("api/v1/labs/reports/<uuid:report_id>", labs.reports),
    path("api/v1/labs/imports/<uuid:report_id>", labs.reports),
    path("api/v1/labs/reports/<uuid:report_id>/review", labs.review),
    path("api/v1/documents/<uuid:document_id>/content", labs.document),
    path("api/v1/journal/search", journal.search),
    path("api/v1/catalog/metrics", metrics.catalog),
    path("api/v1/overview", metrics.overview),
    path("api/v1/sleep-activity", sleep_activity.page),
    path("api/v1/blood-pressure", blood_pressure.page),
    path("api/v1/baselines", metrics.references),
    path("api/v1/baselines/preview", metrics.preview),
    path("api/v1/baselines/<uuid:record_id>", metrics.references),
    path("api/v1/body", body.page),
    path("api/v1/body/weights", body.weights),
    path("api/v1/body/weights/<uuid:record_id>", body.weights),
    path("api/v1/body/days/<str:day>/representative", body.representative),
    path("api/v1/breathing", breathing.page),
    path("api/v1/breathing/manual-sessions", breathing.create),
    path("api/v1/breathing/sessions/<uuid:record_id>", breathing.page),
    path("api/v1/ingestion/batches", ingest.batches),
    path("api/v1/ingestion/batches/<uuid:batch_id>", ingest.batches),
    path("api/v1/sync/requests", ingest.sync),
    path("api/v1/sync/status", ingest.sync),
    path("api/v1/account/delete", operations.delete_account),
    path("api/v1/records/<uuid:record_id>/delete", operations.delete_record),
    path("api/v1/exports/<uuid:record_id>/tickets", artifacts.ticket),
    path("o/authorize/", native.authorize),
    path("o/continue/<uuid:continuation_id>/", native.continuation),
    path("o/token/", native.token),
    path("o/revoke_token/", native.revoke_token),
    path("api/v1/ingestion/config", native.ingestion_config),
    path("api/v1/devices", native.devices),
    path("api/v1/devices/<uuid:device_id>/revoke", native.revoke_device),
    path("health/live", views.live),
    path("api/v1/auth/bootstrap", views.bootstrap),
    path("api/v1/auth/invitation", views.invitation),
    path("api/v1/session", views.session),
    path("api/v1/session/activity", views.activity),
    path("api/v1/session/context", views.switch_context),
    path("_allauth/", include("allauth.headless.urls")),
]

for route, kind in [
    ("entries", "journal"),
    ("questions", "question"),
    ("medication-events", "medication"),
]:
    urlpatterns += [
        path("api/v1/journal/" + route, journal.records, {"kind": kind}),
        path("api/v1/journal/" + route + "/<uuid:record_id>", journal.records, {"kind": kind}),
    ]
