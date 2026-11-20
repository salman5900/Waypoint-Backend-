from rest_framework.response import Response
from rest_framework import status


def success_response(data=None, status_code=status.HTTP_200_OK):
    """
    Standardized API success envelope:
    {
        "success": True,
        "data": { ... }
    }
    """
    payload = {
        "success": True,
        "data": data if data is not None else {}
    }
    return Response(payload, status=status_code)


def error_response(code="ERROR", message="An error occurred", details=None, status_code=status.HTTP_400_BAD_REQUEST):
    """
    Standardized API error envelope:
    {
        "success": False,
        "error": {
            "code": "ERROR_CODE",
            "message": "Human readable message",
            "details": ... (optional)
        }
    }
    """
    error_payload = {
        "code": code,
        "message": message,
    }
    if details is not None:
        error_payload["details"] = details

    return Response({
        "success": False,
        "error": error_payload
    }, status=status_code)
