from django.contrib import admin
from django.contrib.auth.models import Permission, User
from datetime import datetime, timedelta

from django.contrib.auth.tokens import default_token_generator
from django.core.cache import cache
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import transaction
from django.test import RequestFactory, TestCase, override_settings
from django.urls import reverse
from rest_framework.test import APIClient
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode
from unittest.mock import Mock, patch

from cloudinary import CloudinaryResource
from messaging.models import Conversation
from .admin import ProjectAdmin
from .models import Approval, Client, Project, ProjectFile
from .portal_views import ProjectViewSet
from .permissions import PORTAL_STAFF_PERMISSION
from .services import (
    password_reset_url,
    send_invitation_email,
    send_password_reset_email,
)
from .tokens import password_reset_token_generator


@override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
class InvitationTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="client@example.com", email="client@example.com")
        self.user.set_unusable_password()
        self.user.save(update_fields=["password"])
        Client.objects.create(name="Test Client", email="client@example.com", user=self.user)
        self.uid = urlsafe_base64_encode(force_bytes(self.user.pk))
        self.token = default_token_generator.make_token(self.user)

    @patch("clients.services.resend.Emails.send")
    def test_sends_a_password_setup_link(self, send_email):
        url = send_invitation_email(self.user)
        send_email.assert_called_once()
        self.assertIn("uid=", url)

    def test_accepts_once_and_sets_password(self):
        self.assertEqual(self.client.get(reverse("validate-invitation"), {"uid": self.uid, "token": self.token}).status_code, 200)
        payload = {"uid": self.uid, "token": self.token, "password": "SecurePassword!123", "password_confirmation": "SecurePassword!123"}
        self.assertEqual(self.client.post(reverse("accept-invitation"), payload).status_code, 200)
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password("SecurePassword!123"))
        self.assertEqual(self.client.post(reverse("accept-invitation"), payload).status_code, 400)

    def test_rejects_mismatched_passwords(self):
        response = self.client.post(reverse("accept-invitation"), {"uid": self.uid, "token": self.token, "password": "SecurePassword!123", "password_confirmation": "different"})
        self.assertEqual(response.status_code, 400)
        self.assertIn("password_confirmation", response.data)


