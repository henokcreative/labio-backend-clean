from rest_framework import serializers
from .approval_workflow import actionable_approvals_for_client
from .models import Approval, Client, Project, ProjectFile
from .permissions import has_portal_staff_access


class PublicStaffSerializer(serializers.Serializer):
    id = serializers.IntegerField(read_only=True)
    name = serializers.CharField(source="get_full_name", read_only=True)


class ClientSerializer(serializers.ModelSerializer):
    primary_contact = PublicStaffSerializer(read_only=True)

    class Meta:
        model = Client
        fields = [
            "id",
            "name",
            "email",
            "company",
            "phone",
            "primary_contact",
            "created_at",
        ]


class ProjectSerializer(serializers.ModelSerializer):
    client_name = serializers.CharField(source="client.name", read_only=True)
    progress = serializers.SerializerMethodField()
    primary_contact = serializers.SerializerMethodField()
    primary_staff = PublicStaffSerializer(read_only=True)
    team_members = PublicStaffSerializer(many=True, read_only=True)
    client = serializers.PrimaryKeyRelatedField(queryset=Client.objects.all())
    class Meta:
        model = Project
        fields = [
            "id",
            "client",
            "title",
            "description",
            "project_type",
            "status",
            "start_date",
            "deadline",
            "budget",
            "client_name",
            "progress",
            "primary_contact",
            "primary_staff",
            "team_members",
            "created_at",
            "updated_at",
        ]

    def get_progress(self, obj):
        stages = ["lead", "planning", "pre-production", "production", "review", "approval", "completed"]
        return 100 if obj.status == "archived" else int((stages.index(obj.status) / (len(stages) - 1)) * 100)

    def get_primary_contact(self, obj):
        staff = obj.primary_staff or obj.client.primary_contact
        return PublicStaffSerializer(staff).data if staff else None


class ProjectFileSerializer(serializers.ModelSerializer):
    uploaded_by_name = serializers.CharField(source="uploaded_by.get_full_name", read_only=True)
    download_url = serializers.SerializerMethodField()
    preview_url = serializers.SerializerMethodField()
    preview_supported = serializers.BooleanField(read_only=True)
    preview_kind = serializers.CharField(read_only=True, allow_null=True)
    pending_approval = serializers.SerializerMethodField()
    file = serializers.FileField(write_only=True)
    supersedes = serializers.PrimaryKeyRelatedField(
        queryset=ProjectFile.objects.all(),
        write_only=True,
        required=False,
        allow_null=True,
    )
    supersedes_id = serializers.IntegerField(read_only=True, allow_null=True)

    def validate_supersedes(self, value):
        project = self.context.get("project")
        if project is None or value is None:
            return value
        if value.project_id != project.id:
            raise serializers.ValidationError(
                "A file can only supersede a version in the same project."
            )
        return value

    class Meta:
        model = ProjectFile
        fields = [
            "id",
            "filename",
            "display_name",
            "category",
            "content_type",
            "extension",
            "size_bytes",
            "supersedes",
            "supersedes_id",
            "uploaded_by_name",
            "created_at",
            "download_url",
            "preview_url",
            "preview_supported",
            "preview_kind",
            "pending_approval",
            "file",
        ]
        read_only_fields = [
            "filename",
            "content_type",
            "extension",
            "size_bytes",
            "uploaded_by_name",
            "created_at",
        ]

    def get_download_url(self, obj):
        return f"/api/projects/{obj.project_id}/files/{obj.id}/download/"

    def get_preview_url(self, obj):
        if not obj.preview_supported:
            return None
        return f"/api/projects/{obj.project_id}/files/{obj.id}/preview/"

    def get_pending_approval(self, obj):
        if obj.category != ProjectFile.Category.APPROVAL:
            return False
        approvals = obj.approvals.filter(
            client=obj.project.client,
            status=Approval.Status.PENDING,
        )
        request = self.context.get("request")
        if request and not has_portal_staff_access(request.user):
            try:
                client = request.user.client_profile
            except Client.DoesNotExist:
                return False
            return actionable_approvals_for_client(client).filter(file=obj).exists()
        return approvals.exists()


class ApprovalSerializer(serializers.ModelSerializer):
    project = serializers.IntegerField(source="file.project_id", read_only=True)
    file_name = serializers.CharField(source="file.filename", read_only=True)

    class Meta:
        model = Approval
        fields = ["id", "project", "file", "file_name", "status", "comment", "created_at", "updated_at"]
        read_only_fields = ["project", "file", "created_at", "updated_at"]
