from unittest.mock import Mock

from django.contrib import admin
from django.contrib.auth.models import Permission, User
from django.test import RequestFactory, TestCase
from rest_framework.test import APIClient

from clients.models import Client
from clients.permissions import PORTAL_STAFF_PERMISSION
from .admin import ConversationAdmin
from .models import Conversation, Message


class ConversationAdminMessageInlineTests(TestCase):
    def setUp(self):
        self.client_user = User.objects.create_user(
            "client@example.com",
            "client@example.com",
            "Password!123",
        )
        self.staff_user = User.objects.create_user(
            "admin",
            "admin@example.com",
            "Password!123",
            is_staff=True,
        )
        self.conversation = Conversation.objects.create(
            client=self.client_user,
            subject="Admin reply",
        )
        self.request = RequestFactory().post(
            f"/admin/messaging/conversation/{self.conversation.pk}/change/"
        )
        self.request.user = self.staff_user
        self.model_admin = ConversationAdmin(Conversation, admin.site)

    @staticmethod
    def formset_for(instances):
        formset = Mock()
        formset.save.return_value = instances
        formset.deleted_objects = []
        return formset

    def test_new_inline_message_records_logged_in_staff_as_sender(self):
        message = Message(
            conversation=self.conversation,
            body="A reply created in Django Admin",
        )
        formset = self.formset_for([message])

        self.model_admin.save_formset(
            self.request,
            form=None,
            formset=formset,
            change=True,
        )

        saved_message = Message.objects.get(conversation=self.conversation)
        self.assertEqual(saved_message.sender, self.staff_user)
        formset.save.assert_called_once_with(commit=False)
        formset.save_m2m.assert_called_once_with()

    def test_existing_inline_message_retains_original_sender(self):
        message = Message.objects.create(
            conversation=self.conversation,
            sender=self.client_user,
            body="Original client message",
        )
        message.body = "Edited body"
        formset = self.formset_for([message])

        self.model_admin.save_formset(
            self.request,
            form=None,
            formset=formset,
            change=True,
        )

        message.refresh_from_db()
        self.assertEqual(message.sender, self.client_user)


