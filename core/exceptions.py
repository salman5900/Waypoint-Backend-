import logging
from rest_framework.views import exception_handler
from rest_framework.response import Response
from rest_framework import status
from rest_framework.exceptions import (
    APIException,
    ValidationError as DRFValidationError,
    AuthenticationFailed as DRFAuthenticationFailed,
    NotAuthenticated as DRFNotAuthenticated,
    PermissionDenied as DRFPermissionDenied,
    NotFound as DRFNotFound,
    MethodNotAllowed as DRFMethodNotAllowed,
)
from django.http import Http404

logger = logging.getLogger(__name__)


class ApplicationError(Exception):
    """Base domain exception for Waypoint application."""
    default_message = "An unexpected domain error occurred."
    default_code = "APPLICATION_ERROR"
    status_code = status.HTTP_400_BAD_REQUEST

    def __init__(self, message=None, code=None, status_code=None, details=None):
        self.message = message or self.default_message
        self.code = code or self.default_code
        if status_code is not None:
            self.status_code = status_code
        self.details = details
        super().__init__(self.message)


class InvalidOTPError(ApplicationError):
    default_message = "Invalid OTP code provided."
    default_code = "INVALID_OTP"
    status_code = status.HTTP_400_BAD_REQUEST


class OTPExpiredError(ApplicationError):
    default_message = "OTP code has expired. Please request a new code."
    default_code = "OTP_EXPIRED"
    status_code = status.HTTP_400_BAD_REQUEST


class OTPMaxAttemptsError(ApplicationError):
    default_message = "Maximum verification attempts exceeded. Please request a new OTP."
    default_code = "OTP_MAX_ATTEMPTS_EXCEEDED"
    status_code = status.HTTP_400_BAD_REQUEST


class OTPNotFoundError(ApplicationError):
    default_message = "No active OTP request found for this email."
    default_code = "OTP_NOT_FOUND"
    status_code = status.HTTP_404_NOT_FOUND


class AuthenticationFailedError(ApplicationError):
    default_message = "Invalid credentials provided."
    default_code = "AUTHENTICATION_FAILED"
    status_code = status.HTTP_401_UNAUTHORIZED


class UserAlreadyExistsError(ApplicationError):
    default_message = "User with this email or username already exists."
    default_code = "USER_ALREADY_EXISTS"
    status_code = status.HTTP_400_BAD_REQUEST


class AIServiceError(ApplicationError):
    default_message = "AI travel concierge service encountered an error."
    default_code = "AI_SERVICE_ERROR"
    status_code = status.HTTP_502_BAD_GATEWAY


class TripNotFoundError(ApplicationError):
    default_message = "Trip plan not found."
    default_code = "TRIP_NOT_FOUND"
    status_code = status.HTTP_404_NOT_FOUND


class PermissionDeniedError(ApplicationError):
    default_message = "You do not have permission to access this resource."
    default_code = "PERMISSION_DENIED"
    status_code = status.HTTP_403_FORBIDDEN


def custom_exception_handler(exc, context):
    """
    Centralized DRF Exception Handler.
    Ensures all responses conform strictly to the standardized envelope:
    {
        "success": False,
        "error": {
            "code": "ERROR_CODE",
            "message": "Human readable message",
            "details": ... (optional)
        }
    }
    """
    # 1. Custom Domain Application Errors
    if isinstance(exc, ApplicationError):
        error_payload = {
            "code": exc.code,
            "message": exc.message,
        }
        if exc.details is not None:
            error_payload["details"] = exc.details

        return Response(
            {
                "success": False,
                "error": error_payload,
            },
            status=exc.status_code,
        )

    # 2. Standard DRF and Django Exceptions
    response = exception_handler(exc, context)

    if response is not None:
        code = "REQUEST_FAILED"
        message = "A request processing error occurred."
        details = response.data

        if isinstance(exc, DRFValidationError):
            code = "VALIDATION_ERROR"
            message = "Validation failed for one or more fields."
            # Extract first error message if available for readability
            if isinstance(response.data, dict):
                first_key = next(iter(response.data), None)
                if first_key and isinstance(response.data[first_key], list) and len(response.data[first_key]) > 0:
                    message = str(response.data[first_key][0])
            elif isinstance(response.data, list) and len(response.data) > 0:
                message = str(response.data[0])

        elif isinstance(exc, (DRFNotAuthenticated,)):
            code = "NOT_AUTHENTICATED"
            message = "Authentication credentials were not provided."

        elif isinstance(exc, (DRFAuthenticationFailed,)):
            code = "AUTHENTICATION_FAILED"
            message = str(response.data.get("detail", "Authentication failed."))

        elif isinstance(exc, (DRFPermissionDenied,)):
            code = "PERMISSION_DENIED"
            message = str(response.data.get("detail", "You do not have permission to perform this action."))

        elif isinstance(exc, (DRFNotFound, Http404)):
            code = "NOT_FOUND"
            message = str(response.data.get("detail", "The requested resource was not found."))

        elif isinstance(exc, DRFMethodNotAllowed):
            code = "METHOD_NOT_ALLOWED"
            req = context.get("request")
            method = req.method if req else "Request"
            message = f"Method '{method}' not allowed."

        elif isinstance(exc, APIException):
            code = getattr(exc, "default_code", "API_ERROR").upper()
            if isinstance(response.data, dict) and "detail" in response.data:
                message = str(response.data["detail"])

        error_payload = {
            "code": code,
            "message": message,
        }
        if details is not None and not (isinstance(details, dict) and list(details.keys()) == ["detail"]):
            error_payload["details"] = details

        return Response(
            {
                "success": False,
                "error": error_payload,
            },
            status=response.status_code,
        )

    # 3. Unhandled Python Exceptions (500)
    logger.exception("Unhandled server exception occurred: %s", exc)
    return Response(
        {
            "success": False,
            "error": {
                "code": "INTERNAL_SERVER_ERROR",
                "message": "An internal server error occurred.",
            },
        },
        status=status.HTTP_500_INTERNAL_SERVER_ERROR,
    )
