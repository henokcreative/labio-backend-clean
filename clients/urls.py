from django.urls import path

from .views import (
    AcceptInvitationView,
    ValidateInvitationView,
    ClientProfileView,
    ClientProjectsView,
)


urlpatterns = [

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
