import os

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = "Create or update a superuser from environment variables."

    def handle(self, *args, **options):
        username = os.environ.get("DJANGO_SUPERUSER_USERNAME")
        email = os.environ.get("DJANGO_SUPERUSER_EMAIL")
        password = os.environ.get("DJANGO_SUPERUSER_PASSWORD")

        if not username:
            raise CommandError("DJANGO_SUPERUSER_USERNAME is not set.")

        if not email:
            raise CommandError("DJANGO_SUPERUSER_EMAIL is not set.")

        if not password:
            raise CommandError("DJANGO_SUPERUSER_PASSWORD is not set.")

        User = get_user_model()

        user, created = User.objects.get_or_create(
            username=username,
            defaults={
                "email": email,
            },
        )

        user.email = email
        user.is_staff = True
        user.is_superuser = True
        user.is_active = True
        user.set_password(password)
        user.save()

        if created:
            self.stdout.write(
                self.style.SUCCESS(
                    f"Created superuser: {username}"
                )
            )
        else:
            self.stdout.write(
                self.style.SUCCESS(
                    f"Updated superuser: {username}"
                )
            )