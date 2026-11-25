import json

from django.core.management.base import BaseCommand

from operations.monitor import status


class Command(BaseCommand):
    def handle(self, *args, **options):
        self.stdout.write(json.dumps(status()))
