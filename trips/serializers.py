from rest_framework import serializers
from .models import TripPlan


class TripGenerateRequestSerializer(serializers.Serializer):
    origin = serializers.CharField(max_length=255, required=True, trim_whitespace=True)
    destination = serializers.CharField(max_length=255, required=True, trim_whitespace=True)
    days = serializers.IntegerField(min_value=1, max_value=30, required=True)
    members = serializers.IntegerField(min_value=1, max_value=50, required=False, default=1)
    budget = serializers.DecimalField(max_digits=12, decimal_places=2, required=False, allow_null=True, default=None)
    currency = serializers.CharField(max_length=10, required=False, default="USD")
    travelStyle = serializers.CharField(max_length=100, required=False, allow_blank=True, default="")
    travel_style = serializers.CharField(max_length=100, required=False, allow_blank=True, default="")
    extraNotes = serializers.CharField(required=False, allow_blank=True, default="")
    extra_notes = serializers.CharField(required=False, allow_blank=True, default="")

    def validate(self, attrs):
        # Normalize camelCase and snake_case inputs from React frontend
        style = attrs.get('travelStyle') or attrs.get('travel_style') or ""
        notes = attrs.get('extraNotes') or attrs.get('extra_notes') or ""
        attrs['travel_style'] = style
        attrs['extra_notes'] = notes
        return attrs


class TripPlanSerializer(serializers.ModelSerializer):
    travelStyle = serializers.CharField(source='travel_style', read_only=True)
    extraNotes = serializers.CharField(source='extra_notes', read_only=True)
    itinerary = serializers.JSONField(source='itinerary_json', read_only=True)
    createdAt = serializers.DateTimeField(source='created_at', read_only=True)

    class Meta:
        model = TripPlan
        fields = [
            'id',
            'origin',
            'destination',
            'days',
            'members',
            'budget',
            'currency',
            'travelStyle',
            'travel_style',
            'extraNotes',
            'extra_notes',
            'itinerary',
            'itinerary_json',
            'createdAt',
            'created_at',
        ]
        read_only_fields = fields


class TripPlanSummarySerializer(serializers.ModelSerializer):
    """Lighter serializer for listing trips."""
    travelStyle = serializers.CharField(source='travel_style', read_only=True)
    createdAt = serializers.DateTimeField(source='created_at', read_only=True)
    tripTitle = serializers.SerializerMethodField()

    class Meta:
        model = TripPlan
        fields = [
            'id',
            'tripTitle',
            'origin',
            'destination',
            'days',
            'members',
            'budget',
            'currency',
            'travelStyle',
            'createdAt',
        ]

    def get_tripTitle(self, obj) -> str:
        if isinstance(obj.itinerary_json, dict):
            return obj.itinerary_json.get('tripTitle', f"{obj.origin} to {obj.destination}")
        return f"{obj.origin} to {obj.destination}"


class EmailRoadmapRequestSerializer(serializers.Serializer):
    email = serializers.EmailField(required=False, allow_null=True, allow_blank=True, default=None)
