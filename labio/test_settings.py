import json
import os
import subprocess
import sys

from django.test import SimpleTestCase


class RenderAllowedHostsSettingsTests(SimpleTestCase):
    @staticmethod
    def _load_allowed_hosts(*, allowed_hosts, render_hostname):
        environment = os.environ.copy()
        environment.update(
            {
                "ALLOWED_HOSTS": allowed_hosts,
                "CLOUDINARY_API_KEY": "test-key",
                "CLOUDINARY_API_SECRET": "test-secret",
                "CLOUDINARY_CLOUD_NAME": "test-cloud",
                "CMS_MEDIA_ACCESS_KEY_ID": "test-access-key",
                "CMS_MEDIA_BUCKET_NAME": "test-bucket",
                "CMS_MEDIA_SECRET_ACCESS_KEY": "test-secret-key",
                "CONTACT_EMAIL": "contact@example.com",
                "CORS_ALLOWED_ORIGINS": "https://example.com",
                "CSRF_TRUSTED_ORIGINS": "https://example.com",
                "DATABASE_URL": "sqlite:///:memory:",
                "DEBUG": "false",
                "DJANGO_ENV": "production",
                "EMAIL_FROM": "notifications@example.com",
                "INVITATION_FRONTEND_URL": (
                    "https://example.com/accept-invitation"
                ),
                "RENDER_EXTERNAL_HOSTNAME": render_hostname,
                "RESEND_API_KEY": "test-resend-key",
                "SECRET_KEY": "test-only-secret-key-" * 4,
                "SECURE_HSTS_SECONDS": "300",
                "WAGTAILADMIN_BASE_URL": "https://example.com",
            }
        )
        result = subprocess.run(
            [
                sys.executable,
                "-c",
                (
                    "import json; "
                    "from django.conf import settings; "
                    "print(json.dumps(settings.ALLOWED_HOSTS))"
                ),
            ],
            check=True,
            capture_output=True,
            cwd=os.path.dirname(os.path.dirname(__file__)),
            env=environment,
            text=True,
        )
        return json.loads(result.stdout)

    def test_render_hostname_is_appended_to_explicit_production_hosts(self):
        allowed_hosts = self._load_allowed_hosts(
            allowed_hosts="api.labiomedia.com",
            render_hostname="labio-backend-prod.onrender.com",
        )

        self.assertEqual(
            allowed_hosts,
            ["api.labiomedia.com", "labio-backend-prod.onrender.com"],
        )

    def test_render_hostname_is_not_duplicated(self):
        allowed_hosts = self._load_allowed_hosts(
            allowed_hosts=(
                "api.labiomedia.com,labio-backend-prod.onrender.com"
            ),
            render_hostname="labio-backend-prod.onrender.com",
        )

        self.assertEqual(
            allowed_hosts,
            ["api.labiomedia.com", "labio-backend-prod.onrender.com"],
        )
