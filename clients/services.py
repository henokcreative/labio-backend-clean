from urllib.parse import urlencode, urlsplit, urlunsplit

from django.conf import settings
from django.contrib.auth.tokens import default_token_generator
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode

import resend

from .tokens import password_reset_token_generator


def invitation_url(user):
    query = urlencode({
        "uid": urlsafe_base64_encode(force_bytes(user.pk)),
        "token": default_token_generator.make_token(user),
    })
    return f"{settings.INVITATION_FRONTEND_URL}?{query}"


def password_reset_url(user):
    configured_url = settings.PASSWORD_RESET_FRONTEND_URL
    if configured_url:
        base_url = configured_url
    else:
        invitation_url_parts = urlsplit(settings.INVITATION_FRONTEND_URL)
        base_url = urlunsplit(
            (
                invitation_url_parts.scheme,
                invitation_url_parts.netloc,
                "/reset-password",
                "",
                "",
            )
        )
    query = urlencode({
        "uid": urlsafe_base64_encode(force_bytes(user.pk)),
        "token": password_reset_token_generator.make_token(user),
    })
    return f"{base_url}?{query}"


def send_invitation_email(user):
    """Email a client a single-use password-setup link."""

    url = invitation_url(user)
    name = user.get_full_name() or user.username

    resend.api_key = settings.RESEND_API_KEY

    resend.Emails.send({
        "from": settings.EMAIL_FROM,
        "to": user.email,
        "subject": "Set up your LaBioMedia client account",
        "text": (
            f"Hello {name},\n\n"
            "Your LaBioMedia client account is ready.\n\n"
            f"Set your password using this link:\n{url}\n\n"
            "This link can be used once and expires in 72 hours.\n\n"
            "If you did not expect this invitation, you can safely ignore "
            "this email."
        ),
    })

    return url


def send_password_reset_email(user):
    """Email a time-limited, single-purpose Django password-reset link."""

    url = password_reset_url(user)
    name = user.get_full_name() or user.username

    resend.api_key = settings.RESEND_API_KEY
    resend.Emails.send({
        "from": settings.EMAIL_FROM,
        "to": user.email,
        "subject": "Reset your LaBio Media password",
        "text": (
            f"Hello {name},\n\n"
            "We received a request to reset your LaBio Media password.\n\n"
            f"Set a new password using this link:\n{url}\n\n"
            "This link is time-limited and stops working after your password "
            "is changed.\n\n"
            "If you did not request a reset, you can safely ignore this email."
        ),
    })
    return url
