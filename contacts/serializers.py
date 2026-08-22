from rest_framework import serializers

from .models import ContactMessage


class ContactMessageSerializer(serializers.ModelSerializer):
    class Meta:
        model = ContactMessage
        fields = '__all__'


class ContactMessageSubmissionSerializer(serializers.ModelSerializer):
    """Public input fields for a new contact request."""

    name = serializers.CharField(
        min_length=2,
        max_length=100,
        trim_whitespace=True,
    )
    email = serializers.EmailField(max_length=254)
    organisation = serializers.CharField(
        required=False,
        allow_blank=True,
        max_length=150,
        trim_whitespace=True,
    )
    service = serializers.CharField(
        required=False,
        allow_blank=True,
        max_length=50,
        trim_whitespace=True,
    )
    message = serializers.CharField(
        min_length=10,
        max_length=5000,
        trim_whitespace=True,
    )
    class Meta:
        model = ContactMessage
        fields = [
            "name",
            "email",
            "organisation",
            "service",
            "message",
        ]
