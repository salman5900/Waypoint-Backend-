from typing import Optional
from django.db import connection
from django.db.models import QuerySet
from .models import TripPlan


def get_trip_by_id(trip_id: int) -> Optional[TripPlan]:
    """Retrieve a single TripPlan by its primary key."""
    try:
        return TripPlan.objects.select_related('user').get(id=trip_id)
    except TripPlan.DoesNotExist:
        return None


def get_user_trips(user) -> QuerySet[TripPlan]:
    """Retrieve all trips owned by the specified user, ordered by creation date desc."""
    if not user or not user.is_authenticated:
        return TripPlan.objects.none()
    return TripPlan.objects.filter(user=user).order_by('-created_at')


def check_database_connection() -> bool:
    """Executes a ping query to verify healthy PostgreSQL database connectivity."""
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1;")
            row = cursor.fetchone()
            return row is not None and row[0] == 1
    except Exception:
        return False
