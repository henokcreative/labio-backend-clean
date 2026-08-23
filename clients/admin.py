from django import forms
from django.contrib import admin, messages
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.db import transaction

from .models import Approval, Client, Project, ProjectFile
from .permissions import has_portal_staff_access, portal_staff_users
from .project_files import create_project_file, inspect_proxy_upload
from .services import send_invitation_email


@admin.action(description="Create accounts and send invitations")
def invite_clients(modeladmin, request, queryset):
    created = linked = invited = skipped = 0

    for client in queryset:
        user = client.user
        existing_users = User.objects.filter(email__iexact=client.email)

        if not user and existing_users.count() > 1:
            modeladmin.message_user(request, f"Could not create an account for {client.name}: multiple users use {client.email}.", messages.ERROR)
            skipped += 1
            continue

        try:
            with transaction.atomic():
                if user:
                    if user.is_staff or user.is_superuser or has_portal_staff_access(user):
                        raise ValueError("the linked account is a staff account")
                elif existing_users.exists():
                    user = existing_users.get()
                    if user.is_staff or user.is_superuser or has_portal_staff_access(user):
                        raise ValueError("the email belongs to a staff account")
                    client.user = user
                    client.save(update_fields=["user"])
                    linked += 1
                else:
                    username = client.email
                    if User.objects.filter(username=username).exists():
                        username = f"{client.email}_{client.id}"
                    first_name, _, last_name = client.name.partition(" ")
                    user = User.objects.create_user(username=username, email=client.email, first_name=first_name, last_name=last_name)
                    user.set_unusable_password()
                    user.save(update_fields=["password"])
                    client.user = user
                    client.save(update_fields=["user"])
                    created += 1
        except Exception as error:
            modeladmin.message_user(request, f"Could not prepare {client.name}'s account: {error}", messages.ERROR)
            skipped += 1
            continue

        if user.has_usable_password():
            modeladmin.message_user(request, f"Could not invite {client.name}: their account is already active.", messages.WARNING)
            skipped += 1
            continue

        try:
            send_invitation_email(user)
            invited += 1
        except Exception as error:
            modeladmin.message_user(request, f"Account ready for {client.name}, but invitation email failed: {error}", messages.ERROR)

    if created:
        modeladmin.message_user(request, f"{created} client account(s) created.", messages.SUCCESS)
    if linked:
        modeladmin.message_user(request, f"{linked} existing user account(s) linked.", messages.SUCCESS)
    if invited:
        modeladmin.message_user(request, f"{invited} invitation email(s) sent.", messages.SUCCESS)
    if skipped:
        modeladmin.message_user(request, f"{skipped} client(s) skipped.", messages.WARNING)


@admin.register(Client)
class ClientAdmin(admin.ModelAdmin):
    list_display = ["name", "email", "company", "primary_contact", "phone", "account_status", "created_at"]
    search_fields = ["name", "email", "company", "phone", "user__username", "user__email"]
    list_filter = ["created_at", "user__is_active"]
    ordering = ["name"]
    readonly_fields = ["created_at", "account_status"]
    actions = [invite_clients]
    fieldsets = (
        ("Client", {"fields": ("name", "email", "company", "phone", "primary_contact")} ),
        ("Account", {"fields": ("user", "account_status")} ),
        ("System", {"fields": ("created_at",)} ),
    )

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == "primary_contact":
            kwargs["queryset"] = portal_staff_users()
        return super().formfield_for_foreignkey(db_field, request, **kwargs)

    @admin.display(description="Account")
    def account_status(self, obj):
        if not obj.user:
            return "No account"
        if not obj.user.is_active:
            return "Inactive"
        if obj.user.has_usable_password():
            return "Active"
        return "Pending invitation"


