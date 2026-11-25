from django.core.management.base import BaseCommand
from django.db import transaction
from metrics.registry import definitions

from records.models import RegistryDefinition


class Command(BaseCommand):
    help = "Load versioned public metric definitions; no clinical values."

    @transaction.atomic
    def handle(self, *args, **options):
        for row in definitions():
            RegistryDefinition.objects.update_or_create(
                key=row["key"], defaults={"version": "health03-metrics-1", "definition": row}
            )
        self.stdout.write("Metric definitions loaded.")
