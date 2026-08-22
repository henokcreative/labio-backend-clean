from django.urls import path

from .views import (
    AcceptInvitationView,
    ValidateInvitationView,
    ClientProfileView,
    ClientProjectsView,
    PasswordResetConfirmView,
    PasswordResetRequestView,
)


urlpatterns = [

    path(
        "password-reset/request/",
        PasswordResetRequestView.as_view(),
        name="password-reset-request",
    ),

    path(
        "password-reset/confirm/",
        PasswordResetConfirmView.as_view(),
        name="password-reset-confirm",
    ),

    path(
        "invitations/validate/",
        ValidateInvitationView.as_view(),
        name="validate-invitation",
    ),

    path(
        "invitations/accept/",
        AcceptInvitationView.as_view(),
        name="accept-invitation",
    ),

    path(
        "profile/",
        ClientProfileView.as_view()
    ),

path(
    "projects/",
    ClientProjectsView.as_view(),
    name="client-projects"
),

]
