"""Interactive enrollment; no credential or invitation is printed."""

import os
import secrets
from datetime import timedelta
from pathlib import Path

from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand, CommandError
from django.core.validators import validate_email
from django.db import connection, transaction
from django.utils import timezone

from accounts.adapter import token_hash
from accounts.models import Account, Invitation


class Command(BaseCommand):
    help = "Create the first owner enrollment; write its secret to a new operator-only file."

    def handle(self, *args, **options):
        email = input("Owner email: ").strip().lower()
        try:
            validate_email(email)
        except ValidationError as exc:
            raise CommandError("A valid email is required") from exc
        target = (
            Path(input("New private handoff file (outside the repository): ").strip())
            .expanduser()
            .resolve()
        )
        from django.conf import settings

        if target.is_relative_to(settings.BASE_DIR):
            raise CommandError("Choose a private path outside the repository")
        token = secrets.token_urlsafe(32)
        with transaction.atomic():
            with connection.cursor() as cursor:
                cursor.execute("SELECT pg_advisory_xact_lock(%s)", [3103002])
            if (
                Account.objects.filter(role="owner").exists()
                or Invitation.objects.filter(
                    role="owner", consumed_at__isnull=True, expires_at__gt=timezone.now()
                ).exists()
            ):
                raise CommandError("An owner or active owner enrollment already exists")
            with os.fdopen(
                os.open(target, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600), "w"
            ) as output:
                output.write(token + "\n")
            Invitation.objects.create(
                email=email,
                role="owner",
                secret_hash=token_hash(token),
                expires_at=timezone.now() + timedelta(hours=72),
            )
        self.stdout.write(
            "Inactive enrollment created. Private handoff expires in 72 hours. No login created."
        )
