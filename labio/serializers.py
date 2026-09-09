from django.contrib.auth import authenticate, get_user_model
from django.utils.crypto import constant_time_compare
from rest_framework import serializers
from rest_framework_simplejwt.exceptions import InvalidToken
from rest_framework_simplejwt.serializers import (
    TokenObtainPairSerializer,
    TokenRefreshSerializer,
)
from rest_framework_simplejwt.settings import api_settings
from rest_framework_simplejwt.utils import get_md5_hash_password

from clients.permissions import has_portal_staff_access


class PasswordBoundTokenRefreshSerializer(TokenRefreshSerializer):
    """Reject refresh tokens issued before the user's current password."""

    default_error_messages = {
        **TokenRefreshSerializer.default_error_messages,
        "invalid_token": "Token is invalid or expired",
    }

    def validate(self, attrs):
        refresh = self.token_class(attrs["refresh"])
        user_id = refresh.payload.get(api_settings.USER_ID_CLAIM)

        try:
            user = get_user_model().objects.get(
                **{api_settings.USER_ID_FIELD: user_id}
            )
        except (TypeError, ValueError, get_user_model().DoesNotExist):
            self._reject_token()

        if not api_settings.USER_AUTHENTICATION_RULE(user):
            self._reject_token()

        token_password_digest = refresh.payload.get(
            api_settings.REVOKE_TOKEN_CLAIM
        )
        current_password_digest = get_md5_hash_password(user.password)
        if not isinstance(token_password_digest, str) or not constant_time_compare(
            token_password_digest,
            current_password_digest,
        ):
            self._reject_token()

        try:
            return super().validate(attrs)
        except get_user_model().DoesNotExist:
            # Keep a user deletion racing this validation on the generic path.
            self._reject_token()

    def _reject_token(self):
        raise InvalidToken(self.error_messages["invalid_token"])


class CustomTokenObtainPairSerializer(TokenObtainPairSerializer):
    # SimpleJWT builds its credential field from this attribute in __init__.
    # Without this override it adds a required `username` field before
    # validate() is called.
    username_field = "email"

    def validate(self, attrs):

        email = attrs.get("email")
        password = attrs.get("password")


        user = authenticate(
            username=email,
            password=password
        )


        if not user:
            raise serializers.ValidationError(
                {
                    "non_field_errors": [
                        "Invalid email or password"
                    ]
                }
            )


        refresh = self.get_token(user)


        data = {
            "refresh": str(refresh),
            "access": str(refresh.access_token),
        }


        data["is_staff"] = user.is_staff
        data["is_portal_staff"] = has_portal_staff_access(user)


        return data



    @classmethod
    def get_token(cls, user):

        token = super().get_token(user)

        token["is_staff"] = user.is_staff
        token["is_portal_staff"] = has_portal_staff_access(user)

        return token
