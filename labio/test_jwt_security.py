from django.contrib.auth.models import User
from django.test import TestCase
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode
from rest_framework.test import APIClient
from rest_framework_simplejwt.settings import api_settings
from rest_framework_simplejwt.tokens import RefreshToken

from clients.models import Client
from clients.tokens import password_reset_token_generator


class PasswordBoundJwtTests(TestCase):
    old_password = "OldSecurePassword!123"
    new_password = "NewSecurePassword!456"

    def setUp(self):
        self.user = self.create_client_user("client-a@example.com")
        self.other_user = self.create_client_user("client-b@example.com")
        self.api = APIClient()

    def create_client_user(self, email):
        user = User.objects.create_user(
            username=email,
            email=email,
            password=self.old_password,
        )
        Client.objects.create(name=email, email=email, user=user)
        return user

    def issue_tokens(self, user=None):
        user = user or self.user
        refresh = RefreshToken.for_user(user)
        return str(refresh.access_token), str(refresh)

    def authorize(self, access):
        self.api.credentials(HTTP_AUTHORIZATION=f"Bearer {access}")

    def reset_password(self, password=None):
        token = password_reset_token_generator.make_token(self.user)
        response = self.api.post(
            "/api/auth/password-reset/confirm/",
            {
                "uid": urlsafe_base64_encode(force_bytes(self.user.pk)),
                "token": token,
                "password": password or self.new_password,
                "password_confirmation": password or self.new_password,
            },
            format="json",
        )
        return response

    def refresh(self, token):
        return self.api.post(
            "/api/auth/refresh/",
            {"refresh": token},
            format="json",
        )

    def test_access_and_refresh_tokens_work_before_password_change(self):
        access, refresh = self.issue_tokens()

        self.authorize(access)
        self.assertEqual(self.api.get("/api/auth/profile/").status_code, 200)
        self.api.credentials()
        refresh_response = self.refresh(refresh)
        self.assertEqual(refresh_response.status_code, 200)
        self.assertIn("access", refresh_response.data)

    def test_password_reset_rejects_old_access_and_refresh_tokens(self):
        access, refresh = self.issue_tokens()
        self.assertEqual(self.reset_password().status_code, 200)

        self.authorize(access)
        self.assertEqual(self.api.get("/api/auth/profile/").status_code, 401)
        self.api.credentials()
        self.assertEqual(self.refresh(refresh).status_code, 401)

    def test_new_access_and_refresh_tokens_work_after_password_reset(self):
        self.assertEqual(self.reset_password().status_code, 200)
        login = self.api.post(
            "/api/auth/login/",
            {"email": self.user.email, "password": self.new_password},
            format="json",
        )

        self.assertEqual(login.status_code, 200)
        self.authorize(login.data["access"])
        self.assertEqual(self.api.get("/api/auth/profile/").status_code, 200)
        self.api.credentials()
        refreshed = self.refresh(login.data["refresh"])
        self.assertEqual(refreshed.status_code, 200)
        self.assertIn("access", refreshed.data)

    def test_one_clients_password_change_does_not_revoke_another_clients_tokens(self):
        other_access, other_refresh = self.issue_tokens(self.other_user)
        self.assertEqual(self.reset_password().status_code, 200)

        self.authorize(other_access)
        self.assertEqual(self.api.get("/api/auth/profile/").status_code, 200)
        self.api.credentials()
        self.assertEqual(self.refresh(other_refresh).status_code, 200)

    def test_refresh_for_inactive_user_is_rejected(self):
        _, refresh = self.issue_tokens()
        self.user.is_active = False
        self.user.save(update_fields=["is_active"])

        response = self.refresh(refresh)

        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.data["code"], "token_not_valid")

    def test_refresh_for_deleted_user_is_rejected(self):
        _, refresh = self.issue_tokens()
        self.user.delete()

        response = self.refresh(refresh)

        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.data["code"], "token_not_valid")

    def test_refresh_for_unknown_user_is_rejected(self):
        refresh = RefreshToken.for_user(self.user)
        refresh[api_settings.USER_ID_CLAIM] = 999999999

        response = self.refresh(str(refresh))

        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.data["code"], "token_not_valid")

    def test_refresh_missing_password_digest_claim_is_rejected(self):
        refresh = RefreshToken.for_user(self.user)
        del refresh[api_settings.REVOKE_TOKEN_CLAIM]

        response = self.refresh(str(refresh))

        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.data["code"], "token_not_valid")

    def test_malformed_refresh_token_retains_generic_error_behavior(self):
        response = self.refresh("not-a-jwt")

        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.data["code"], "token_not_valid")

    def test_failed_password_validation_does_not_revoke_existing_tokens(self):
        access, refresh = self.issue_tokens()
        reset = self.reset_password("123")
        self.assertEqual(reset.status_code, 400)

        self.authorize(access)
        self.assertEqual(self.api.get("/api/auth/profile/").status_code, 200)
        self.api.credentials()
        self.assertEqual(self.refresh(refresh).status_code, 200)
