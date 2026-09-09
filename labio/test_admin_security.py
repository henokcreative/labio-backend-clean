from django.contrib.auth.models import Permission, User
from django.test import TestCase
from rest_framework.test import APIClient

from contacts.models import ContactMessage
from messaging.models import Conversation, Message


class AdminListEditablePermissionTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            "restricted-admin",
            "restricted@example.com",
            "Password!123",
            is_staff=True,
        )
        self.api = APIClient()
        self.api.force_login(self.user)

    def grant_change_permission(self, app_label, codename):
        self.user.user_permissions.add(
            Permission.objects.get(
                codename=codename,
                content_type__app_label=app_label,
            )
        )

    @staticmethod
    def forged_extra_form():
        return {
            "form-TOTAL_FORMS": "1",
            "form-INITIAL_FORMS": "0",
            "form-MIN_NUM_FORMS": "0",
            "form-MAX_NUM_FORMS": "1000",
            "form-0-id": "",
            "form-0-is_read": "on",
            "_save": "Save",
        }

    def test_contact_changelist_cannot_add_without_add_permission(self):
        self.grant_change_permission("contacts", "change_contactmessage")

        response = self.api.post(
            "/admin/contacts/contactmessage/",
            self.forged_extra_form(),
        )

        self.assertFalse(self.user.has_perm("contacts.add_contactmessage"))
        self.assertEqual(response.status_code, 400)
        self.assertEqual(ContactMessage.objects.count(), 0)

    def test_message_changelist_cannot_add_without_add_permission(self):
        self.grant_change_permission("messaging", "change_message")

        response = self.api.post(
            "/admin/messaging/message/",
            self.forged_extra_form(),
        )

        self.assertFalse(self.user.has_perm("messaging.add_message"))
        self.assertEqual(response.status_code, 400)
        self.assertEqual(Message.objects.count(), 0)

    def test_existing_rows_remain_editable_with_change_permission(self):
        self.grant_change_permission("contacts", "change_contactmessage")
        contact = ContactMessage.objects.create(
            name="Existing contact",
            email="existing@example.com",
            message="Existing message",
        )

        response = self.api.post(
            "/admin/contacts/contactmessage/",
            {
                "form-TOTAL_FORMS": "1",
                "form-INITIAL_FORMS": "1",
                "form-MIN_NUM_FORMS": "0",
                "form-MAX_NUM_FORMS": "1000",
                "form-0-id": str(contact.pk),
                "form-0-is_read": "on",
                "_save": "Save",
            },
        )

        self.assertEqual(response.status_code, 302)
        contact.refresh_from_db()
        self.assertTrue(contact.is_read)

    def test_existing_message_rows_remain_editable_with_change_permission(self):
        self.grant_change_permission("messaging", "change_message")
        client_user = User.objects.create_user("client")
        conversation = Conversation.objects.create(
            client=client_user,
            subject="Existing conversation",
        )
        message = Message.objects.create(
            conversation=conversation,
            sender=client_user,
            body="Existing message",
        )

        response = self.api.post(
            "/admin/messaging/message/",
            {
                "form-TOTAL_FORMS": "1",
                "form-INITIAL_FORMS": "1",
                "form-MIN_NUM_FORMS": "0",
                "form-MAX_NUM_FORMS": "1000",
                "form-0-id": str(message.pk),
                "form-0-is_read": "on",
                "_save": "Save",
            },
        )

        self.assertEqual(response.status_code, 302)
        message.refresh_from_db()
        self.assertTrue(message.is_read)
