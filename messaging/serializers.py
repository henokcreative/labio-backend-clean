from rest_framework import serializers
from .models import Conversation, Message
from django.contrib.auth.models import User

from clients.permissions import has_portal_staff_access

class SimpleUserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['id', 'username', 'first_name', 'last_name']

class MessageSerializer(serializers.ModelSerializer):
    sender_username = serializers.CharField(source='sender.username', read_only=True)
    sender_name = serializers.SerializerMethodField()
    sender_role = serializers.SerializerMethodField()
    content = serializers.CharField(source='body', read_only=True)

    class Meta:
        model = Message
        fields = [
            'id',
            'body',
            'content',
            'sender_username',
            'sender_name',
            'sender_role',
            'is_read',
            'created_at',
        ]

    def get_sender_name(self, obj):
        if obj.sender_id == obj.conversation.client_id:
            client_profile = getattr(obj.sender, 'client_profile', None)
            if client_profile:
                return client_profile.name
        return obj.sender.get_full_name()

    def get_sender_role(self, obj):
        return 'client' if obj.sender_id == obj.conversation.client_id else 'staff'

class ConversationSerializer(serializers.ModelSerializer):
    messages = MessageSerializer(many=True, read_only=True)
    client_username = serializers.CharField(source='client.username', read_only=True)
    client_name = serializers.SerializerMethodField()
    assigned_staff_username = serializers.CharField(source='assigned_staff.username', read_only=True, allow_null=True)
    assigned_staff_name = serializers.CharField(source='assigned_staff.get_full_name', read_only=True, allow_null=True)
    project_id = serializers.IntegerField(source='project.id', read_only=True, allow_null=True)
    project_title = serializers.CharField(source='project.title', read_only=True, allow_null=True)
    unread_count = serializers.SerializerMethodField()

    class Meta:
        model = Conversation
        fields = [
            'id',
            'subject',
            'client_username',
            'client_name',
            'assigned_staff_username',
            'assigned_staff_name',
            'project_id',
            'project_title',
            'unread_count',
            'created_at',
            'updated_at',
            'messages',
        ]

    def get_client_name(self, obj):
        client_profile = getattr(obj.client, 'client_profile', None)
        if client_profile:
            return client_profile.name
        return obj.client.get_full_name()

    def get_unread_count(self, obj):
        request = self.context.get('request')
        unread = obj.messages.filter(is_read=False)
        if request and has_portal_staff_access(request.user):
            return unread.filter(sender_id=obj.client_id).count()
        return unread.exclude(sender_id=obj.client_id).count()
