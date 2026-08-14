from django.contrib.auth import get_user_model
from django.db.models import Q
from rest_framework.permissions import BasePermission


PORTAL_STAFF_PERMISSION = "clients.access_private_portal_data"


def has_portal_staff_access(user):
    return bool(
        user
        and user.is_authenticated
        and user.is_active
        and (user.is_superuser or user.has_perm(PORTAL_STAFF_PERMISSION))
    )


def portal_staff_users():
    permission_filter = Q(
        user_permissions__codename="access_private_portal_data",
        user_permissions__content_type__app_label="clients",
    ) | Q(
        groups__permissions__codename="access_private_portal_data",
        groups__permissions__content_type__app_label="clients",
    )
    return (
        get_user_model()
        .objects.filter(is_active=True)
        .filter(Q(is_superuser=True) | permission_filter)
        .distinct()
    )


class IsPortalStaff(BasePermission):
    def has_permission(self, request, view):
        return has_portal_staff_access(request.user)


class IsPortalStaffOrClient(BasePermission):
    def has_permission(self, request, view):
        user = request.user
        return bool(
            user
            and user.is_authenticated
            and user.is_active
            and (
                has_portal_staff_access(user)
                or hasattr(user, "client_profile")
            )
        )


class IsStaffOrOwnClientData(BasePermission):
    def has_permission(self, request, view):
        return IsPortalStaffOrClient().has_permission(request, view)

    def has_object_permission(self, request, view, obj):
        if has_portal_staff_access(request.user):
            return True
        project = getattr(obj, "project", obj)
        return getattr(project, "client", None) and project.client.user_id == request.user.id
