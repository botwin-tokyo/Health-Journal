import json

from django.core.management.base import BaseCommand

from operations.ledger import publish


class Command(BaseCommand):
    def handle(self, *args, **options):
        self.stdout.write(json.dumps(publish()))
