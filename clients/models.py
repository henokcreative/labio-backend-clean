from django.db import models
from django.db.models import Q
from django.conf import settings
from django.core.exceptions import ValidationError
from django.db.models.signals import post_save
from django.db.models.signals import m2m_changed
from django.dispatch import receiver
from cloudinary.models import CloudinaryField

from .permissions import has_portal_staff_access


def validate_portal_staff(user, field_name):
    if user is not None and not has_portal_staff_access(user):
        raise ValidationError({field_name: "Select an active Portal Staff user."})


class Client(models.Model):
    name = models.CharField(max_length=100)
    email = models.EmailField(unique=True)
    company = models.CharField(max_length=100, blank=True)
    phone = models.CharField(max_length=20, blank=True)

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="client_profile",
    )

    primary_contact = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="primary_contact_clients",
    )

    created_at = models.DateTimeField(auto_now_add=True)

    def clean(self):
        super().clean()
        validate_portal_staff(self.primary_contact, "primary_contact")

    def save(self, *args, **kwargs):
        validate_portal_staff(self.primary_contact, "primary_contact")
        super().save(*args, **kwargs)


    def __str__(self):
        return self.name



class Project(models.Model):

    STATUS_CHOICES = [
        ("lead", "Lead"),
        ("planning", "Planning"),
        ("pre-production", "Pre-production"),
        ("production", "Production"),
        ("review", "Review"),
        ("approval", "Approval"),
        ("completed", "Completed"),
        ("archived", "Archived"),
    ]


    client = models.ForeignKey(
        Client,
        on_delete=models.CASCADE,
        related_name="projects"
    )

    primary_staff = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="primary_staff_projects",
    )

    team_members = models.ManyToManyField(
        settings.AUTH_USER_MODEL,
        blank=True,
        related_name="team_projects",
    )


    title = models.CharField(
        max_length=200
    )

    description = models.TextField(
        blank=True
    )

    project_type = models.CharField(max_length=100, blank=True)


    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default="planning"
    )


    deadline = models.DateField(
        null=True,
        blank=True
    )
    start_date = models.DateField(null=True, blank=True)
    budget = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)


    created_at = models.DateTimeField(
        auto_now_add=True
    )


    updated_at = models.DateTimeField(
        auto_now=True
    )

    class Meta:
        permissions = [
            (
                "access_private_portal_data",
                "Can access private LaBio client portal data",
            ),
        ]

    def clean(self):
        super().clean()
        validate_portal_staff(self.primary_staff, "primary_staff")

    def save(self, *args, **kwargs):
        validate_portal_staff(self.primary_staff, "primary_staff")
        super().save(*args, **kwargs)


    def __str__(self):
        return self.title


@receiver(m2m_changed, sender=Project.team_members.through)
def validate_project_team_members(sender, instance, action, pk_set, **kwargs):
    if action != "pre_add" or not pk_set:
        return

    user_model = Project.team_members.field.remote_field.model
    if any(
        not has_portal_staff_access(user)
        for user in user_model.objects.filter(pk__in=pk_set)
    ):
        raise ValidationError(
            {"team_members": "Only active Portal Staff users may join a project team."}
        )


