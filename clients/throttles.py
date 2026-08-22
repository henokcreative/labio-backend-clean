import hashlib

from django.conf import settings
from rest_framework.throttling import SimpleRateThrottle


class PasswordResetRequestThrottle(SimpleRateThrottle):
    """Short-lived request-source limit without retaining raw IP addresses."""

    scope = "password_reset_request"

    def get_rate(self):
        return "password-reset-request"

    def parse_rate(self, rate):
        return (
            settings.PASSWORD_RESET_RATE_LIMIT,
            settings.PASSWORD_RESET_RATE_WINDOW_SECONDS,
        )

    def get_cache_key(self, request, view):
        identifier = self.get_ident(request) or "unknown"
        digest = hashlib.sha256(identifier.encode("utf-8")).hexdigest()
        return self.cache_format % {
            "scope": self.scope,
            "ident": digest,
        }
