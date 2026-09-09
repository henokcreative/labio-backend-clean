import logging

from django.conf import settings
from django.core.cache import caches
from django.utils.crypto import salted_hmac
from redis.exceptions import RedisError
from rest_framework.throttling import BaseThrottle


logger = logging.getLogger(__name__)
CACHE_OPERATION_ERRORS = (OSError, RedisError)


def get_security_cache():
    return caches[settings.SECURITY_THROTTLE_CACHE_ALIAS]


class LoginAttemptGuard:
    """Atomic fixed-window counters for login spraying and credential guessing."""

    key_salt = "labio.login-throttle"

    def __init__(self, request):
        identifier = str(request.data.get("email", "")).strip().casefold()
        client_ip = BaseThrottle().get_ident(request) or "unknown"
        self.identifier_key = self._cache_key("identifier", identifier)
        self.ip_key = self._cache_key("ip", client_ip)
        self.retry_after = settings.LOGIN_RATE_WINDOW_SECONDS

    @classmethod
    def _cache_key(cls, kind, value):
        digest = salted_hmac(cls.key_salt, value).hexdigest()
        return f"login:{kind}:{digest}"

    def allow_attempt(self):
        try:
            cache = get_security_cache()
            ip_count = self._increment(cache, self.ip_key)
            if ip_count > settings.LOGIN_IP_RATE_LIMIT:
                return False

            identifier_count = self._increment(cache, self.identifier_key)
            return identifier_count <= settings.LOGIN_IDENTIFIER_RATE_LIMIT
        except CACHE_OPERATION_ERRORS:
            logger.exception(
                "Security login throttle cache unavailable; allowing login attempt."
            )
            return True

    def clear_identifier_failures(self):
        try:
            get_security_cache().delete(self.identifier_key)
        except CACHE_OPERATION_ERRORS:
            logger.exception(
                "Security login throttle cache unavailable while clearing failures."
            )

    @staticmethod
    def _increment(cache, key):
        timeout = settings.LOGIN_RATE_WINDOW_SECONDS
        if cache.add(key, 1, timeout=timeout):
            return 1
        try:
            return cache.incr(key)
        except ValueError:
            # The fixed window may expire between add() and incr(). Retry the
            # atomic creation once without extending an existing key's TTL.
            if cache.add(key, 1, timeout=timeout):
                return 1
            return cache.incr(key)
