from time import time

from cloudinary.utils import private_download_url
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db.models import F
from django.http import Http404
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError as ApiValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from messaging.models import Conversation, Message
from messaging.serializers import MessageSerializer
from .approval_workflow import actionable_approvals_for_client
from .models import Approval, Client, Project, ProjectFile
from .permissions import (
    IsPortalStaff,
    IsPortalStaffOrClient,
    IsStaffOrOwnClientData,
    has_portal_staff_access,
    portal_staff_users,
)
from .project_files import create_project_file
from .serializers import ApprovalSerializer, ProjectFileSerializer, ProjectSerializer


class ProjectViewSet(viewsets.ModelViewSet):
    serializer_class = ProjectSerializer
    permission_classes = [IsAuthenticated, IsStaffOrOwnClientData]

    def get_queryset(self):
        queryset = Project.objects.select_related(
            "client",
            "client__user",
            "client__primary_contact",
            "primary_staff",
        ).prefetch_related("team_members")
        return queryset if has_portal_staff_access(self.request.user) else queryset.filter(client__user=self.request.user)

    def get_permissions(self):
        if self.action in {"create", "update", "partial_update", "destroy"} or (
            self.action == "files" and self.request.method == "POST"
        ):
            return [IsAuthenticated(), IsPortalStaff()]
        return super().get_permissions()

    @action(detail=True, methods=["get", "post"], url_path="files")
    def files(self, request, pk=None):
        project = self.get_object()
        if request.method == "POST":
            serializer = ProjectFileSerializer(
                data=request.data,
                context={"request": request, "project": project},
            )
            serializer.is_valid(raise_exception=True)
            validated_data = serializer.validated_data
            try:
                project_file = create_project_file(
                    project=project,
                    uploaded_by=request.user,
                    uploaded_file=validated_data["file"],
                    category=validated_data["category"],
                    display_name=validated_data.get("display_name", ""),
                    supersedes=validated_data.get("supersedes"),
                )
            except DjangoValidationError as error:
                detail = getattr(error, "message_dict", None) or {
                    "file": error.messages
                }
                raise ApiValidationError(detail) from error
            return Response(ProjectFileSerializer(project_file, context={"request": request}).data, status=status.HTTP_201_CREATED)
        files = project.files.all()
        if not has_portal_staff_access(request.user):
            files = files.exclude(category=ProjectFile.Category.RAW)
        return Response(ProjectFileSerializer(files, many=True, context={"request": request}).data)

    @action(detail=True, methods=["get"], url_path=r"files/(?P<file_id>[^/.]+)/download")
    def download_file(self, request, pk=None, file_id=None):
        project = self.get_object()
        try:
            project_file = project.files.get(pk=file_id)
        except ProjectFile.DoesNotExist as exc:
            raise Http404 from exc
        if not has_portal_staff_access(request.user) and project_file.category == ProjectFile.Category.RAW:
            return Response({"detail": "Not found."}, status=status.HTTP_404_NOT_FOUND)
        return Response({"url": self._signed_file_url(project_file, attachment=True)})

    @action(detail=True, methods=["get"], url_path=r"files/(?P<file_id>[^/.]+)/preview")
    def preview_file(self, request, pk=None, file_id=None):
        project = self.get_object()
        try:
            project_file = project.files.get(pk=file_id)
        except ProjectFile.DoesNotExist as exc:
            raise Http404 from exc
        if project_file.category == ProjectFile.Category.RAW and not has_portal_staff_access(request.user):
            return Response({"detail": "Not found."}, status=status.HTTP_404_NOT_FOUND)
        if not project_file.preview_supported:
            return Response(
                {"detail": "This file cannot be previewed in the browser. Download it instead."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        return Response({"url": self._signed_file_url(project_file, attachment=False)})

    @staticmethod
    def _signed_file_url(project_file, attachment):
        resource = project_file.file
        public_id = project_file.provider_public_id or resource.public_id
        resource_type = project_file.provider_resource_type or resource.resource_type
        delivery_type = project_file.provider_delivery_type or resource.type
        resource_format = project_file.provider_format or resource.format

        if resource_type == ProjectFile.ProviderResourceType.RAW:
            extension_value = resource_format or project_file.effective_extension
            extension = f".{extension_value}" if extension_value else ""
            if not public_id.lower().endswith(extension.lower()):
                public_id = f"{public_id}{extension}"
            resource_format = None

        options = {
            "resource_type": resource_type,
            "type": delivery_type,
            "expires_at": int(time()) + 300,
        }
        if attachment:
            options["attachment"] = True
        return private_download_url(public_id, resource_format, **options)

    @action(detail=True, methods=["post"], url_path="approve")
    def approve(self, request, pk=None):
        project = self.get_object()
        if has_portal_staff_access(request.user):
            return Response({"detail": "Only the client can approve deliverables."}, status=status.HTTP_403_FORBIDDEN)
        file_id = request.data.get("file_id")
        try:
            approval = actionable_approvals_for_client(project.client).get(
                file_id=file_id,
                file__project=project,
            )
        except Approval.DoesNotExist:
            return Response({"detail": "Pending approval not found."}, status=status.HTTP_404_NOT_FOUND)
        status_value = request.data.get("status")
        if status_value not in {Approval.Status.APPROVED, Approval.Status.CHANGES_REQUESTED}:
            return Response({"status": ["Use approved or changes_requested."]}, status=status.HTTP_400_BAD_REQUEST)
        approval.status = status_value
        approval.comment = request.data.get("comment", "")
        approval.save(update_fields=["status", "comment", "updated_at"])
        if status_value == Approval.Status.CHANGES_REQUESTED:
            project.status = "review"
        elif actionable_approvals_for_client(project.client).filter(
            file__project=project
        ).exists():
            project.status = "approval"
        else:
            project.status = "completed"
        project.save(update_fields=["status", "updated_at"])
        return Response(ApprovalSerializer(approval).data)


class PortalMessageViewSet(viewsets.ViewSet):
    permission_classes = [IsAuthenticated, IsPortalStaffOrClient]

    def list(self, request):
        messages = Message.objects.select_related("conversation", "sender", "conversation__project").order_by("-created_at")
        mark_incoming_read = True
        if has_portal_staff_access(request.user):
            project_id = request.query_params.get("project")
            if project_id:
                messages = messages.filter(conversation__project_id=project_id)
            else:
                mark_incoming_read = False
        else:
            messages = messages.filter(conversation__client=request.user)
            project_id = request.query_params.get("project")
            if project_id:
                messages = messages.filter(conversation__project_id=project_id)
        if mark_incoming_read:
            unread = messages.filter(is_read=False)
            if has_portal_staff_access(request.user):
                unread.filter(sender_id=F("conversation__client_id")).update(is_read=True)
            else:
                unread.exclude(sender=request.user).update(is_read=True)
        latest_messages = list(messages[:50])
        latest_messages.reverse()
        return Response(MessageSerializer(latest_messages, many=True).data)

    def create(self, request):
        project_id = request.data.get("project")
        content = str(request.data.get("content", "")).strip()
        if not project_id or not content:
            return Response({"detail": "project and content are required."}, status=status.HTTP_400_BAD_REQUEST)
        if len(content) > 10000:
            return Response({"content": ["Ensure this field has no more than 10000 characters."]}, status=status.HTTP_400_BAD_REQUEST)
        try:
            project = Project.objects.get(pk=project_id)
        except Project.DoesNotExist:
            return Response({"detail": "Project not found."}, status=status.HTTP_404_NOT_FOUND)
        if not has_portal_staff_access(request.user) and project.client.user_id != request.user.id:
            return Response({"detail": "Not found."}, status=status.HTTP_404_NOT_FOUND)
        client_user = project.client.user
        if not client_user:
            return Response({"detail": "This project has no portal client account."}, status=status.HTTP_400_BAD_REQUEST)
        conversation = Conversation.objects.filter(
            project=project,
            client=client_user,
        ).order_by("-updated_at").first()
        if conversation is None:
            conversation = Conversation.objects.create(
                project=project,
                client=client_user,
                subject=project.title,
                assigned_staff=(
                    request.user if has_portal_staff_access(request.user) else None
                ),
            )
        if has_portal_staff_access(request.user):
            incoming = conversation.messages.filter(
                sender=client_user,
                is_read=False,
            )
        else:
            incoming = conversation.messages.filter(is_read=False).exclude(
                sender=request.user
            )
        incoming.update(is_read=True)
        message = Message.objects.create(conversation=conversation, sender=request.user, body=content)
        conversation.save(update_fields=["updated_at"])
        return Response(MessageSerializer(message).data, status=status.HTTP_201_CREATED)


class DashboardViewSet(viewsets.ViewSet):
    permission_classes = [IsAuthenticated, IsPortalStaffOrClient]

    def list(self, request):
        if has_portal_staff_access(request.user):
            staff_ids = portal_staff_users().values("pk")
            return Response(
                {
                    "unread_client_messages": Message.objects.filter(
                        is_read=False
                    ).exclude(sender_id__in=staff_ids).count()
                }
            )
        try:
            client = request.user.client_profile
        except Client.DoesNotExist:
            return Response({"detail": "Client profile not found."}, status=status.HTTP_404_NOT_FOUND)
        projects = Project.objects.filter(client=client).select_related(
            "client__primary_contact",
            "primary_staff",
        ).prefetch_related("team_members").exclude(status__in=["completed", "archived"])
        files = ProjectFile.objects.filter(
            project__client=client,
            category=ProjectFile.Category.FINAL_DELIVERY,
        ).select_related("project")
        approvals = actionable_approvals_for_client(client).select_related(
            "file",
            "file__project",
        )
        all_messages = Message.objects.filter(conversation__client=request.user)
        messages = all_messages.exclude(sender=request.user).select_related(
            "conversation",
            "conversation__project",
            "sender",
        ).order_by("-created_at")
        return Response(
            {
                "client": {"name": client.name, "company": client.company},
                "active_project_count": projects.count(),
                "message_count": all_messages.count(),
                "pending_approval_count": approvals.count(),
                "delivered_file_count": files.count(),
                "active_projects": ProjectSerializer(projects, many=True).data,
                "pending_approvals": ApprovalSerializer(approvals, many=True).data,
                "latest_messages": MessageSerializer(messages[:5], many=True).data,
                "latest_files": ProjectFileSerializer(
                    files[:5],
                    many=True,
                    context={"request": request},
                ).data,
            }
        )
