import logging

import resend
from django.conf import settings
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response

from clients.permissions import IsPortalStaff

from .models import ContactMessage
from .serializers import (
    ContactMessageSerializer,
    ContactMessageSubmissionSerializer,
)
from .throttles import ContactSubmissionRateThrottle

logger = logging.getLogger(__name__)

PUBLIC_SUBMISSION_RESPONSE = {
    "message": "Message received!",
    "email_notification": "sent",
}


@api_view(["GET"])
@permission_classes([IsAuthenticated, IsPortalStaff])
def get_messages(request):
    """List contact submissions for authorized private-platform staff."""
    messages = ContactMessage.objects.all().order_by("-submitted_at")
    serializer = ContactMessageSerializer(messages, many=True)
    return Response(serializer.data)


@api_view(["POST"])
@permission_classes([AllowAny])
def submit_contact(request):
    honeypot = request.data.get("website", "")
    if not isinstance(honeypot, str) or honeypot.strip():
        return Response(PUBLIC_SUBMISSION_RESPONSE, status=status.HTTP_201_CREATED)

    throttle = ContactSubmissionRateThrottle()
    if not throttle.allow_request(request, submit_contact):
        return Response(
            {"message": "Unable to process your request right now."},
            status=status.HTTP_429_TOO_MANY_REQUESTS,
        )

    serializer = ContactMessageSubmissionSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    contact_message = serializer.save()

    notification_status = "sent"
    try:
        resend.api_key = settings.RESEND_API_KEY
        safe_name = contact_message.name.replace("\r", " ").replace("\n", " ")
        resend.Emails.send(
            {
                "from": settings.EMAIL_FROM,
                "to": settings.CONTACT_EMAIL,
                "subject": f"New contact from {safe_name}",
                "text": (
                    f"Name: {contact_message.name}\n"
                    f"Email: {contact_message.email}\n"
                    f"Organisation: {contact_message.organisation}\n"
                    f"Service: {contact_message.service}\n"
                    f"Message: {contact_message.message}"
                ),
            }
        )
    except Exception:
        notification_status = "failed"
        logger.exception(
            "Contact notification email failed for contact_message_id=%s",
            contact_message.pk,
        )

    response_data = {
        **PUBLIC_SUBMISSION_RESPONSE,
        "email_notification": notification_status,
    }
    return Response(response_data, status=status.HTTP_201_CREATED)
