from functools import wraps

from access.policy import AccessDenied
from crypto.envelopes import IntegrityError, KMSUnavailable
from django.core.exceptions import ValidationError
from django.http import HttpResponseBase, JsonResponse

from .validation import DomainError


def endpoint(methods):
    def decorate(fn):
        @wraps(fn)
        def handle(request, *args, **kwargs):
            try:
                if request.method not in methods:
                    raise DomainError("method_not_allowed", 405)
                value = fn(request, *args, **kwargs)
                response = value if isinstance(value, HttpResponseBase) else JsonResponse(value)
                if isinstance(value, dict) and value.get("etag"):
                    response["ETag"] = value["etag"]
                if isinstance(value, dict) and value.get("context_reset_required"):
                    response.permission_reset_ack = True
                return response
            except (
                AccessDenied,
                DomainError,
                KMSUnavailable,
                IntegrityError,
                ValidationError,
                ValueError,
                TypeError,
                KeyError,
            ) as error:
                if isinstance(error, AccessDenied):
                    code, status = "not_found", 404
                elif isinstance(error, (KMSUnavailable, IntegrityError)):
                    code, status = "encrypted_storage_unavailable", 503
                elif isinstance(error, DomainError):
                    code, status = error.code, error.status
                else:
                    code, status = "invalid_request", 422
                response = JsonResponse(
                    {
                        "error": {
                            "code": code,
                            "message": "The request could not be completed.",
                            "field_errors": [],
                            "request_id": getattr(request, "health03_request_id", None),
                            "retryable": status == 503,
                        }
                    },
                    status=status,
                )
                if status == 503:
                    response["Retry-After"] = "30"
                return response

        return handle

    return decorate
