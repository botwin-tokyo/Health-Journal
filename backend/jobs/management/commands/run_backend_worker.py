import threading
import time

from access.policy import AccessDenied
from artifacts import jobs as security
from django.core.management.base import BaseCommand
from django.db import connections
from ingest import blood_pressure_backfill
from ingest.service import process
from records.validation import DomainError

from jobs import service


class Command(BaseCommand):
    help = "Run bounded backend and isolated-artifact jobs."

    def add_arguments(self, parser):
        parser.add_argument("--once", action="store_true")

    def handle(self, *args, **options):
        next_display_scan = 0.0
        while True:
            if time.monotonic() >= next_display_scan:
                try:
                    blood_pressure_backfill.schedule()
                except Exception:
                    # Display repair must not block ordinary midnight ingestion; retry next minute.
                    self.stderr.write("Blood-pressure display scheduling deferred; retrying automatically")
                next_display_scan = time.monotonic() + 60
            job = service.claim()
            if job:
                stop = threading.Event()

                def renew():
                    try:
                        while not stop.wait(30):
                            if not service.heartbeat(job):
                                return
                    finally:
                        connections.close_all()

                thread = threading.Thread(target=renew, daemon=True)
                thread.start()
                try:
                    if job.kind == "ingest":
                        process(job)
                    elif job.kind == blood_pressure_backfill.KIND:
                        blood_pressure_backfill.execute(job)
                    elif job.kind == "archive":
                        from reports.archives import execute

                        execute(job)
                    elif job.kind == "invalidate":
                        from metrics.aggregates import rebuild

                        rebuild(job)
                    else:
                        service.finish(job, "unsupported_job", True)
                        continue
                    service.finish(job)
                except Exception as error:
                    terminal = (
                        isinstance(error, AccessDenied)
                        or isinstance(error, DomainError)
                        and error.status < 500
                    )
                    code = (
                        "permission_changed"
                        if isinstance(error, AccessDenied)
                        else error.code
                        if isinstance(error, DomainError)
                        else "dependency_unavailable"
                    )
                    try:
                        service.finish(job, code, terminal)
                    except RuntimeError:
                        # The replacement lease holder owns publication and state.
                        pass
                    else:
                        if job.kind == "archive" and (terminal or job.attempts >= 5):
                            from reports.models import ExportBundle

                            ExportBundle.objects.filter(pk=job.reference).update(
                                state="revoked" if isinstance(error, AccessDenied) else "failed",
                                error_code=code,
                            )
                finally:
                    stop.set()
                    thread.join(timeout=2)
                    connections.close_all()
            artifact = security.claim()
            if artifact:
                security.execute(artifact)
            if options["once"]:
                return
            if not job and not artifact:
                time.sleep(2)
