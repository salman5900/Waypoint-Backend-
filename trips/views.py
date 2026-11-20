from rest_framework.views import APIView
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework import status
from rest_framework.exceptions import ValidationError as DRFValidationError

from core.responses import success_response
from core.exceptions import TripNotFoundError, PermissionDeniedError
from .serializers import (
    TripGenerateRequestSerializer,
    TripPlanSerializer,
    TripPlanSummarySerializer,
    EmailRoadmapRequestSerializer,
)
from . import selectors
from . import services


class HealthCheckView(APIView):
    permission_classes = [AllowAny]

    def get(self, request):
        db_connected = selectors.check_database_connection()
        data = {
            "status": "ok",
            "database": "connected" if db_connected else "disconnected",
        }
        return success_response(data=data, status_code=status.HTTP_200_OK)


class TripGenerateView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = TripGenerateRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        validated = serializer.validated_data

        trip_plan = services.generate_trip_plan(
            origin=validated["origin"],
            destination=validated["destination"],
            days=validated["days"],
            members=validated.get("members", 1),
            budget=validated.get("budget"),
            currency=validated.get("currency", "USD"),
            travel_style=validated.get("travel_style", ""),
            extra_notes=validated.get("extra_notes", ""),
            user=request.user if request.user.is_authenticated else None,
        )

        data = {
            "id": trip_plan.id,
            "origin": trip_plan.origin,
            "destination": trip_plan.destination,
            "days": trip_plan.days,
            "itinerary": trip_plan.itinerary_json,
        }
        return success_response(data=data, status_code=status.HTTP_201_CREATED)


class TripListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        trips = selectors.get_user_trips(request.user)
        serializer = TripPlanSummarySerializer(trips, many=True)
        return success_response(data=serializer.data, status_code=status.HTTP_200_OK)


class TripDetailView(APIView):
    permission_classes = [AllowAny]

    def get(self, request, pk: int):
        trip = selectors.get_trip_by_id(pk)
        if not trip:
            raise TripNotFoundError(f"Trip with ID {pk} does not exist.")

        if trip.user_id is not None:
            if not request.user or not request.user.is_authenticated or request.user.id != trip.user_id:
                raise PermissionDeniedError("You do not have permission to view this trip.")

        serializer = TripPlanSerializer(trip)
        return success_response(data=serializer.data, status_code=status.HTTP_200_OK)


class TripEmailRoadmapView(APIView):
    permission_classes = [AllowAny]

    def post(self, request, pk: int):
        serializer = EmailRoadmapRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        recipient_email = serializer.validated_data.get("email")
        if not recipient_email:
            if request.user and request.user.is_authenticated and request.user.email:
                recipient_email = request.user.email
            else:
                raise DRFValidationError({"email": "Recipient email address must be provided."})

        # Verify access permission if owned by a specific user
        trip = selectors.get_trip_by_id(pk)
        if not trip:
            raise TripNotFoundError(f"Trip with ID {pk} does not exist.")

        if trip.user_id is not None:
            if not request.user or not request.user.is_authenticated or request.user.id != trip.user_id:
                raise PermissionDeniedError("You do not have permission to email this trip.")

        result = services.send_trip_roadmap_email(
            trip_id=pk,
            recipient_email=recipient_email,
        )
        return success_response(data=result, status_code=status.HTTP_200_OK)
