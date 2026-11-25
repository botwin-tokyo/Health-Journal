from django.conf import settings
from django.core.management.base import BaseCommand
from oauth2_provider.models import Application


class Command(BaseCommand):
    help = "Register the fixed synthetic public Android client (no APK secret)."

    def handle(self, *args, **options):
        Application.objects.update_or_create(
            client_id=settings.UPLOADER_CLIENT_ID,
            defaults={
                "name": "Health03 synthetic Android uploader",
                "client_type": Application.CLIENT_PUBLIC,
                "authorization_grant_type": Application.GRANT_AUTHORIZATION_CODE,
                "redirect_uris": settings.UPLOADER_CALLBACK,
                "skip_authorization": False,
            },
        )
        self.stdout.write(
            "Fixed synthetic public client registered; production App Links remain gated."
        )
