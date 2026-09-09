import json
import os
import subprocess
import sys
import time
from unittest.mock import patch

from django.conf import settings
from django.contrib.auth.models import User
from django.core.cache import caches
from django.test import SimpleTestCase, TestCase, override_settings
from rest_framework.test import APIClient

from .login_throttle import LoginAttemptGuard


class SecurityCacheSettingsTests(SimpleTestCase):
    def test_development_uses_an_explicit_local_security_cache(self):
        cache_config = settings.CACHES[settings.SECURITY_THROTTLE_CACHE_ALIAS]
        self.assertEqual(
            cache_config["BACKEND"],
            "django.core.cache.backends.locmem.LocMemCache",
        )

    def test_production_requires_security_cache_url(self):
        environment = os.environ.copy()
        environment["DJANGO_ENV"] = "production"
        environment.pop("SECURITY_CACHE_URL", None)

        result = subprocess.run(
            [sys.executable, "-c", "import labio.settings"],
            capture_output=True,
            cwd=settings.BASE_DIR,
            env=environment,
            text=True,
        )

        self.assertNotEqual(result.returncode, 0)
        self.assertIn(
            "SECURITY_CACHE_URL must be configured in production",
            result.stderr,
        )

    def test_security_cache_url_selects_redis_with_bounded_timeouts(self):
        environment = os.environ.copy()
        environment.update(
            {
                "DJANGO_ENV": "development",
                "SECRET_KEY": "isolated-settings-secret",
                "SECURITY_CACHE_URL": "redis://cache.example.test:6379/0",
            }
        )
        result = subprocess.run(
            [
                sys.executable,
                "-c",
                (
                    "import json; from labio import settings; "
                    "print(json.dumps(settings.CACHES['security_throttle']))"
                ),
            ],
            check=True,
            capture_output=True,
            cwd=settings.BASE_DIR,
            env=environment,
            text=True,
        )

        cache_config = json.loads(result.stdout)
        self.assertEqual(
            cache_config["BACKEND"],
            "django.core.cache.backends.redis.RedisCache",
        )
        self.assertEqual(cache_config["OPTIONS"]["socket_connect_timeout"], 1)
        self.assertEqual(cache_config["OPTIONS"]["socket_timeout"], 1)
        self.assertFalse(cache_config["OPTIONS"]["retry_on_timeout"])


