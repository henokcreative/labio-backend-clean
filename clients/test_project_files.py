import io
import zipfile
from unittest.mock import patch

from cloudinary import CloudinaryResource
from django.contrib import admin
from django.contrib.auth.models import Permission, User
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import SimpleTestCase, TestCase, override_settings
from rest_framework.test import APIClient

from .admin import ProjectFileInline, ProjectFileInlineForm
from .models import Approval, Client, Project, ProjectFile
from .permissions import PORTAL_STAFF_PERMISSION
from .portal_views import ProjectViewSet
from .project_files import (
    CloudinaryProjectFileProvider,
    StoredProjectFile,
    create_project_file,
    inspect_proxy_upload,
)


def uploaded_file(name, content, content_type):
    return SimpleUploadedFile(name, content, content_type=content_type)


def zip_bytes(entries=None):
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w") as archive:
        for name, content in (entries or {"deliverable.txt": "hello"}).items():
            archive.writestr(name, content)
    return output.getvalue()


FILE_SAMPLES = {
    "photo.jpg": (b"\xff\xd8\xff\xe0jpeg", "image/jpeg", "image", "authenticated", "image"),
    "graphic.png": (b"\x89PNG\r\n\x1a\npng", "image/png", "image", "authenticated", "image"),
    "document.pdf": (b"%PDF-1.7\npdf", "application/pdf", "image", "authenticated", "pdf"),
    "review.mp4": (b"\x00\x00\x00\x18ftypisomvideo", "video/mp4", "video", "authenticated", "video"),
    "track.mp3": (b"ID3\x04\x00\x00audio", "audio/mpeg", "video", "authenticated", "audio"),
    "source.zip": (zip_bytes(), "application/zip", "raw", "private", None),
}


