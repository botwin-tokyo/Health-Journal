import json

from django.core.management.base import BaseCommand

from operations.retention import run


class Command(BaseCommand):
    def add_arguments(self, parser):
        parser.add_argument("--dry-run", action="store_true")

    def handle(self, *args, **options):
        self.stdout.write(json.dumps(run(dry_run=options["dry_run"])))
