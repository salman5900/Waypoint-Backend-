from typing import Optional
from django.contrib.auth import get_user_model
from django.db.models import Q
from .models import EmailOTP

User = get_user_model()


def get_user_by_id(user_id: int) -> Optional[User]:
    """Retrieve user by primary key."""
    try:
        return User.objects.get(id=user_id)
    except User.DoesNotExist:
        return None


def get_user_by_email(email: str) -> Optional[User]:
    """Retrieve user by case-insensitive email."""
    if not email:
        return None
    try:
        return User.objects.get(email__iexact=email.strip())
    except User.DoesNotExist:
        return None


def get_user_by_username(username: str) -> Optional[User]:
    """Retrieve user by username."""
    if not username:
        return None
    try:
        return User.objects.get(username=username.strip())
    except User.DoesNotExist:
        return None


def get_user_by_identifier(identifier: str) -> Optional[User]:
    """Retrieve user by username OR email."""
    if not identifier:
        return None
    clean_identifier = identifier.strip()
    return User.objects.filter(
        Q(username__iexact=clean_identifier) | Q(email__iexact=clean_identifier)
    ).first()


def user_exists_by_email(email: str) -> bool:
    """Check if a user exists with the given email."""
    if not email:
        return False
    return User.objects.filter(email__iexact=email.strip()).exists()


def user_exists_by_username(username: str) -> bool:
    """Check if a user exists with the given username."""
    if not username:
        return False
    return User.objects.filter(username=username.strip()).exists()


def get_latest_otp(email: str) -> Optional[EmailOTP]:
    """Retrieve the latest OTP record for the specified email regardless of status."""
    if not email:
        return None
    return EmailOTP.objects.filter(email__iexact=email.strip()).order_by('-created_at').first()


def get_latest_active_otp(email: str) -> Optional[EmailOTP]:
    """Retrieve the latest unused and unexpired OTP for the specified email."""
    if not email:
        return None
    return EmailOTP.objects.filter(
        email__iexact=email.strip(),
        is_used=False
    ).order_by('-created_at').first()
