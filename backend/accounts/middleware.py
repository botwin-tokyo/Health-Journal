import uuid

from access.policy import AccessDenied, AuthorizationContext
from django.contrib.auth import logout
from django.http import JsonResponse

from .policy import fresh, session_state

PUBLIC = {"/api/v1/auth/bootstrap", "/api/v1/auth/invitation", "/health/live"}
AUTH_PREFIX = "/_allauth/browser/v1/"
# Keep unused email mutation/phone/code endpoints closed until their policy is integrated.
AUTH_ROUTES = {
    "config",
    "auth/session",
    "auth/login",
    "auth/signup",
    "auth/reauthenticate",
    "auth/email/verify",
    "auth/email/verify/resend",
    "auth/password/request",
    "auth/password/reset",
    "account/password/change",
}


class SecurityBoundaryMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        return self.respond(request)

    def respond(self, request):
        path = request.path
        from operations.models import OperationalControl

        control = OperationalControl.objects.filter(pk=1).first()
        if (
            control
            and (control.incident_locked or control.restored_candidate)
            and path != "/health/live"
        ):
            from artifacts import store

            if hasattr(store, "_service"):
                store._service.lock()
            response = JsonResponse({"code": "service_locked"}, status=503)
            response["Cache-Control"] = "no-store"
            return response
        response = None
        state = None
        selected_epoch = None
        is_auth = path.startswith("/_allauth/")
        protected = (
            path.startswith("/api/")
            and path not in PUBLIC
            and not path.startswith("/api/v1/ingestion/")
        )
        if request.headers.get("Authorization") and (
            protected
            or is_auth
            or path.startswith("/o/authorize/")
            or path.startswith("/o/continue/")
        ):
            response = JsonResponse({"code": "browser_credentials_required"}, status=401)
        if is_auth:
            route = path.removeprefix(AUTH_PREFIX)
            if not path.startswith(AUTH_PREFIX) or route not in AUTH_ROUTES:
                response = JsonResponse({"code": "not_found"}, status=404)
            if request.user.is_authenticated:
                state = session_state(request)
                if state is None:
                    logout(request)
                    response = JsonResponse({"code": "authentication_required"}, status=401)
            if route == "account/password/change" and not fresh(state):
                response = JsonResponse({"code": "reauthentication_required"}, status=403)
        if protected:
            state = session_state(request)
            if state is None:
                if request.user.is_authenticated:
                    logout(request)
                response = JsonResponse({"code": "authentication_required"}, status=401)
            request.security_state = state
            if state is not None and path != "/api/v1/session/context":
                try:
                    selected_epoch = AuthorizationContext(request).epoch()
                except AccessDenied:
                    response = JsonResponse({"code": "context_unavailable"}, status=403)
        response = response if response is not None else self.get_response(request)
        if getattr(request, "revoke_browser_session", False):
            logout(request)
            response = JsonResponse({"status": "credentials_updated", "login_required": True})
            state = None
        if getattr(request, "account_closure_accepted", False):
            state = None  # Preserve only the terminal receipt after deliberate session revocation.
        if state is not None and protected:
            try:
                current_epoch = AuthorizationContext(request).epoch()
                if (
                    selected_epoch is not None
                    and current_epoch != selected_epoch
                    and not getattr(response, "permission_reset_ack", False)
                ):
                    response = JsonResponse({"code": "permission_context_changed"}, status=403)
                response["X-Permission-Epoch"] = current_epoch
            except AccessDenied:
                if response.status_code < 400:
                    response = JsonResponse({"code": "context_unavailable"}, status=403)
        response["Cache-Control"] = "no-store, private"
        response["Pragma"] = "no-cache"
        response["X-Request-ID"] = str(uuid.uuid4())
        response["Referrer-Policy"] = "no-referrer"
        response["X-Frame-Options"] = "DENY"
        return response
