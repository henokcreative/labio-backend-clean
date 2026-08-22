import hashlib

from django.conf import settings
from rest_framework.throttling import SimpleRateThrottle


class ContactSubmissionRateThrottle(SimpleRateThrottle):
    """Short-lived, per-request-source protection for the public form."""

    scope = "contact_submission"

    def get_rate(self):
        return "contact-submission"

    def parse_rate(self, rate):
        return (
            settings.CONTACT_SUBMISSION_RATE_LIMIT,
            settings.CONTACT_SUBMISSION_RATE_WINDOW_SECONDS,
        )

    def get_cache_key(self, request, view):
        identifier = self.get_ident(request) or "unknown"
        digest = hashlib.sha256(identifier.encode("utf-8")).hexdigest()
        return self.cache_format % {
            "scope": self.scope,
            "ident": digest,
        }
