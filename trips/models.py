from django.db import models
from django.conf import settings


class TripPlan(models.Model):
    """
    Stores an AI-generated trip itinerary and associated user trip parameters.
    User is optional (null=True) to allow unauthenticated frontend testing.
    """
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name='trips',
    )
    origin = models.CharField(max_length=255)
    destination = models.CharField(max_length=255)
    days = models.PositiveIntegerField()
    members = models.PositiveIntegerField(default=1)
    budget = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    currency = models.CharField(max_length=10, default='USD')
    travel_style = models.CharField(max_length=100, blank=True, default='')
    extra_notes = models.TextField(blank=True, default='')
    itinerary_json = models.JSONField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user', '-created_at']),
        ]
        verbose_name = 'Trip Plan'
        verbose_name_plural = 'Trip Plans'

    def __str__(self):
        owner = self.user.username if self.user else "Anonymous"
        return f"Trip {self.id}: {self.origin} -> {self.destination} ({self.days} days) [{owner}]"