class ProjectFileInlineForm(forms.ModelForm):
    upload = forms.FileField(
        required=False,
        label="File",
        help_text="For a replacement, add a new row and select the prior version under Supersedes.",
    )

    class Meta:
        model = ProjectFile
        fields = ["upload", "display_name", "category", "supersedes"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["upload"].required = not self.instance.pk
        self.fields["upload"].disabled = bool(self.instance.pk)
        if self.instance.project_id:
            self.fields["supersedes"].queryset = ProjectFile.objects.filter(
                project_id=self.instance.project_id
            )
        if self.instance.pk:
            for field_name in {"category", "supersedes"}:
                if field_name in self.fields:
                    self.fields[field_name].disabled = True

    def clean(self):
        cleaned_data = super().clean()
        if self.instance.pk:
            for field_name in {"category", "supersedes"}:
                if field_name in self.changed_data:
                    self.add_error(
                        field_name,
                        "ProjectFile versions are immutable. Upload a new version instead.",
                    )
        elif cleaned_data.get("upload"):
            try:
                inspect_proxy_upload(cleaned_data["upload"])
            except ValidationError as error:
                for message in error.messages:
                    self.add_error("upload", message)
            else:
                # The model's provider field is deliberately excluded from this form.
                # New uploads are handed to the existing upload service by save_formset.
                self.instance.file = cleaned_data["upload"]
        return cleaned_data


class ProjectFileInline(admin.TabularInline):
    model = ProjectFile
    form = ProjectFileInlineForm
    extra = 1
    fields = [
        "stored_file",
        "upload",
        "display_name",
        "category",
        "supersedes",
        "workflow_state",
        "uploaded_by",
        "created_at",
    ]
    readonly_fields = [
        "stored_file",
        "workflow_state",
        "uploaded_by",
        "created_at",
    ]

    @admin.display(description="Stored file")
    def stored_file(self, obj):
        if not obj or not obj.pk:
            return "New upload"
        return obj.filename or str(obj.file)

    @admin.display(description="State")
    def workflow_state(self, obj):
        if not obj or not obj.pk:
            return "—"
        if obj.category == ProjectFile.Category.APPROVAL:
            approval = obj.approvals.order_by("-updated_at").first()
            return approval.get_status_display() if approval else "Approval required"
        if obj.category == ProjectFile.Category.FINAL_DELIVERY:
            return "Delivered"
        if obj.category == ProjectFile.Category.PREVIEW:
            return "Preview only"
        return "Staff only"

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(Project)
class ProjectAdmin(admin.ModelAdmin):
    list_display = ["title", "client", "primary_staff", "project_type", "status", "deadline", "updated_at"]
    list_filter = ["status", "project_type"]
    search_fields = ["title", "client__name", "client__company"]
    ordering = ["-updated_at"]
    filter_horizontal = ["team_members"]
    inlines = [ProjectFileInline]

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == "primary_staff":
            kwargs["queryset"] = portal_staff_users()
        return super().formfield_for_foreignkey(db_field, request, **kwargs)

    def formfield_for_manytomany(self, db_field, request, **kwargs):
        if db_field.name == "team_members":
            kwargs["queryset"] = portal_staff_users()
        return super().formfield_for_manytomany(db_field, request, **kwargs)

    def save_formset(self, request, form, formset, change):
        instances = formset.save(commit=False)

        for instance in instances:
            if isinstance(instance, ProjectFile) and instance._state.adding:
                create_project_file(
                    project=instance.project,
                    uploaded_by=request.user,
                    uploaded_file=instance.file,
                    category=instance.category,
                    display_name=instance.display_name,
                    supersedes=instance.supersedes,
                )
                continue
            instance.save(update_fields=["display_name"])


@admin.register(Approval)
class ApprovalAdmin(admin.ModelAdmin):
    list_display = ["project", "file", "client", "status", "updated_at"]
    list_filter = ["status"]
    search_fields = ["project__title", "file__filename", "client__name"]
    readonly_fields = ["project", "file", "client", "created_at", "updated_at"]

    def has_add_permission(self, request):
        return False
