from django.http import JsonResponse
from django.test import RequestFactory
from uploader.public_boundary import UploadHostBoundaryMiddleware


def test_public_hostname_allows_only_machine_routes(settings):
    settings.HEALTH03_UPLOAD_HOST = "phone.example.org"
    settings.ALLOWED_HOSTS = ["phone.example.org", "localhost"]
    boundary = UploadHostBoundaryMiddleware(lambda request: JsonResponse({"upstream": True}))
    factory = RequestFactory()
    for path in [
        "/api/v1/ingestion/batches",
        "/api/v1/ingestion/config",
        "/api/v1/ingestion/assets",
        "/o/token/",
        "/o/revoke_token/",
    ]:
        request = factory.post(
            path, HTTP_HOST="phone.example.org", HTTP_X_FORWARDED_PROTO="https"
        )
        assert boundary(request).status_code == 200
    for path in [
        "/",
        "/overview",
        "/internal/local-session",
        "/api/v1/auth/bootstrap",
        "/api/v1/body",
        "/_allauth/browser/v1/auth/login",
        "/o/authorize/",
        "/admin/",
        "/api/v1/ingestion/batches/../body",
    ]:
        request = factory.get(
            path, HTTP_HOST="phone.example.org", HTTP_X_FORWARDED_PROTO="https"
        )
        assert boundary(request).status_code == 404
    assert (
        boundary(
            factory.post("/api/v1/ingestion/batches", HTTP_HOST="phone.example.org")
        ).status_code
        == 400
    )
    assert (
        boundary(factory.post("/internal/local-session", HTTP_HOST="localhost:8443")).status_code
        == 200
    )


def test_upload_boundary_runs_before_forwarding_headers_are_stripped(settings):
    assert settings.MIDDLEWARE.index(
        "uploader.public_boundary.UploadHostBoundaryMiddleware"
    ) < settings.MIDDLEWARE.index("operations.http.BoundaryMiddleware")
