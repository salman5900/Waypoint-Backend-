from django.contrib import admin
from django.urls import path, include
from trips.views import HealthCheckView

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/health/', HealthCheckView.as_view(), name='api-health'),
    path('api/auth/', include('accounts.urls')),
    path('api/trips/', include('trips.urls')),
]
