from django.contrib.auth.tokens import PasswordResetTokenGenerator


class PortalPasswordResetTokenGenerator(PasswordResetTokenGenerator):
    key_salt = "clients.tokens.PortalPasswordResetTokenGenerator"


password_reset_token_generator = PortalPasswordResetTokenGenerator()