class ProjectFileInspectionTests(SimpleTestCase):
    def test_required_media_types_are_classified_from_mime_extension_and_signature(self):
        for name, (content, mime, resource_type, delivery_type, preview_kind) in FILE_SAMPLES.items():
            with self.subTest(name=name):
                inspected = inspect_proxy_upload(uploaded_file(name, content, mime))
                self.assertEqual(inspected.rule.resource_type, resource_type)
                self.assertEqual(inspected.rule.delivery_type, delivery_type)
                self.assertEqual(inspected.rule.preview_kind, preview_kind)

    def test_unicode_and_spaces_are_preserved_without_using_them_as_provider_ids(self):
        inspected = inspect_proxy_upload(
            uploaded_file(
                "../Hääkuva final 版本.png",
                b"\x89PNG\r\n\x1a\npng",
                "image/png",
            )
        )
        self.assertEqual(inspected.filename, "Hääkuva final 版本.png")
        self.assertEqual(inspected.extension, "png")

    def test_declared_mime_must_match_extension(self):
        with self.assertRaisesMessage(ValidationError, "declared content type"):
            inspect_proxy_upload(
                uploaded_file("picture.png", b"\x89PNG\r\n\x1a\npng", "application/pdf")
            )

    def test_signature_must_match_extension(self):
        with self.assertRaisesMessage(ValidationError, "file contents"):
            inspect_proxy_upload(uploaded_file("picture.png", b"%PDF-1.7", "image/png"))

    def test_ooxml_container_must_match_the_declared_office_extension(self):
        docx = zip_bytes({"[Content_Types].xml": "types", "word/document.xml": "doc"})
        inspected = inspect_proxy_upload(
            uploaded_file(
                "brief.docx",
                docx,
                "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            )
        )
        self.assertEqual(inspected.extension, "docx")
        with self.assertRaisesMessage(ValidationError, "file contents"):
            inspect_proxy_upload(uploaded_file("brief.zip", docx, "application/zip"))

    @override_settings(PROJECT_FILE_PROXY_UPLOAD_MAX_BYTES=8)
    def test_proxy_upload_limit_is_configurable_validation_not_a_model_field_limit(self):
        with self.assertRaisesMessage(ValidationError, "temporary server upload path"):
            inspect_proxy_upload(
                uploaded_file("large.png", b"\x89PNG\r\n\x1a\nlarge", "image/png")
            )


class CloudinaryProviderTests(SimpleTestCase):
    def cloudinary_response(self, expected_size):
        def response(file_object, **options):
            file_format = options["public_id"].rsplit(".", 1)[-1]
            file_format = "png" if options["resource_type"] == "image" else file_format
            return CloudinaryResource(
                options["public_id"],
                version=17,
                format=file_format,
                type=options["type"],
                resource_type=options["resource_type"],
                metadata={
                    "asset_id": "provider-asset-id",
                    "public_id": options["public_id"],
                    "version": 17,
                    "format": file_format,
                    "type": options["type"],
                    "resource_type": options["resource_type"],
                    "bytes": expected_size,
                },
            )

        return response

    @patch("clients.project_files.upload_resource")
    def test_generated_public_ids_do_not_contain_user_filenames(self, upload_resource):
        file_object = uploaded_file(
            "Client Name secret concept.png",
            b"\x89PNG\r\n\x1a\npng",
            "image/png",
        )
        inspected = inspect_proxy_upload(file_object)
        upload_resource.side_effect = self.cloudinary_response(file_object.size)

        stored = CloudinaryProjectFileProvider().upload(file_object, inspected, project_id=42)

        self.assertRegex(stored.public_id, r"^projects/42/[0-9a-f]{32}$")
        self.assertNotIn("Client", stored.public_id)
        self.assertEqual(upload_resource.call_args.kwargs["resource_type"], "image")
        self.assertEqual(upload_resource.call_args.kwargs["type"], "authenticated")

    @patch("clients.project_files.upload_resource")
    def test_raw_public_id_contains_only_generated_id_and_exact_extension(self, upload_resource):
        file_object = uploaded_file("private source.zip", zip_bytes(), "application/zip")
        inspected = inspect_proxy_upload(file_object)
        upload_resource.side_effect = self.cloudinary_response(file_object.size)

        stored = CloudinaryProjectFileProvider().upload(file_object, inspected, project_id=7)

        self.assertRegex(stored.public_id, r"^projects/7/[0-9a-f]{32}\.zip$")
        self.assertEqual(upload_resource.call_args.kwargs["resource_type"], "raw")
        self.assertEqual(upload_resource.call_args.kwargs["type"], "private")
        self.assertTrue(stored.resource.get_prep_value().endswith(".zip"))
        self.assertFalse(stored.resource.get_prep_value().endswith(".zip.zip"))

    @patch("clients.project_files.destroy")
    @patch("clients.project_files.upload_resource")
    def test_provider_metadata_is_verified_before_a_database_row_can_be_created(self, upload_resource, destroy):
        file_object = uploaded_file("graphic.png", b"\x89PNG\r\n\x1a\npng", "image/png")
        inspected = inspect_proxy_upload(file_object)
        upload_resource.return_value = CloudinaryResource(
            "wrong-public-id",
            version=1,
            format="png",
            type="upload",
            resource_type="image",
            metadata={"asset_id": "asset", "bytes": file_object.size},
        )

        with self.assertRaisesMessage(ValidationError, "delivery type"):
            CloudinaryProjectFileProvider().upload(file_object, inspected, project_id=1)
        destroy.assert_called_once_with("wrong-public-id", resource_type="image", type="upload", invalidate=True)


class FakeProjectFileProvider:
    name = ProjectFile.StorageProvider.CLOUDINARY

    def __init__(self):
        self.uploaded = []
        self.deleted = []

    def upload(self, uploaded_file, inspected_file, project_id):
        suffix = f".{inspected_file.extension}" if inspected_file.rule.resource_type == "raw" else ""
        public_id = f"projects/{project_id}/fake{len(self.uploaded) + 1}{suffix}"
        provider_format = "" if inspected_file.rule.resource_type == "raw" else inspected_file.extension
        resource = CloudinaryResource(
            public_id,
            version=len(self.uploaded) + 1,
            format=provider_format or None,
            type=inspected_file.rule.delivery_type,
            resource_type=inspected_file.rule.resource_type,
        )
        stored = StoredProjectFile(
            resource=resource,
            asset_id=f"asset-{len(self.uploaded) + 1}",
            public_id=public_id,
            resource_type=inspected_file.rule.resource_type,
            delivery_type=inspected_file.rule.delivery_type,
            provider_format=provider_format,
            version=len(self.uploaded) + 1,
            size_bytes=inspected_file.size_bytes,
        )
        self.uploaded.append(stored)
        return stored

    def delete(self, stored_file):
        self.deleted.append(stored_file)


class ProjectFileVersionTests(TestCase):
    def setUp(self):
        self.staff = User.objects.create_user("staff", password="Password!123")
        self.client_user = User.objects.create_user("client", password="Password!123")
        self.client = Client.objects.create(
            name="Client", email="client@example.com", user=self.client_user
        )
        self.project = Project.objects.create(client=self.client, title="Project")
        self.provider = FakeProjectFileProvider()

    def create_file(self, name="review.pdf", category=ProjectFile.Category.APPROVAL, supersedes=None):
        return create_project_file(
            project=self.project,
            uploaded_by=self.staff,
            uploaded_file=uploaded_file(name, b"%PDF-1.7\nfile", "application/pdf"),
            category=category,
            supersedes=supersedes,
            provider=self.provider,
        )

    def test_service_persists_provider_neutral_metadata_and_exact_approval(self):
        project_file = self.create_file()
        approval = Approval.objects.get(file=project_file)

        self.assertEqual(project_file.filename, "review.pdf")
        self.assertEqual(project_file.content_type, "application/pdf")
        self.assertEqual(project_file.extension, "pdf")
        self.assertEqual(project_file.provider_asset_id, "asset-1")
        self.assertEqual(project_file.provider_public_id, f"projects/{self.project.id}/fake1")
        self.assertEqual(project_file.provider_resource_type, "image")
        self.assertEqual(project_file.provider_delivery_type, "authenticated")
        self.assertEqual(approval.client, self.client)
        self.assertEqual(approval.project, self.project)

    def test_display_name_is_editable_but_file_identity_and_category_are_immutable(self):
        project_file = self.create_file(category=ProjectFile.Category.PREVIEW)
        project_file.display_name = "Client review cut"
        project_file.save(update_fields=["display_name"])
        project_file.refresh_from_db()
        self.assertEqual(project_file.display_name, "Client review cut")

        project_file.category = ProjectFile.Category.FINAL_DELIVERY
        with self.assertRaisesMessage(ValidationError, "immutable"):
            project_file.save()

    def test_admin_disables_immutable_fields_and_inline_deletion(self):
        project_file = self.create_file(category=ProjectFile.Category.PREVIEW)
        form = ProjectFileInlineForm(instance=project_file)
        self.assertTrue(form.fields["file"].disabled)
        self.assertTrue(form.fields["category"].disabled)
        self.assertTrue(form.fields["supersedes"].disabled)
        self.assertFalse(form.fields["display_name"].disabled)
        self.assertFalse(ProjectFileInline(Project, admin.site).has_delete_permission(None))

    def test_changes_requested_v1_and_new_pending_v2_both_remain_in_history(self):
        first = self.create_file()
        first_approval = Approval.objects.get(file=first)
        first_approval.status = Approval.Status.CHANGES_REQUESTED
        first_approval.save(update_fields=["status", "updated_at"])

        second = self.create_file(name="review v2.pdf", supersedes=first)

        first_approval.refresh_from_db()
        self.assertEqual(first_approval.status, Approval.Status.CHANGES_REQUESTED)
        self.assertEqual(Approval.objects.get(file=second).status, Approval.Status.PENDING)
        self.assertEqual(second.supersedes, first)
        self.assertEqual(Approval.objects.filter(project=self.project).count(), 2)

    def test_pending_approval_becomes_superseded_without_deleting_history(self):
        first = self.create_file()
        second = self.create_file(name="replacement.pdf", supersedes=first)

        self.assertEqual(Approval.objects.get(file=first).status, Approval.Status.SUPERSEDED)
        self.assertEqual(Approval.objects.get(file=second).status, Approval.Status.PENDING)
        self.assertEqual(Approval.objects.filter(project=self.project).count(), 2)

    def test_supersedes_must_stay_in_the_same_project_and_category(self):
        first = self.create_file()
        other_project = Project.objects.create(client=self.client, title="Other")
        other_file = ProjectFile.objects.create(
            project=other_project,
            uploaded_by=self.staff,
            file=CloudinaryResource("other", resource_type="raw", type="private", format="pdf"),
            filename="other.pdf",
            category=ProjectFile.Category.APPROVAL,
        )
        with self.assertRaisesMessage(ValidationError, "same project"):
            self.create_file(name="wrong-project.pdf", supersedes=other_file)

        preview = self.create_file(name="preview.pdf", category=ProjectFile.Category.PREVIEW)
        with self.assertRaisesMessage(ValidationError, "same category"):
            self.create_file(name="wrong-category.pdf", supersedes=preview)
        self.assertEqual(self.provider.uploaded[0].asset_id, "asset-1")
        self.assertEqual(first.project, self.project)

    def test_model_does_not_encode_the_temporary_proxy_size_limit(self):
        project_file = ProjectFile.objects.create(
            project=self.project,
            uploaded_by=self.staff,
            file=CloudinaryResource("huge", resource_type="video", type="authenticated", format="mp4"),
            filename="huge.mp4",
            category=ProjectFile.Category.RAW,
            size_bytes=5_000_000_000,
        )
        self.assertEqual(project_file.size_bytes, 5_000_000_000)


class ProjectFileAccessContractTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("client", password="Password!123")
        self.other_user = User.objects.create_user("other", password="Password!123")
        self.staff = User.objects.create_user("staff", password="Password!123")
        permission = Permission.objects.get(
            codename=PORTAL_STAFF_PERMISSION.split(".", 1)[1],
            content_type__app_label="clients",
        )
        self.staff.user_permissions.add(permission)
        self.client = Client.objects.create(name="Client", email="client@example.com", user=self.user)
        self.other_client = Client.objects.create(
            name="Other", email="other@example.com", user=self.other_user
        )
        self.project = Project.objects.create(client=self.client, title="Project")
        self.other_project = Project.objects.create(client=self.other_client, title="Other")
        self.supported = ProjectFile.objects.create(
            project=self.project, uploaded_by=self.staff,
            file=CloudinaryResource("projects/preview", resource_type="raw", type="private", format="png"),
            filename="preview.png", category=ProjectFile.Category.PREVIEW,
        )
        self.unsupported = ProjectFile.objects.create(
            project=self.project, uploaded_by=self.staff,
            file=CloudinaryResource("projects/source", resource_type="raw", type="private", format="zip"),
            filename="source.zip", category=ProjectFile.Category.PREVIEW,
        )
        self.final = ProjectFile.objects.create(
            project=self.project, uploaded_by=self.staff,
            file=CloudinaryResource("projects/final", resource_type="raw", type="private", format="pdf"),
            filename="final.pdf", category=ProjectFile.Category.FINAL_DELIVERY,
        )
        self.raw = ProjectFile.objects.create(
            project=self.project, uploaded_by=self.staff,
            file=CloudinaryResource("projects/raw", resource_type="raw", type="private", format="png"),
            filename="raw.png", category=ProjectFile.Category.RAW,
        )
        self.api = APIClient()

    def test_api_exposes_safe_preview_metadata_without_provider_identifiers(self):
        self.api.force_authenticate(self.user)
        response = self.api.get(f"/api/projects/{self.project.id}/files/")
        self.assertEqual(response.status_code, 200)
        files = {item["id"]: item for item in response.data}

        self.assertNotIn(self.raw.id, files)
        self.assertFalse(files[self.unsupported.id]["preview_supported"])
        self.assertIsNone(files[self.unsupported.id]["preview_kind"])
        self.assertIsNone(files[self.unsupported.id]["preview_url"])
        self.assertFalse(files[self.final.id]["preview_supported"])
        self.assertIsNone(files[self.final.id]["preview_url"])
        for item in files.values():
            self.assertFalse(
                {"provider_public_id", "provider_asset_id", "provider_delivery_type"}
                & set(item)
            )

    @patch("clients.portal_views.create_project_file")
    def test_portal_staff_api_upload_uses_the_validated_service(self, portal_create):
        provider = FakeProjectFileProvider()
        portal_create.side_effect = lambda **kwargs: create_project_file(
            **kwargs,
            provider=provider,
        )
        self.api.force_authenticate(self.staff)
        response = self.api.post(
            f"/api/projects/{self.project.id}/files/",
            {
                "file": uploaded_file(
                    "Client review 版本.png",
                    b"\x89PNG\r\n\x1a\npng",
                    "image/png",
                ),
                "category": ProjectFile.Category.PREVIEW,
                "display_name": "Review image",
            },
            format="multipart",
        )
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data["filename"], "Client review 版本.png")
        self.assertEqual(response.data["display_name"], "Review image")
        self.assertTrue(response.data["preview_supported"])

        self.api.force_authenticate(self.user)
        denied = self.api.post(
            f"/api/projects/{self.project.id}/files/",
            {"category": ProjectFile.Category.PREVIEW},
            format="multipart",
        )
        self.assertEqual(denied.status_code, 403)

    @patch("clients.portal_views.private_download_url", return_value="https://signed.example/file")
    def test_supported_preview_and_final_download_remain_authenticated(self, signed_url):
        self.api.force_authenticate(self.user)
        preview_response = self.api.get(
            f"/api/projects/{self.project.id}/files/{self.supported.id}/preview/"
        )
        download_response = self.api.get(
            f"/api/projects/{self.project.id}/files/{self.final.id}/download/"
        )
        self.assertEqual(preview_response.status_code, 200)
        self.assertEqual(download_response.status_code, 200)
        self.assertEqual(preview_response.data["url"], "https://signed.example/file")

    def test_unsupported_and_final_files_cannot_call_preview_endpoint(self):
        self.api.force_authenticate(self.user)
        for project_file in (self.unsupported, self.final):
            response = self.api.get(
                f"/api/projects/{self.project.id}/files/{project_file.id}/preview/"
            )
            self.assertEqual(response.status_code, 400)
            self.assertIn("Download it instead", response.data["detail"])

    def test_raw_cross_client_and_unauthenticated_boundaries_remain_enforced(self):
        raw_url = f"/api/projects/{self.project.id}/files/{self.raw.id}/download/"
        self.assertEqual(self.api.get(raw_url).status_code, 401)
        self.api.force_authenticate(self.user)
        self.assertEqual(self.api.get(raw_url).status_code, 404)
        self.api.force_authenticate(self.other_user)
        self.assertEqual(
            self.api.get(f"/api/projects/{self.project.id}/files/").status_code,
            404,
        )

    @patch("clients.portal_views.private_download_url", return_value="https://signed.example/file")
    def test_new_metadata_and_legacy_raw_values_both_sign_exact_identifiers(self, signed_url):
        modern = ProjectFile(
            project=self.project, uploaded_by=self.staff,
            file=CloudinaryResource("ignored", resource_type="raw", type="private", format="zip"),
            filename="source.zip", category=ProjectFile.Category.PREVIEW,
            provider_public_id="projects/exact-source.zip",
            provider_resource_type="raw", provider_delivery_type="private",
            provider_format="zip",
        )
        ProjectViewSet._signed_file_url(modern, attachment=False)
        self.assertEqual(signed_url.call_args.args, ("projects/exact-source.zip", None))

        legacy = ProjectFile(
            project=self.project, uploaded_by=self.staff,
            file=CloudinaryResource("projects/legacy", resource_type="raw", type="private", format="pdf"),
            filename="legacy.pdf", category=ProjectFile.Category.PREVIEW,
        )
        ProjectViewSet._signed_file_url(legacy, attachment=False)
        self.assertEqual(signed_url.call_args.args, ("projects/legacy.pdf", None))

    @patch("clients.portal_views.private_download_url", return_value="https://signed.example/file")
    def test_authenticated_image_signing_uses_provider_metadata_and_format(self, signed_url):
        image = ProjectFile(
            project=self.project, uploaded_by=self.staff,
            file=CloudinaryResource("ignored", resource_type="image", type="authenticated", format="png"),
            filename="image.png", category=ProjectFile.Category.PREVIEW,
            provider_public_id="projects/exact-image",
            provider_resource_type="image", provider_delivery_type="authenticated",
            provider_format="png",
        )
        ProjectViewSet._signed_file_url(image, attachment=False)
        self.assertEqual(signed_url.call_args.args, ("projects/exact-image", "png"))
        self.assertEqual(signed_url.call_args.kwargs["type"], "authenticated")
        self.assertEqual(signed_url.call_args.kwargs["resource_type"], "image")
