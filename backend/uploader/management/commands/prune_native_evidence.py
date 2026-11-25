from datetime import timedelta

from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone
from oauth2_provider.models import RefreshToken

from uploader.models import AuthorizationContinuation, TokenFamily
from uploader.policy import revoke_family
from uploader.views import native_lock


class Command(BaseCommand):
    help = "Prune native families only after their 180-day absolute window plus seven days."

    @transaction.atomic
    def handle(self, *args, **options):
        native_lock()
        expired = list(
            TokenFamily.objects.filter(
                absolute_expires_at__lt=timezone.now() - timedelta(days=7)
            ).values_list("pk", flat=True)
        )
        for family_id in expired:
            revoke_family(family_id)
            RefreshToken.objects.filter(token_family=family_id).delete()
        TokenFamily.objects.filter(pk__in=expired).delete()
        AuthorizationContinuation.objects.filter(expires_at__lt=timezone.now()).delete()
        self.stdout.write(
            f"Pruned {len(expired)} expired families; retained younger replay evidence."
        )
