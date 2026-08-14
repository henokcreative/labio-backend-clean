from unittest.mock import patch

from django.contrib.auth.models import Permission, User
from django.test import TestCase
from rest_framework.test import APIClient

from clients.models import Client
from clients.permissions import PORTAL_STAFF_PERMISSION

from .models import ContactMessage


class ContactMessageApiTests(TestCase):
    def setUp(self):
        self.api = APIClient()
        self.client_user = User.objects.create_user(
            "client@example.com",
            "client@example.com",
            "Password!123",
        )
        Client.objects.create(
            name="Client",
            email="client@example.com",
            user=self.client_user,
        )
        self.cms_only_staff = User.objects.create_user(
            "cms@example.com",
            "cms@example.com",
            "Password!123",
            is_staff=True,
        )
        self.portal_staff = User.objects.create_user(
            "portal@example.com",
            "portal@example.com",
            "Password!123",
        )
        portal_permission = Permission.objects.get(
            codename=PORTAL_STAFF_PERMISSION.split(".", 1)[1],
            content_type__app_label="clients",
        )
        self.portal_staff.user_permissions.add(portal_permission)
        self.superuser = User.objects.create_superuser(
            "admin@example.com",
            "admin@example.com",
            "Password!123",
        )
        self.contact_message = ContactMessage.objects.create(
            name="Private Contact",
            email="private@example.com",
            organisation="Research Lab",
            service="video",
            message="Private project details",
        )

    def test_anonymous_user_cannot_list_contact_messages(self):
        response = self.api.get("/api/contacts/messages/")
        self.assertEqual(response.status_code, 401)

    def test_client_cannot_list_contact_messages(self):
        self.api.force_authenticate(self.client_user)
        response = self.api.get("/api/contacts/messages/")
        self.assertEqual(response.status_code, 403)

    def test_generic_django_staff_cannot_list_contact_messages(self):
        self.api.force_authenticate(self.cms_only_staff)
        response = self.api.get("/api/contacts/messages/")
        self.assertEqual(response.status_code, 403)

    def test_portal_staff_can_list_contact_messages(self):
        self.api.force_authenticate(self.portal_staff)
        response = self.api.get("/api/contacts/messages/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data[0]["email"], "private@example.com")
        self.assertEqual(response.data[0]["message"], "Private project details")

    def test_superuser_can_list_contact_messages(self):
        self.api.force_authenticate(self.superuser)
        response = self.api.get("/api/contacts/messages/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data[0]["id"], self.contact_message.id)

    @patch("contacts.views.resend.Emails.send")
    def test_public_contact_submission_remains_available(self, send_email):
        self.api.force_authenticate(user=None)
        response = self.api.post(
            "/api/contacts/submit/",
            {
                "name": "Public Contact",
                "email": "public@example.com",
                "organisation": "Public Lab",
                "service": "photography",
                "message": "Please contact me",
                "is_read": True,
            },
            format="json",
        )

        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data["email_notification"], "sent")
        saved = ContactMessage.objects.get(email="public@example.com")
        self.assertFalse(saved.is_read)
        send_email.assert_called_once()

    @patch(
        "contacts.views.resend.Emails.send",
        side_effect=RuntimeError("provider unavailable"),
    )
    def test_email_failure_keeps_submission_and_is_not_silent(self, send_email):
        self.api.force_authenticate(user=None)
        with self.assertLogs("contacts.views", level="ERROR"):
            response = self.api.post(
                "/api/contacts/submit/",
                {
                    "name": "Saved Contact",
                    "email": "saved@example.com",
                    "message": "Keep this request",
                },
                format="json",
            )

        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data["email_notification"], "failed")
        self.assertTrue(
            ContactMessage.objects.filter(email="saved@example.com").exists()
        )
        send_email.assert_called_once()
