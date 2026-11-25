import json

from django.core.management.base import BaseCommand

from operations.backup import perform


class Command(BaseCommand):
    def handle(self, *args, **options):
        self.stdout.write(json.dumps(perform()))