class EmailLoginTests(TestCase):
    def test_login_accepts_email_and_password_without_username(self):
        User.objects.create_user(
            username="client@example.com",
            email="client@example.com",
            password="SecurePassword!123",
        )

        response = self.client.post(
            reverse("token_obtain_pair"),
            {"email": "client@example.com", "password": "SecurePassword!123"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertIn("access", response.data)
        self.assertIn("refresh", response.data)


class PasswordResetTests(TestCase):
    def setUp(self):
        cache.clear()
        self.user = User.objects.create_user(
            username="reset@example.com",
            email="reset@example.com",
            password="OldSecurePassword!123",
        )

    @patch("clients.views.send_password_reset_email")
    def test_request_is_generic_for_known_and_unknown_emails(self, send_email):
        known = self.client.post(
            reverse("password-reset-request"),
            {"email": self.user.email},
        )
        unknown = self.client.post(
            reverse("password-reset-request"),
            {"email": "unknown@example.com"},
        )

        self.assertEqual(known.status_code, 200)
        self.assertEqual(unknown.status_code, 200)
        self.assertEqual(known.json(), unknown.json())
        send_email.assert_called_once_with(self.user)

    @override_settings(
        PASSWORD_RESET_FRONTEND_URL="https://example.com/reset-password"
    )
    def test_reset_url_uses_frontend_route_without_exposing_credentials(self):
        url = password_reset_url(self.user)
        self.assertTrue(url.startswith("https://example.com/reset-password?"))
        self.assertIn("uid=", url)
        self.assertIn("token=", url)

    @override_settings(
        PASSWORD_RESET_FRONTEND_URL="",
        INVITATION_FRONTEND_URL="https://www.example.com/accept-invitation",
    )
    def test_reset_url_defaults_to_invitation_frontend_origin(self):
        url = password_reset_url(self.user)
        self.assertTrue(url.startswith("https://www.example.com/reset-password?"))

    @patch("clients.services.resend.Emails.send")
    def test_reset_email_uses_existing_resend_sender(self, send_email):
        url = send_password_reset_email(self.user)
        send_email.assert_called_once()
        payload = send_email.call_args.args[0]
        self.assertEqual(payload["to"], self.user.email)
        self.assertEqual(payload["from"], "dev-null@localhost")
        self.assertIn(url, payload["text"])

    def test_valid_reset_sets_password_and_invalidates_token(self):
        uid = urlsafe_base64_encode(force_bytes(self.user.pk))
        token = password_reset_token_generator.make_token(self.user)
        payload = {
            "uid": uid,
            "token": token,
            "password": "NewSecurePassword!456",
            "password_confirmation": "NewSecurePassword!456",
        }

        response = self.client.post(reverse("password-reset-confirm"), payload)
        self.assertEqual(response.status_code, 200)
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password("NewSecurePassword!456"))
        self.assertEqual(
            self.client.post(reverse("password-reset-confirm"), payload).status_code,
            400,
        )

    def test_password_validation_errors_are_returned(self):
        uid = urlsafe_base64_encode(force_bytes(self.user.pk))
        token = password_reset_token_generator.make_token(self.user)
        response = self.client.post(
            reverse("password-reset-confirm"),
            {
                "uid": uid,
                "token": token,
                "password": "123",
                "password_confirmation": "123",
            },
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("password", response.json())

    @override_settings(PASSWORD_RESET_TIMEOUT=60)
    def test_expired_token_is_rejected(self):
        issued_at = datetime(2026, 1, 1, 12, 0, 0)
        with patch.object(password_reset_token_generator, "_now", return_value=issued_at):
            token = password_reset_token_generator.make_token(self.user)
        uid = urlsafe_base64_encode(force_bytes(self.user.pk))
        with patch.object(
            password_reset_token_generator,
            "_now",
            return_value=issued_at + timedelta(seconds=61),
        ):
            response = self.client.post(
                reverse("password-reset-confirm"),
                {
                    "uid": uid,
                    "token": token,
                    "password": "NewSecurePassword!456",
                    "password_confirmation": "NewSecurePassword!456",
                },
            )
        self.assertEqual(response.status_code, 400)

    def test_invitation_token_cannot_be_used_as_password_reset_token(self):
        uid = urlsafe_base64_encode(force_bytes(self.user.pk))
        invitation_token = default_token_generator.make_token(self.user)
        response = self.client.post(
            reverse("password-reset-confirm"),
            {
                "uid": uid,
                "token": invitation_token,
                "password": "NewSecurePassword!456",
                "password_confirmation": "NewSecurePassword!456",
            },
        )
        self.assertEqual(response.status_code, 400)

    @override_settings(
        PASSWORD_RESET_RATE_LIMIT=2,
        PASSWORD_RESET_RATE_WINDOW_SECONDS=900,
    )
    @patch("clients.views.send_password_reset_email")
    def test_request_is_rate_limited_by_request_source(self, send_email):
        for _ in range(2):
            response = self.client.post(
                reverse("password-reset-request"),
                {"email": self.user.email},
                REMOTE_ADDR="203.0.113.4",
            )
            self.assertEqual(response.status_code, 200)
        response = self.client.post(
            reverse("password-reset-request"),
            {"email": self.user.email},
            REMOTE_ADDR="203.0.113.4",
        )
        self.assertEqual(response.status_code, 429)


class ProjectAdminTests(TestCase):
    @patch("clients.admin.create_project_file")
    def test_inline_file_upload_records_logged_in_staff_as_uploader(self, create_file):
        staff = User.objects.create_superuser(
            username="admin",
            email="admin@example.com",
            password="Password!123",
        )
        client = Client.objects.create(name="Client", email="client@example.com")
        project = Project.objects.create(client=client, title="Project")
        project_file = ProjectFile(
            project=project,
            file=SimpleUploadedFile(
                "admin upload.pdf",
                b"%PDF-1.7 admin upload",
                content_type="application/pdf",
            ),
            category=ProjectFile.Category.PREVIEW,
        )
        create_file.side_effect = lambda **kwargs: ProjectFile.objects.create(
            project=kwargs["project"],
            uploaded_by=kwargs["uploaded_by"],
            file=CloudinaryResource(
                "admin-upload", resource_type="raw", type="private", format="pdf"
            ),
            filename=kwargs["uploaded_file"].name,
            category=kwargs["category"],
        )
        formset = Mock()
        formset.save.return_value = [project_file]
        request = RequestFactory().post(f"/admin/clients/project/{project.pk}/change/")
        request.user = staff

        ProjectAdmin(Project, admin.site).save_formset(
            request,
            form=None,
            formset=formset,
            change=True,
        )

        saved_file = ProjectFile.objects.get(project=project)
        self.assertEqual(saved_file.uploaded_by, staff)
        self.assertFalse(Approval.objects.filter(file=saved_file).exists())
        formset.save.assert_called_once_with(commit=False)
        create_file.assert_called_once()
        formset.save_m2m.assert_not_called()

    @patch("clients.admin.create_project_file")
    def test_inline_approval_file_creates_pending_approval_for_project_client(self, create_file):
        staff = User.objects.create_superuser("admin", "admin@example.com", "Password!123")
        client = Client.objects.create(name="Client", email="client@example.com")
        project = Project.objects.create(client=client, title="Project")
        project_file = ProjectFile(
            project=project,
            file=SimpleUploadedFile(
                "approval.pdf", b"%PDF-1.7 approval", content_type="application/pdf"
            ),
            category=ProjectFile.Category.APPROVAL,
        )
        create_file.side_effect = lambda **kwargs: ProjectFile.objects.create(
            project=kwargs["project"],
            uploaded_by=kwargs["uploaded_by"],
            file=CloudinaryResource(
                "approval-upload", resource_type="raw", type="private", format="pdf"
            ),
            filename=kwargs["uploaded_file"].name,
            category=kwargs["category"],
        )
        formset = Mock()
        formset.save.return_value = [project_file]
        request = RequestFactory().post(f"/admin/clients/project/{project.pk}/change/")
        request.user = staff

        ProjectAdmin(Project, admin.site).save_formset(request, None, formset, True)

        approval = Approval.objects.get(file__project=project)
        self.assertEqual(approval.project, project)
        self.assertEqual(approval.client, client)
        self.assertEqual(approval.status, Approval.Status.PENDING)


class PortalPermissionTests(TestCase):
    def setUp(self):
        self.user_a = User.objects.create_user("a@example.com", "a@example.com", "Password!123")
        self.user_b = User.objects.create_user("b@example.com", "b@example.com", "Password!123")
        self.staff = User.objects.create_user("staff", "staff@example.com", "Password!123", is_staff=True)
        self.staff.first_name = "Portal"
        self.staff.last_name = "Staff"
        self.staff.save(update_fields=["first_name", "last_name"])
        self.portal_permission = Permission.objects.get(
            codename=PORTAL_STAFF_PERMISSION.split(".", 1)[1],
            content_type__app_label="clients",
        )
        self.staff.user_permissions.add(self.portal_permission)
        self.client_a = Client.objects.create(name="Client A", email="a@example.com", user=self.user_a)
        self.client_b = Client.objects.create(name="Client B", email="b@example.com", user=self.user_b)
        self.project_a = Project.objects.create(client=self.client_a, title="A project")
        self.project_b = Project.objects.create(client=self.client_b, title="B project")
        self.preview_a = ProjectFile.objects.create(
            project=self.project_a, uploaded_by=self.staff,
            file=CloudinaryResource("client-a-preview", resource_type="raw", type="private", format="pdf"),
            filename="client-a-preview.pdf", category=ProjectFile.Category.PREVIEW,
        )
        self.raw_a = ProjectFile.objects.create(
            project=self.project_a, uploaded_by=self.staff,
            file=CloudinaryResource("client-a-raw", resource_type="raw", type="private", format="zip"),
            filename="client-a-raw.zip", category=ProjectFile.Category.RAW,
        )
        self.approval_file_a = ProjectFile.objects.create(
            project=self.project_a, uploaded_by=self.staff,
            file=CloudinaryResource("client-a-approval", resource_type="raw", type="private", format="pdf"),
            filename="client-a-approval.pdf", category=ProjectFile.Category.APPROVAL,
        )
        self.approval_a = Approval.objects.get(file=self.approval_file_a)
        self.final_a = ProjectFile.objects.create(
            project=self.project_a, uploaded_by=self.staff,
            file=CloudinaryResource("client-a-final", resource_type="raw", type="private", format="pdf"),
            filename="client-a-final.pdf", category=ProjectFile.Category.FINAL_DELIVERY,
        )
        self.preview_b = ProjectFile.objects.create(
            project=self.project_b, uploaded_by=self.staff,
            file=CloudinaryResource("client-b-preview", resource_type="raw", type="private", format="pdf"),
            filename="client-b-preview.pdf", category=ProjectFile.Category.PREVIEW,
        )
        self.approval_file_b = ProjectFile.objects.create(
            project=self.project_b, uploaded_by=self.staff,
            file=CloudinaryResource("client-b-approval", resource_type="raw", type="private", format="pdf"),
            filename="client-b-approval.pdf", category=ProjectFile.Category.APPROVAL,
        )
        self.approval_b = Approval.objects.get(file=self.approval_file_b)
        self.api = APIClient()

    def test_client_cannot_access_another_clients_project_or_messages(self):
        self.api.force_authenticate(self.user_a)
        self.assertEqual(self.api.get(f"/api/projects/{self.project_b.id}/").status_code, 404)
        self.assertEqual(self.api.get(f"/api/projects/{self.project_b.id}/files/").status_code, 404)
        response = self.api.post("/api/messages/", {"project": self.project_b.id, "content": "hello"}, format="json")
        self.assertEqual(response.status_code, 404)
        response = self.api.post(f"/api/projects/{self.project_b.id}/approve/", {"file_id": self.approval_file_b.id, "status": "approved"}, format="json")
        self.assertEqual(response.status_code, 404)

    def test_staff_can_access_projects_and_unauthenticated_cannot(self):
        self.assertEqual(self.api.get("/api/projects/").status_code, 401)
        self.api.force_authenticate(self.staff)
        self.assertEqual(self.api.get(f"/api/projects/{self.project_a.id}/").status_code, 200)
        response = self.api.post(
            "/api/projects/",
            {"client": self.client_a.id, "title": "Staff-created project"},
            format="json",
        )
        self.assertEqual(response.status_code, 201)

    def test_generic_django_staff_cannot_access_private_portal_data(self):
        cms_editor = User.objects.create_user(
            "cms-editor",
            "cms@example.com",
            "Password!123",
            is_staff=True,
        )
        self.api.force_authenticate(cms_editor)

        self.assertEqual(self.api.get("/api/projects/").status_code, 403)
        self.assertEqual(self.api.get("/api/messages/").status_code, 403)
        self.assertEqual(self.api.get("/api/auth/dashboard/").status_code, 403)
        self.assertEqual(
            self.api.get(f"/api/projects/{self.project_a.id}/files/").status_code,
            403,
        )
        self.assertEqual(
            self.api.post(
                "/api/projects/",
                {"client": self.client_a.id, "title": "Forbidden project"},
                format="json",
            ).status_code,
            403,
        )

    def test_superuser_retains_private_portal_access(self):
        superuser = User.objects.create_superuser(
            "superuser",
            "superuser@example.com",
            "Password!123",
        )
        self.api.force_authenticate(superuser)
        self.assertEqual(self.api.get("/api/projects/").status_code, 200)

    def test_assignments_do_not_change_client_ownership(self):
        self.project_b.primary_staff = self.staff
        self.project_b.save()
        self.project_b.team_members.add(self.staff)

        self.api.force_authenticate(self.user_a)
        self.assertEqual(
            self.api.get(f"/api/projects/{self.project_b.id}/").status_code,
            404,
        )

    def test_invalid_and_inactive_users_cannot_be_assigned(self):
        self.client_a.primary_contact = self.user_a
        with self.assertRaises(ValidationError):
            self.client_a.save()

        self.project_a.primary_staff = self.user_a
        with self.assertRaises(ValidationError):
            self.project_a.save()
        self.project_a.primary_staff = None

        with self.assertRaises(ValidationError), transaction.atomic():
            self.project_a.team_members.add(self.user_a)

        cms_editor = User.objects.create_user(
            "assignment-cms-editor",
            "assignment-cms@example.com",
            "Password!123",
            is_staff=True,
        )
        self.project_a.primary_staff = cms_editor
        with self.assertRaises(ValidationError):
            self.project_a.save()
        self.project_a.primary_staff = None
        with self.assertRaises(ValidationError), transaction.atomic():
            self.project_a.team_members.add(cms_editor)

        inactive_staff = User.objects.create_user(
            "inactive-staff",
            "inactive@example.com",
            "Password!123",
            is_active=False,
        )
        inactive_staff.user_permissions.add(self.portal_permission)
        self.project_a.primary_staff = inactive_staff
        with self.assertRaises(ValidationError):
            self.project_a.save()
        self.project_a.primary_staff = None
        with self.assertRaises(ValidationError), transaction.atomic():
            self.project_a.team_members.add(inactive_staff)

    def test_project_serializes_only_safe_staff_information_and_resolution(self):
        team_member = User.objects.create_user(
            "team-member",
            "team@example.com",
            "Password!123",
            first_name="Team",
            last_name="Member",
        )
        team_member.user_permissions.add(self.portal_permission)
        self.client_a.primary_contact = team_member
        self.client_a.save()
        self.project_a.team_members.add(team_member)

        self.api.force_authenticate(self.user_a)
        response = self.api.get(f"/api/projects/{self.project_a.id}/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.data["primary_contact"],
            {"id": team_member.id, "name": "Team Member"},
        )
        self.assertIsNone(response.data["primary_staff"])
        self.assertEqual(
            response.data["team_members"],
            [{"id": team_member.id, "name": "Team Member"}],
        )
        self.assertEqual(set(response.data["primary_contact"]), {"id", "name"})

        self.project_a.primary_staff = self.staff
        self.project_a.save()
        response = self.api.get(f"/api/projects/{self.project_a.id}/")
        self.assertEqual(
            response.data["primary_contact"],
            {"id": self.staff.id, "name": "Portal Staff"},
        )

    @patch("clients.portal_views.private_download_url", return_value="https://signed.example/file")
    def test_file_delivery_is_private_and_category_scoped(self, signed_url):
        self.api.force_authenticate(self.user_a)
        response = self.api.get(f"/api/projects/{self.project_a.id}/files/")
        self.assertEqual(response.status_code, 200)
        files_by_id = {item["id"]: item for item in response.data}
        self.assertNotIn(self.raw_a.id, files_by_id)
        self.assertEqual(files_by_id[self.preview_a.id]["preview_url"], f"/api/projects/{self.project_a.id}/files/{self.preview_a.id}/preview/")
        self.assertEqual(files_by_id[self.preview_a.id]["download_url"], f"/api/projects/{self.project_a.id}/files/{self.preview_a.id}/download/")
        self.assertFalse(files_by_id[self.preview_a.id]["pending_approval"])
        self.assertTrue(files_by_id[self.approval_file_a.id]["pending_approval"])
        self.assertIsNone(files_by_id[self.final_a.id]["preview_url"])
        self.assertFalse(files_by_id[self.final_a.id]["pending_approval"])
        self.assertFalse(Approval.objects.filter(file=self.preview_a).exists())
        self.assertFalse(Approval.objects.filter(file=self.final_a).exists())
        self.assertEqual(self.api.get(f"/api/projects/{self.project_a.id}/files/{self.raw_a.id}/download/").status_code, 404)
        response = self.api.get(f"/api/projects/{self.project_a.id}/files/{self.preview_a.id}/download/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["url"], "https://signed.example/file")
        signed_url.assert_called_once_with(
            "client-a-preview.pdf",
            None,
            resource_type="raw",
            type="private",
            expires_at=signed_url.call_args.kwargs["expires_at"],
            attachment="client-a-preview.pdf",
        )

    @patch("clients.portal_views.private_download_url", return_value="https://signed.example/file")
    def test_raw_signed_urls_preserve_png_pdf_and_zip_extensions(self, signed_url):
        resources = [
            ("projects/image-id", "png", "projects/image-id.png"),
            ("projects/document-id", "pdf", "projects/document-id.pdf"),
            ("projects/archive-id.zip", "zip", "projects/archive-id.zip"),
        ]

        for public_id, file_format, expected_public_id in resources:
            project_file = ProjectFile(
                project=self.project_a,
                uploaded_by=self.staff,
                file=CloudinaryResource(
                    public_id,
                    resource_type="raw",
                    type="private",
                    format=file_format,
                ),
                filename=f"file.{file_format}",
                category=ProjectFile.Category.PREVIEW,
            )

            ProjectViewSet._signed_file_url(project_file, attachment=False)

            args, kwargs = signed_url.call_args
            self.assertEqual(args, (expected_public_id, None))
            self.assertEqual(kwargs["resource_type"], "raw")
            self.assertEqual(kwargs["type"], "private")

    def test_protected_file_endpoints_require_authentication(self):
        self.assertEqual(
            self.api.get(f"/api/projects/{self.project_a.id}/files/{self.preview_a.id}/download/").status_code,
            401,
        )
        self.assertEqual(
            self.api.get(f"/api/projects/{self.project_a.id}/files/{self.preview_a.id}/preview/").status_code,
            401,
        )

    def test_preview_file_cannot_be_approved(self):
        self.api.force_authenticate(self.user_a)
        response = self.api.post(
            f"/api/projects/{self.project_a.id}/approve/",
            {"file_id": self.preview_a.id, "status": "approved"},
            format="json",
        )
        self.assertEqual(response.status_code, 404)

    def test_client_approval_transitions_and_project_messages(self):
        Conversation.objects.create(client=self.user_a, subject="Legacy conversation")
        self.api.force_authenticate(self.user_a)
        response = self.api.post(f"/api/projects/{self.project_a.id}/approve/", {"file_id": self.approval_file_a.id, "status": "changes_requested", "comment": "Please adjust the pacing."}, format="json")
        self.assertEqual(response.status_code, 200)
        self.approval_a.refresh_from_db()
        self.project_a.refresh_from_db()
        self.assertEqual(self.approval_a.status, Approval.Status.CHANGES_REQUESTED)
        self.assertEqual(self.approval_a.comment, "Please adjust the pacing.")
        self.assertEqual(self.project_a.status, "review")
        response = self.api.post("/api/messages/", {"project": self.project_a.id, "content": "Could you revise section two?"}, format="json")
        self.assertEqual(response.status_code, 201)
        self.assertEqual(Conversation.objects.get(project=self.project_a).client, self.user_a)
        self.assertEqual(self.api.get(f"/api/messages/?project={self.project_a.id}").status_code, 200)
        self.assertEqual(self.api.get("/api/messages/").status_code, 200)

    def test_unauthenticated_portal_requests_are_rejected(self):
        self.assertEqual(self.api.get("/api/messages/").status_code, 401)
        self.assertEqual(self.api.get("/api/auth/dashboard/").status_code, 401)