class MessagingPortalStaffPermissionTests(TestCase):
    def setUp(self):
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
        self.conversation = Conversation.objects.create(
            client=self.client_user,
            subject="Project update",
        )
        self.portal_staff = User.objects.create_user(
            "portal-staff",
            "staff@example.com",
            "Password!123",
            is_staff=True,
            first_name="Portal",
            last_name="Staff",
        )
        permission = Permission.objects.get(
            codename=PORTAL_STAFF_PERMISSION.split(".", 1)[1],
            content_type__app_label="clients",
        )
        self.portal_staff.user_permissions.add(permission)
        self.cms_editor = User.objects.create_user(
            "cms-editor",
            "cms@example.com",
            "Password!123",
            is_staff=True,
        )
        self.api = APIClient()

    def test_portal_staff_can_access_staff_messaging_endpoints(self):
        self.api.force_authenticate(self.portal_staff)
        self.assertEqual(
            self.api.get("/api/messaging/conversations/").status_code,
            200,
        )
        response = self.api.post(
            f"/api/messaging/conversations/{self.conversation.id}/assign/"
        )
        self.assertEqual(response.status_code, 200)
        self.conversation.refresh_from_db()
        self.assertEqual(self.conversation.assigned_staff, self.portal_staff)

    def test_conversation_response_preserves_fields_and_adds_safe_display_data(self):
        Message.objects.create(
            conversation=self.conversation,
            sender=self.client_user,
            body="Hello from the client",
        )
        self.api.force_authenticate(self.portal_staff)

        response = self.api.get("/api/messaging/conversations/")

        self.assertEqual(response.status_code, 200)
        conversation = response.data[0]
        self.assertEqual(conversation["client_username"], "client@example.com")
        self.assertEqual(conversation["client_name"], "Client")
        self.assertIn("assigned_staff_username", conversation)
        self.assertIn("messages", conversation)
        message = conversation["messages"][0]
        self.assertEqual(message["body"], "Hello from the client")
        self.assertEqual(message["content"], "Hello from the client")
        self.assertEqual(message["sender_name"], "Client")
        self.assertEqual(message["sender_role"], "client")

    def test_staff_filters_and_unread_count_use_client_messages(self):
        assigned = Conversation.objects.create(
            client=self.client_user,
            subject="Assigned",
            assigned_staff=self.portal_staff,
        )
        Message.objects.create(
            conversation=assigned,
            sender=self.client_user,
            body="Needs a reply",
        )
        Message.objects.create(
            conversation=self.conversation,
            sender=self.portal_staff,
            body="Waiting for the client",
        )
        self.api.force_authenticate(self.portal_staff)

        mine = self.api.get("/api/messaging/conversations/?filter=mine")
        unread = self.api.get("/api/messaging/conversations/?filter=unread")
        unassigned = self.api.get("/api/messaging/conversations/?filter=unassigned")
        count = self.api.get("/api/messaging/unread/")

        self.assertEqual([item["id"] for item in mine.data], [assigned.id])
        self.assertEqual([item["id"] for item in unread.data], [assigned.id])
        self.assertEqual(
            [item["id"] for item in unassigned.data],
            [self.conversation.id],
        )
        self.assertEqual(count.data, {"unread": 1})

    def test_each_side_marks_only_incoming_messages_read(self):
        client_message = Message.objects.create(
            conversation=self.conversation,
            sender=self.client_user,
            body="Client message",
        )
        staff_message = Message.objects.create(
            conversation=self.conversation,
            sender=self.portal_staff,
            body="Staff message",
        )

        self.api.force_authenticate(self.portal_staff)
        response = self.api.post(
            f"/api/messaging/conversations/{self.conversation.id}/mark-read/"
        )
        self.assertEqual(response.status_code, 200)
        client_message.refresh_from_db()
        staff_message.refresh_from_db()
        self.assertTrue(client_message.is_read)
        self.assertFalse(staff_message.is_read)

        self.api.force_authenticate(self.client_user)
        self.assertEqual(
            self.api.get("/api/messaging/unread/").data,
            {"unread": 1},
        )
        response = self.api.post(
            f"/api/messaging/conversations/{self.conversation.id}/mark-read/"
        )
        self.assertEqual(response.status_code, 200)
        staff_message.refresh_from_db()
        self.assertTrue(staff_message.is_read)

    def test_replies_are_validated_scoped_and_update_conversation(self):
        unread_client_message = Message.objects.create(
            conversation=self.conversation,
            sender=self.client_user,
            body="Please reply",
        )
        previous_updated_at = self.conversation.updated_at
        self.api.force_authenticate(self.portal_staff)

        self.assertEqual(
            self.api.post(
                f"/api/messaging/conversations/{self.conversation.id}/send/",
                {"body": "   "},
                format="json",
            ).status_code,
            400,
        )
        response = self.api.post(
            f"/api/messaging/conversations/{self.conversation.id}/send/",
            {"body": "  A helpful reply  "},
            format="json",
        )
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data["body"], "A helpful reply")
        self.assertEqual(response.data["sender_name"], "Portal Staff")
        unread_client_message.refresh_from_db()
        self.conversation.refresh_from_db()
        self.assertTrue(unread_client_message.is_read)
        self.assertGreater(self.conversation.updated_at, previous_updated_at)

        other_user = User.objects.create_user(
            "other@example.com",
            "other@example.com",
            "Password!123",
        )
        Client.objects.create(
            name="Other Client",
            email="other@example.com",
            user=other_user,
        )
        other_conversation = Conversation.objects.create(
            client=other_user,
            subject="Private",
        )
        self.api.force_authenticate(self.client_user)
        self.assertEqual(
            self.api.post(
                f"/api/messaging/conversations/{other_conversation.id}/send/",
                {"body": "Not allowed"},
                format="json",
            ).status_code,
            404,
        )

    def test_client_conversation_list_is_scoped_and_can_mark_own_conversation(self):
        other_user = User.objects.create_user(
            "other@example.com",
            "other@example.com",
            "Password!123",
        )
        Client.objects.create(
            name="Other Client",
            email="other@example.com",
            user=other_user,
        )
        other_conversation = Conversation.objects.create(
            client=other_user,
            subject="Other private conversation",
        )
        self.api.force_authenticate(self.client_user)

        response = self.api.get("/api/messaging/conversations/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual([item["id"] for item in response.data], [self.conversation.id])
        self.assertEqual(
            self.api.post(
                f"/api/messaging/conversations/{other_conversation.id}/mark-read/"
            ).status_code,
            404,
        )

    def test_start_conversation_validation_and_client_list_compatibility(self):
        self.api.force_authenticate(self.portal_staff)
        self.assertEqual(
            self.api.post(
                "/api/messaging/conversations/start/",
                {"client_id": self.client_user.id, "subject": "   "},
                format="json",
            ).status_code,
            400,
        )
        response = self.api.post(
            "/api/messaging/conversations/start/",
            {"client_id": self.client_user.id, "subject": " New brief "},
            format="json",
        )
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data["subject"], "New brief")
        self.assertEqual(response.data["assigned_staff_name"], "Portal Staff")

        clients = self.api.get("/api/messaging/clients/")
        self.assertEqual(clients.status_code, 200)
        self.assertEqual(clients.data[0]["username"], "client@example.com")
        self.assertEqual(clients.data[0]["name"], "Client")
        self.assertEqual(
            self.api.post(
                f"/api/messaging/conversations/{self.conversation.id}/mark-read/"
            ).status_code,
            200,
        )

    def test_generic_django_staff_cannot_access_private_messaging(self):
        self.api.force_authenticate(self.cms_editor)
        self.assertEqual(
            self.api.get("/api/messaging/conversations/").status_code,
            403,
        )
        self.assertEqual(
            self.api.get("/api/messaging/clients/").status_code,
            403,
        )
        self.assertEqual(
            self.api.post(
                f"/api/messaging/conversations/{self.conversation.id}/mark-read/"
            ).status_code,
            403,
        )

# Create your tests here.