@override_settings(
    LOGIN_IP_RATE_LIMIT=20,
    LOGIN_IDENTIFIER_RATE_LIMIT=8,
    LOGIN_RATE_WINDOW_SECONDS=900,
)
class LoginThrottleTests(TestCase):
    password = "SecurePassword!123"

    def setUp(self):
        self.cache = caches[settings.SECURITY_THROTTLE_CACHE_ALIAS]
        self.cache.clear()
        self.user = User.objects.create_user(
            username="client@example.com",
            email="client@example.com",
            password=self.password,
        )
        self.api = APIClient()

    def login(self, email, password="wrong-password", api=None, **headers):
        return (api or self.api).post(
            "/api/auth/login/",
            {"email": email, "password": password},
            format="json",
            **headers,
        )

    @override_settings(LOGIN_IDENTIFIER_RATE_LIMIT=2)
    def test_normalized_identifier_reaches_failure_limit(self):
        variants = (
            "client@example.com",
            " CLIENT@EXAMPLE.COM ",
            "Client@Example.Com",
        )

        responses = [
            self.login(email, REMOTE_ADDR="198.51.100.10")
            for email in variants
        ]

        self.assertEqual(
            [response.status_code for response in responses],
            [400, 400, 429],
        )
        self.assertEqual(responses[-1]["Retry-After"], "900")

    @override_settings(LOGIN_IP_RATE_LIMIT=2, LOGIN_IDENTIFIER_RATE_LIMIT=20)
    def test_multiple_identifiers_reach_ip_spray_limit(self):
        responses = [
            self.login(
                f"unknown-{index}@example.com",
                REMOTE_ADDR="198.51.100.11",
            )
            for index in range(3)
        ]

        self.assertEqual(
            [response.status_code for response in responses],
            [400, 400, 429],
        )

    @override_settings(LOGIN_IP_RATE_LIMIT=2, LOGIN_IDENTIFIER_RATE_LIMIT=20)
    def test_correct_credentials_are_blocked_after_ip_limit(self):
        for index in range(2):
            self.assertEqual(
                self.login(
                    f"unknown-{index}@example.com",
                    REMOTE_ADDR="198.51.100.12",
                ).status_code,
                400,
            )

        blocked = self.login(
            self.user.email,
            self.password,
            REMOTE_ADDR="198.51.100.12",
        )

        self.assertEqual(blocked.status_code, 429)

    def test_success_clears_identifier_but_not_ip_counter(self):
        address = "198.51.100.13"
        self.assertEqual(
            self.login(self.user.email, REMOTE_ADDR=address).status_code,
            400,
        )
        self.assertEqual(
            self.login(
                self.user.email,
                self.password,
                REMOTE_ADDR=address,
            ).status_code,
            200,
        )

        identifier_key = LoginAttemptGuard._cache_key(
            "identifier",
            self.user.email.casefold(),
        )
        ip_key = LoginAttemptGuard._cache_key("ip", address)
        self.assertNotIn(self.user.email, identifier_key)
        self.assertIsNone(self.cache.get(identifier_key))
        self.assertEqual(self.cache.get(ip_key), 2)

    @override_settings(LOGIN_IP_RATE_LIMIT=2, LOGIN_IDENTIFIER_RATE_LIMIT=20)
    def test_separate_clients_share_the_security_cache_counters(self):
        other_worker = APIClient()
        address = "198.51.100.14"

        first = self.login("one@example.com", REMOTE_ADDR=address)
        second = self.login(
            "two@example.com",
            api=other_worker,
            REMOTE_ADDR=address,
        )
        blocked = self.login("three@example.com", REMOTE_ADDR=address)

        self.assertEqual(
            [first.status_code, second.status_code, blocked.status_code],
            [400, 400, 429],
        )

    @override_settings(
        REST_FRAMEWORK={"NUM_PROXIES": 1},
        LOGIN_IP_RATE_LIMIT=1,
        LOGIN_IDENTIFIER_RATE_LIMIT=20,
    )
    def test_spoofed_forwarded_address_cannot_bypass_trusted_proxy_model(self):
        first = self.login(
            "one@example.com",
            REMOTE_ADDR="10.0.0.8",
            HTTP_X_FORWARDED_FOR="203.0.113.1, 198.51.100.15",
        )
        blocked = self.login(
            "two@example.com",
            REMOTE_ADDR="10.0.0.8",
            HTTP_X_FORWARDED_FOR="203.0.113.2, 198.51.100.15",
        )

        self.assertEqual(first.status_code, 400)
        self.assertEqual(blocked.status_code, 429)

    def test_unknown_account_and_wrong_password_responses_are_identical(self):
        wrong_password = self.login(
            self.user.email,
            REMOTE_ADDR="198.51.100.16",
        )
        unknown_account = self.login(
            "unknown@example.com",
            REMOTE_ADDR="198.51.100.17",
        )

        self.assertEqual(wrong_password.status_code, unknown_account.status_code)
        self.assertEqual(wrong_password.data, unknown_account.data)

    @patch("labio.login_throttle.get_security_cache", side_effect=ConnectionError)
    def test_cache_failure_fails_open_and_logs(self, get_cache):
        with self.assertLogs("labio.login_throttle", level="ERROR") as logs:
            response = self.login(
                self.user.email,
                self.password,
                REMOTE_ADDR="198.51.100.18",
            )

        self.assertEqual(response.status_code, 200)
        self.assertGreaterEqual(get_cache.call_count, 1)
        self.assertTrue(
            any("cache unavailable" in message for message in logs.output)
        )

    @override_settings(
        LOGIN_IP_RATE_LIMIT=20,
        LOGIN_IDENTIFIER_RATE_LIMIT=1,
        LOGIN_RATE_WINDOW_SECONDS=1,
    )
    def test_counter_ttl_allows_attempts_after_window_expires(self):
        address = "198.51.100.19"
        self.assertEqual(
            self.login(self.user.email, REMOTE_ADDR=address).status_code,
            400,
        )
        self.assertEqual(
            self.login(self.user.email, REMOTE_ADDR=address).status_code,
            429,
        )

        time.sleep(1.1)

        self.assertEqual(
            self.login(self.user.email, REMOTE_ADDR=address).status_code,
            400,
        )

    def test_normal_login_contract_remains_unchanged_below_limits(self):
        response = self.login(
            self.user.email,
            self.password,
            REMOTE_ADDR="198.51.100.20",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            set(response.data),
            {"access", "refresh", "is_staff", "is_portal_staff"},
        )

    def test_original_twenty_five_attempt_proof_is_stopped_by_429(self):
        statuses = [
            self.login(
                self.user.email,
                REMOTE_ADDR="198.51.100.21",
            ).status_code
            for _ in range(25)
        ]

        self.assertEqual(statuses[:8], [400] * 8)
        self.assertEqual(statuses[8:], [429] * 17)
