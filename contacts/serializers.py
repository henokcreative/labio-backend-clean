from rest_framework import serializers

from .models import ContactMessage


class ContactMessageSerializer(serializers.ModelSerializer):
    class Meta:
        model = ContactMessage
        fields = '__all__'


class ContactMessageSubmissionSerializer(serializers.ModelSerializer):
    """Public input fields for a new contact request."""

    class Meta:
        model = ContactMessage
        fields = [
            "name",
            "email",
            "organisation",
            "service",
            "message",
        ]
