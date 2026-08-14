from django.contrib.auth import authenticate
from rest_framework import serializers
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer

from clients.permissions import has_portal_staff_access


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
