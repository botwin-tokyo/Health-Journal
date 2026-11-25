"""Enroll fictional accounts only in the dedicated frontend acceptance database."""

import os
import secrets
from datetime import date, timedelta
from pathlib import Path

from access.models import SharingGrant
from accounts.models import Account
from allauth.account.models import EmailAddress
from django.conf import settings
from django.core.management import call_command
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone


class Command(BaseCommand):
    help = "Prepare isolated frontend fixtures; never runs against the owner database."

    def handle(self, *args, **options):
        if (
            settings.ENVIRONMENT != "development"
            or settings.DATABASES["default"]["NAME"] != "health03_frontend_acceptance"
        ):
            raise CommandError("Only the isolated frontend acceptance database is permitted")
        from operations.models import DeletionRequest

        if DeletionRequest.objects.exists():
            raise CommandError(
                "Fixture was closed; recreate the isolated database before preparing"
            )
        if not Account.objects.exists():
            call_command("seed_synthetic", environment="development")
        if Account.objects.exclude(email__endswith="@example.invalid").exists():
            raise CommandError("Non-fictional identity found; refusing enrollment")
        password = secrets.token_urlsafe(32)
        path = Path(settings.BASE_DIR) / ".local/frontend-test-password"
        descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(descriptor, "w") as output:
            output.write(password)
        users = []
        for name, role in [
            ("fixture-owner", "owner"),
            ("doctor-a", "doctor"),
            ("doctor-b", "doctor"),
        ]:
            user, _ = Account.objects.get_or_create(
                email=name + "@example.invalid", defaults={"role": role}
            )
            user.set_password(password)
            user.is_active = user.enrollment_complete = True
            user.save()
            EmailAddress.objects.update_or_create(
                user=user, email=user.email, defaults={"verified": True, "primary": True}
            )
            users.append(user)
        for doctor, categories in zip(users[1:], [["body", "questions"], ["breathing"]]):
            SharingGrant.objects.update_or_create(
                owner=users[0],
                recipient=doctor,
                defaults={
                    "recipient_email": doctor.email,
                    "state": "active",
                    "starts_on": date(2026, 10, 1),
                    "ends_on": date(2026, 11, 30),
                    "not_before": timezone.now() - timedelta(minutes=1),
                    "approved_at": timezone.now(),
                    "expires_at": timezone.now() + timedelta(days=1),
                    "categories": categories,
                    "actions": ["read"],
                    "selected_result_ids": [],
                },
            )
        from weasyprint import HTML

        HTML(
            string="<h1>Fictional laboratory report</h1><p>Sample only. Collection date November 7, 2026.</p><p>Fictional analyte: 5.00 mg/L. Reference 0-10 mg/L.</p>"
        ).write_pdf("/tmp/health03-synthetic-lab.pdf")
        self.stdout.write(
            "Isolated fictional accounts prepared. Password is in the private local file."
        )
