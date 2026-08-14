from django.contrib.auth import password_validation
from django.contrib.auth.models import User
from django.contrib.auth.tokens import default_token_generator
from django.core.exceptions import ValidationError
from django.utils.encoding import force_str
from django.utils.http import urlsafe_base64_decode
from .serializers import ProjectSerializer

from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.authentication import JWTAuthentication

from .models import Client, Project
from .permissions import has_portal_staff_access
from .serializers import ClientSerializer, ProjectSerializer


def invited_user(uid, token):
    """Resolve a valid invitation without allowing staff-account activation."""

    try:
        user_id = force_str(urlsafe_base64_decode(uid))
        user = User.objects.get(pk=user_id)
    except (
        TypeError,
        ValueError,
        OverflowError,
        User.DoesNotExist,
    ):
        return None

    if (
        user.is_staff
        or user.is_superuser
        or has_portal_staff_access(user)
        or not Client.objects.filter(user=user).exists()
    ):
        return None

    return (
        user
        if default_token_generator.check_token(user, token)
        else None
    )


class ValidateInvitationView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []

    def get(self, request):
        user = invited_user(
            request.query_params.get("uid"),
            request.query_params.get("token"),
        )

        if not user:
            return Response(
                {
                    "detail": (
                        "This invitation link is invalid or has expired."
                    )
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        return Response(
            {
                "email": user.email,
                "name": user.get_full_name() or user.username,
            }
        )


class AcceptInvitationView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []

    def post(self, request):
        user = invited_user(
            request.data.get("uid"),
            request.data.get("token"),
        )

        password = request.data.get("password")
        confirmation = request.data.get("password_confirmation")

        if not user:
            return Response(
                {
                    "detail": (
                        "This invitation link is invalid or has expired."
                    )
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        if not password:
            return Response(
                {"password": ["This field is required."]},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if password != confirmation:
            return Response(
                {
                    "password_confirmation": [
                        "Passwords do not match."
                    ]
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            password_validation.validate_password(
                password,
                user,
            )
        except ValidationError as error:
            return Response(
                {"password": list(error.messages)},
                status=status.HTTP_400_BAD_REQUEST,
            )

        user.set_password(password)
        user.save(update_fields=["password"])

        return Response(
            {
                "detail": (
                    "Your password has been set. "
                    "You can now sign in."
                )
            }
        )


class ClientProfileView(APIView):
    permission_classes = [IsAuthenticated]
    authentication_classes = [JWTAuthentication]

    def get(self, request):
        try:
            client = request.user.client_profile
        except Client.DoesNotExist:
            return Response(
                {"detail": "Client profile not found"},
                status=status.HTTP_404_NOT_FOUND,
            )

        serializer = ClientSerializer(client)

        return Response(serializer.data)


class ClientProjectsView(APIView):

    permission_classes = [IsAuthenticated]
    authentication_classes = [JWTAuthentication]


    def get(self, request):

        try:
            client = request.user.client_profile
        except Client.DoesNotExist:
            return Response(
                {"detail": "Client profile not found"},
                status=404
            )


        projects = Project.objects.filter(
            client=client
        ).order_by("-created_at")


        serializer = ProjectSerializer(
            projects,
            many=True
        )

        return Response(serializer.data)
