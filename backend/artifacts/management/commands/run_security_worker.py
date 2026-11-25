import time

from django.core.management.base import BaseCommand

from artifacts.jobs import claim, execute


class Command(BaseCommand):
    help = "Run the durable security import/export worker."

    def handle(self, *args, **options):
        while True:
            job = claim()
            if job is None:
                time.sleep(2)
            else:
                execute(job)
