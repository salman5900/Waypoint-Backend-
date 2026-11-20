from django.db import models
from django.contrib.auth.models import AbstractUser
from django.utils import timezone


class User(AbstractUser):
    """Custom User model with unique email and customizable username."""
    email = models.EmailField(unique=True, db_index=True)

    REQUIRED_FIELDS = ['email']

    class Meta:
        ordering = ['id']
        verbose_name = 'User'
        verbose_name_plural = 'Users'

    def __str__(self):
        return self.username or self.email


class EmailOTP(models.Model):
    """
    Stores cryptographically hashed one-time passwords for passwordless authentication.
    Raw OTP codes are never stored.
    """
    email = models.EmailField(db_index=True)
    code_hash = models.CharField(max_length=255)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
    attempts = models.PositiveSmallIntegerField(default=0)
    is_used = models.BooleanField(default=False)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['email', 'is_used', 'expires_at']),
        ]
        verbose_name = 'Email OTP'
        verbose_name_plural = 'Email OTPs'

    def is_expired(self) -> bool:
        return timezone.now() > self.expires_at

    def __str__(self):
        return f"OTP for {self.email} (used={self.is_used}, attempts={self.attempts})"
