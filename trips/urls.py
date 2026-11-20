from django.urls import path
from .views import (
    TripGenerateView,
    TripListView,
    TripDetailView,
    TripEmailRoadmapView,
)

urlpatterns = [
    path('generate/', TripGenerateView.as_view(), name='trip-generate'),
    path('', TripListView.as_view(), name='trip-list'),
    path('<int:pk>/', TripDetailView.as_view(), name='trip-detail'),
    path('<int:pk>/email-roadmap/', TripEmailRoadmapView.as_view(), name='trip-email-roadmap'),
]
