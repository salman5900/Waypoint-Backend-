from rest_framework.views import APIView
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework import status

from core.responses import success_response
from .serializers import (
    RegisterRequestSerializer,
    LoginRequestSerializer,
    RequestOTPRequestSerializer,
    VerifyOTPRequestSerializer,
    UserResponseSerializer,
)
from . import services


class RegisterView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = RegisterRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = services.register_user(
            username=serializer.validated_data["username"],
            email=serializer.validated_data["email"],
            password=serializer.validated_data["password"],
        )
        return success_response(data=data, status_code=status.HTTP_201_CREATED)


class LoginView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = LoginRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = services.authenticate_user(
            identifier=serializer.validated_data["identifier"],
            password=serializer.validated_data["password"],
        )
        return success_response(data=data, status_code=status.HTTP_200_OK)


class RequestOTPView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = RequestOTPRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = services.request_email_otp(
            email=serializer.validated_data["email"]
        )
        return success_response(data=data, status_code=status.HTTP_200_OK)


class VerifyOTPView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = VerifyOTPRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = services.verify_email_otp(
            email=serializer.validated_data["email"],
            code=serializer.validated_data["code"],
        )
        return success_response(data=data, status_code=status.HTTP_200_OK)


class MeView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        serializer = UserResponseSerializer(request.user)
        return success_response(data=serializer.data, status_code=status.HTTP_200_OK)
