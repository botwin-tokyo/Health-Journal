"""Authorized current BP revisions, including explicitly unqualified source readings."""

from datetime import date, timedelta

from records import service
from records.http import endpoint
from records.validation import DomainError


@endpoint({"GET"})
def page(request):
    try:
        end = date.fromisoformat(request.GET.get("to", date.today().isoformat()))
        start = date.fromisoformat(request.GET.get("from", (end - timedelta(days=27)).isoformat()))
    except ValueError:
        raise DomainError("invalid_date") from None
    if not 0 <= (end - start).days < 366:
        raise DomainError("invalid_date_range")
    return service.permitted(
        request,
        ["blood_pressure"],
        start.isoformat(),
        end.isoformat(),
        200,
        request.GET.get("cursor"),
    )
