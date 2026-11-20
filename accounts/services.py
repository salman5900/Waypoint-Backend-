import re
import secrets
from datetime import timedelta
from typing import Dict, Any

from django.contrib.auth import get_user_model
from django.contrib.auth.hashers import make_password, check_password
from django.core.mail import send_mail
from django.db import transaction
from django.utils import timezone
from rest_framework_simplejwt.tokens import RefreshToken

from core.exceptions import (
    InvalidOTPError,
    OTPExpiredError,
    OTPMaxAttemptsError,
    OTPNotFoundError,
    AuthenticationFailedError,
    UserAlreadyExistsError,
)
from .models import EmailOTP
from .selectors import (
    get_user_by_email,
    get_user_by_identifier,
    user_exists_by_email,
    user_exists_by_username,
    get_latest_otp,
    get_latest_active_otp,
)

User = get_user_model()

MAX_OTP_ATTEMPTS = 5
OTP_EXPIRY_MINUTES = 10


def generate_tokens_for_user(user: User) -> Dict[str, str]:
    """Generate JWT access and refresh tokens for a user instance."""
    refresh = RefreshToken.for_user(user)
    return {
        "access": str(refresh.access_token),
        "refresh": str(refresh),
    }


def register_user(username: str, email: str, password: str) -> Dict[str, Any]:
    """
    Registers a new user with classical email + password authentication.
    Returns access, refresh tokens, and user profile data.
    """
    clean_email = email.strip().lower()
    clean_username = username.strip()

    if user_exists_by_email(clean_email):
        raise UserAlreadyExistsError("A user with this email address already exists.")

    if user_exists_by_username(clean_username):
        raise UserAlreadyExistsError("A user with this username already exists.")

    user = User.objects.create_user(
        username=clean_username,
        email=clean_email,
        password=password,
    )

    tokens = generate_tokens_for_user(user)

    return {
        "access": tokens["access"],
        "refresh": tokens["refresh"],
        "user": {
            "id": user.id,
            "username": user.username,
            "email": user.email,
        },
    }


def authenticate_user(identifier: str, password: str) -> Dict[str, Any]:
    """
    Authenticates a user via either username or email and password.
    Returns access, refresh tokens, and user profile data.
    """
    user = get_user_by_identifier(identifier)

    if not user or not user.check_password(password):
        raise AuthenticationFailedError("Invalid username/email or password.")

    if not user.is_active:
        raise AuthenticationFailedError("This account is currently disabled.")

    tokens = generate_tokens_for_user(user)

    return {
        "access": tokens["access"],
        "refresh": tokens["refresh"],
        "user": {
            "id": user.id,
            "username": user.username,
            "email": user.email,
        },
    }


def request_email_otp(email: str) -> Dict[str, Any]:
    """
    Generates a cryptographically secure 6-digit OTP, stores its hash,
    invalidates older pending OTPs for the email, and dispatches the email.
    """
    clean_email = email.strip().lower()

    # Invalidate older pending OTPs for this email
    EmailOTP.objects.filter(email__iexact=clean_email, is_used=False).update(is_used=True)

    # Cryptographically random 6-digit code
    raw_code = f"{secrets.randbelow(1_000_000):06d}"
    code_hash = make_password(raw_code)
    expires_at = timezone.now() + timedelta(minutes=OTP_EXPIRY_MINUTES)

    EmailOTP.objects.create(
        email=clean_email,
        code_hash=code_hash,
        expires_at=expires_at,
        is_used=False,
        attempts=0,
    )

    # Dispatch OTP via configured email backend
    subject = "Your Waypoint Verification Code"
    message = (
        f"Hello,\n\n"
        f"Your Waypoint one-time login code is: {raw_code}\n\n"
        f"This code will expire in {OTP_EXPIRY_MINUTES} minutes. "
        f"If you did not request this code, you can safely ignore this email.\n\n"
        f"Happy travels,\n"
        f"The Waypoint Team"
    )

    send_mail(
        subject=subject,
        message=message,
        from_email=None,  # Uses DEFAULT_FROM_EMAIL
        recipient_list=[clean_email],
        fail_silently=False,
    )

    return {
        "email": clean_email,
        "expires_in_minutes": OTP_EXPIRY_MINUTES,
    }


def verify_email_otp(email: str, code: str) -> Dict[str, Any]:
    """
    Validates the supplied OTP against the hashed code.
    If valid, atomically gets or creates the user, marks the OTP as used,
    and returns JWT credentials.
    """
    clean_email = email.strip().lower()
    clean_code = str(code).strip()

    otp = get_latest_otp(clean_email)

    if not otp:
        raise OTPNotFoundError("No active OTP request found for this email. Please request a new code.")

    if otp.is_used:
        if otp.attempts >= MAX_OTP_ATTEMPTS:
            raise OTPMaxAttemptsError("Maximum verification attempts exceeded. Please request a new OTP.")
        raise OTPNotFoundError("This OTP has already been used. Please request a new code.")

    if otp.attempts >= MAX_OTP_ATTEMPTS:
        otp.is_used = True
        otp.save(update_fields=['is_used'])
        raise OTPMaxAttemptsError("Maximum verification attempts exceeded. Please request a new OTP.")

    if otp.is_expired():
        otp.is_used = True
        otp.save(update_fields=['is_used'])
        raise OTPExpiredError("OTP code has expired. Please request a new code.")

    if not check_password(clean_code, otp.code_hash):
        otp.attempts += 1
        if otp.attempts >= MAX_OTP_ATTEMPTS:
            otp.is_used = True
            otp.save(update_fields=['attempts', 'is_used'])
            raise OTPMaxAttemptsError("Maximum verification attempts exceeded. Please request a new OTP.")
        otp.save(update_fields=['attempts'])
        remaining = MAX_OTP_ATTEMPTS - otp.attempts
        raise InvalidOTPError(f"Invalid verification code. {remaining} attempt(s) remaining.")

    # OTP is valid: consume it atomically and retrieve/create the user
    with transaction.atomic():
        otp.is_used = True
        otp.save(update_fields=['is_used'])

        user = get_user_by_email(clean_email)
        is_new_user = False

        if not user:
            # Auto-generate a clean username from email prefix + 4-char hex
            prefix = clean_email.split('@')[0]
            clean_prefix = re.sub(r'[^a-zA-Z0-9_]', '', prefix)[:20] or "traveler"
            username = f"{clean_prefix}_{secrets.token_hex(2)}"

            while user_exists_by_username(username):
                username = f"{clean_prefix}_{secrets.token_hex(2)}"

            user = User.objects.create_user(
                username=username,
                email=clean_email,
            )
            user.set_unusable_password()
            user.save()
            is_new_user = True

    tokens = generate_tokens_for_user(user)

    return {
        "access": tokens["access"],
        "refresh": tokens["refresh"],
        "isNewUser": is_new_user,
        "user": {
            "id": user.id,
            "username": user.username,
            "email": user.email,
        },
    }