class ProjectFile(models.Model):
    class Category(models.TextChoices):
        RAW = "raw", "Raw"
        PREVIEW = "preview", "Preview"
        APPROVAL = "approval", "Approval"
        FINAL_DELIVERY = "final_delivery", "Final delivery"

    class StorageProvider(models.TextChoices):
        CLOUDINARY = "cloudinary", "Cloudinary"

    class ProviderResourceType(models.TextChoices):
        IMAGE = "image", "Image"
        VIDEO = "video", "Video"
        RAW = "raw", "Raw"

    class ProviderDeliveryType(models.TextChoices):
        PRIVATE = "private", "Private"
        AUTHENTICATED = "authenticated", "Authenticated"
        UPLOAD = "upload", "Legacy public upload"

    PREVIEW_KINDS = {
        "jpg": "image",
        "jpeg": "image",
        "png": "image",
        "webp": "image",
        "pdf": "pdf",
        "mp4": "video",
        "webm": "video",
        "mp3": "audio",
        "wav": "audio",
    }

    IMMUTABLE_FIELDS = (
        "project_id",
        "uploaded_by_id",
        "file",
        "filename",
        "category",
        "content_type",
        "extension",
        "size_bytes",
        "storage_provider",
        "provider_asset_id",
        "provider_public_id",
        "provider_resource_type",
        "provider_delivery_type",
        "provider_format",
        "provider_version",
        "supersedes_id",
    )

    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name="files")
    uploaded_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="uploaded_project_files")
    # Files are private Cloudinary assets. Views authorize every temporary URL.
    file = CloudinaryField(
        "file",
        resource_type="raw",
        type="private",
        folder="projects",
    )
    filename = models.CharField(max_length=255)
    display_name = models.CharField(max_length=255, blank=True)
    category = models.CharField(max_length=20, choices=Category.choices)
    content_type = models.CharField(max_length=255, blank=True)
    extension = models.CharField(max_length=32, blank=True)
    size_bytes = models.PositiveBigIntegerField(null=True, blank=True)
    storage_provider = models.CharField(
        max_length=32,
        choices=StorageProvider.choices,
        default=StorageProvider.CLOUDINARY,
    )
    provider_asset_id = models.CharField(max_length=255, blank=True)
    provider_public_id = models.CharField(max_length=512, blank=True)
    provider_resource_type = models.CharField(
        max_length=16,
        choices=ProviderResourceType.choices,
        blank=True,
    )
    provider_delivery_type = models.CharField(
        max_length=20,
        choices=ProviderDeliveryType.choices,
        blank=True,
    )
    provider_format = models.CharField(max_length=32, blank=True)
    provider_version = models.PositiveBigIntegerField(null=True, blank=True)
    supersedes = models.ForeignKey(
        "self",
        on_delete=models.RESTRICT,
        null=True,
        blank=True,
        related_name="revisions",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["storage_provider", "provider_asset_id"],
                condition=~Q(provider_asset_id=""),
                name="unique_project_file_provider_asset",
            ),
        ]

    @property
    def effective_extension(self):
        if self.extension:
            return self.extension.lower().lstrip(".")
        if "." not in self.filename:
            return ""
        return self.filename.rsplit(".", 1)[-1].lower()

    @property
    def preview_kind(self):
        if self.category not in {
            self.Category.PREVIEW,
            self.Category.APPROVAL,
        }:
            return None
        return self.PREVIEW_KINDS.get(self.effective_extension)

    @property
    def preview_supported(self):
        return self.preview_kind is not None

    def clean(self):
        super().clean()
        if not self.supersedes_id:
            return
        if self.pk and self.supersedes_id == self.pk:
            raise ValidationError({"supersedes": "A file cannot supersede itself."})
        previous = type(self).objects.filter(pk=self.supersedes_id).first()
        if previous is None:
            raise ValidationError({"supersedes": "The superseded file does not exist."})
        if previous.project_id != self.project_id:
            raise ValidationError(
                {"supersedes": "A file can only supersede a version in the same project."}
            )
        if previous.category != self.category:
            raise ValidationError(
                {"supersedes": "A file can only supersede a version in the same category."}
            )

    def save(self, *args, **kwargs):
        if not self.filename and self.file:
            self.filename = self.file.name.rsplit("/", 1)[-1]
        self.clean()
        if self.pk:
            original = type(self).objects.get(pk=self.pk)
            changed = []
            for field_name in self.IMMUTABLE_FIELDS:
                current_value = getattr(self, field_name)
                original_value = getattr(original, field_name)
                if field_name == "file":
                    current_value = str(current_value)
                    original_value = str(original_value)
                if current_value != original_value:
                    changed.append(field_name.removesuffix("_id"))
            if changed:
                raise ValidationError(
                    {
                        field_name: "ProjectFile versions are immutable. Upload a new version instead."
                        for field_name in changed
                    }
                )
        super().save(*args, **kwargs)

    def __str__(self):
        return self.display_name or self.filename


class Approval(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        APPROVED = "approved", "Approved"
        CHANGES_REQUESTED = "changes_requested", "Changes requested"
        SUPERSEDED = "superseded", "Superseded"

    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name="approvals")
    file = models.ForeignKey(ProjectFile, on_delete=models.CASCADE, related_name="approvals")
    client = models.ForeignKey(Client, on_delete=models.CASCADE, related_name="approvals")
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)
    comment = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["file", "client"], name="unique_file_approval_per_client")]
        ordering = ["-updated_at"]


@receiver(post_save, sender=ProjectFile)
def sync_project_file_approval(sender, instance, created, **kwargs):
    if not created:
        return
    if instance.category == ProjectFile.Category.APPROVAL:
        if instance.supersedes_id:
            Approval.objects.filter(
                file_id=instance.supersedes_id,
                status=Approval.Status.PENDING,
            ).update(status=Approval.Status.SUPERSEDED)
        Approval.objects.get_or_create(
            project=instance.project,
            file=instance,
            client=instance.project.client,
        )
        if instance.project.status != "approval":
            instance.project.status = "approval"
            instance.project.save(update_fields=["status", "updated_at"])
