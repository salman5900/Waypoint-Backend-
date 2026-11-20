from django.urls import path
from .views import (
    RegisterView,
    LoginView,
    RequestOTPView,
    VerifyOTPView,
    MeView,
)

urlpatterns = [
    path('register/', RegisterView.as_view(), name='auth-register'),
    path('login/', LoginView.as_view(), name='auth-login'),
    path('request-otp/', RequestOTPView.as_view(), name='auth-request-otp'),
    path('verify-otp/', VerifyOTPView.as_view(), name='auth-verify-otp'),
    path('me/', MeView.as_view(), name='auth-me'),
]
