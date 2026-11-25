import json

from django.core.management.base import BaseCommand

from operations.lifecycle import incident_lock


class Command(BaseCommand):
    def handle(self, *args, **options):
        self.stdout.write(json.dumps(incident_lock() or {"locked": True}))
