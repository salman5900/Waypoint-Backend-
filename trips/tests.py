from unittest.mock import patch, MagicMock
from django.contrib.auth import get_user_model
from django.core import mail
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from core.exceptions import AIServiceError
from trips.models import TripPlan
from trips.schemas import (
    TripItinerarySchema,
    BudgetBreakdown,
    FlightOption,
    HotelRecommendation,
    DayPlan,
    ActivityItem,
    RestaurantPick,
)
from trips import services

User = get_user_model()


def get_mock_itinerary_schema(num_days: int = 3) -> TripItinerarySchema:
    days_list = []
    for d in range(1, num_days + 1):
        days_list.append(
            DayPlan(
                day=d,
                theme=f"Day {d} Exploration & Culture",
                activities=[
                    ActivityItem(
                        time="09:00 AM",
                        title=f"Historic Landmark Visit {d}",
                        category="sightseeing",
                        description=f"Morning cultural exploration on day {d}.",
                        estimatedCost=500.0,
                        mapOrBookingUrl="https://www.google.com/maps/search/?api=1&query=Tokyo+Landmark",
                        imageUrl="https://images.unsplash.com/photo-1503899036084-c55cdd92da26?auto=format&fit=crop&w=800&q=80",
                    ),
                    ActivityItem(
                        time="02:00 PM",
                        title=f"Afternoon Scenic Walk {d}",
                        category="experience",
                        description=f"Afternoon scenic garden and neighborhood stroll on day {d}.",
                        estimatedCost=0.0,
                        mapOrBookingUrl="https://www.google.com/maps/search/?api=1&query=Tokyo+Park",
                        imageUrl="https://images.unsplash.com/photo-1542051841857-5f90071e7989?auto=format&fit=crop&w=800&q=80",
                    ),
                ],
                restaurantPicks=[
                    RestaurantPick(
                        name=f"Authentic Lunch Spot {d}",
                        cuisine="Japanese Ramen",
                        priceRange="$$",
                        signatureDish="Specialty Broth Ramen",
                        mapUrl="https://www.google.com/maps/search/?api=1&query=Tokyo+Ramen",
                        imageUrl="https://images.unsplash.com/photo-1569718212165-3a8278d5f624?auto=format&fit=crop&w=800&q=80",
                    ),
                    RestaurantPick(
                        name=f"Curated Dinner Spot {d}",
                        cuisine="Japanese Izakaya",
                        priceRange="$$$",
                        signatureDish="Yakitori Platter & Sake",
                        mapUrl="https://www.google.com/maps/search/?api=1&query=Tokyo+Izakaya",
                        imageUrl="https://images.unsplash.com/photo-1517248135467-4c7edcad34c4?auto=format&fit=crop&w=800&q=80",
                    ),
                ],
            )
        )

    return TripItinerarySchema(
        tripTitle="Tokyo Exploration: Neon & Tradition",
        summary="A comprehensive multi-day journey through Tokyo.",
        heroImages=[
            "https://images.unsplash.com/photo-1503899036084-c55cdd92da26?auto=format&fit=crop&w=1200&q=80",
            "https://images.unsplash.com/photo-1536098561742-ca998e48cbcc?auto=format&fit=crop&w=1200&q=80",
            "https://images.unsplash.com/photo-1542051841857-5f90071e7989?auto=format&fit=crop&w=1200&q=80",
            "https://images.unsplash.com/photo-1509042239860-f550ce710b93?auto=format&fit=crop&w=1200&q=80",
            "https://images.unsplash.com/photo-1493976040374-85c8e12f0c0e?auto=format&fit=crop&w=1200&q=80",
        ],
        budgetBreakdown=BudgetBreakdown(
            flights=650.0,
            accommodation=450.0,
            foodAndDining=250.0,
            activitiesAndLocalTransit=150.0,
            totalEstimated=1500.0,
            currency="USD",
        ),
        flightOptions=[
            FlightOption(
                airline="All Nippon Airways (ANA)",
                route="COK -> HND",
                estimatedPrice=650.0,
                duration="10h 30m",
                stops="1 stop",
                bookingSearchUrl="https://www.google.com/travel/flights?q=flights+from+COK+to+HND",
                tip="Book mid-week departures for cheaper fares.",
            )
        ],
        hotelRecommendations=[
            HotelRecommendation(
                name="Shinjuku Granbell Hotel",
                neighborhood="Shinjuku",
                pricePerNight=150.0,
                rating="4.4/5",
                whyItFits="Walkable to transit and dining.",
                bookingSearchUrl="https://www.google.com/travel/hotels?q=hotels+in+Shinjuku",
            )
        ],
        days=days_list,
    )


class HealthCheckTests(APITestCase):
    def test_health_check_endpoint(self):
        url = reverse('api-health')
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data["success"])
        self.assertEqual(response.data["data"]["status"], "ok")
        self.assertEqual(response.data["data"]["database"], "connected")


class AIProviderOrchestrationTests(APITestCase):
    """Unit tests for Groq primary, Gemini fallback, and day count completeness validation."""

    @patch('trips.services._generate_with_groq')
    def test_orchestrator_prefers_groq_when_configured(self, mock_groq):
        mock_groq.return_value = get_mock_itinerary_schema(3)
        with self.settings(AI_PROVIDER='groq'):
            result = services.generate_trip_itinerary("test prompt", expected_days=3)
            self.assertEqual(result.tripTitle, "Tokyo Exploration: Neon & Tradition")
            self.assertEqual(len(result.days), 3)
            mock_groq.assert_called_once_with("test prompt")

    @patch('trips.services._generate_with_gemini')
    @patch('trips.services._generate_with_groq')
    def test_orchestrator_falls_back_to_gemini_when_groq_fails(self, mock_groq, mock_gemini):
        mock_groq.side_effect = Exception("Groq model error")
        mock_gemini.return_value = get_mock_itinerary_schema(3)

        with self.settings(AI_PROVIDER='groq'):
            result = services.generate_trip_itinerary("test prompt", expected_days=3)
            self.assertEqual(result.tripTitle, "Tokyo Exploration: Neon & Tradition")
            mock_groq.assert_called_once()
            mock_gemini.assert_called_once_with("test prompt")

    @patch('trips.services._generate_with_gemini')
    @patch('trips.services._generate_with_groq')
    def test_orchestrator_raises_ai_service_error_when_both_fail(self, mock_groq, mock_gemini):
        mock_groq.side_effect = Exception("Groq down")
        mock_gemini.side_effect = Exception("Gemini down")

        with self.settings(AI_PROVIDER='groq'):
            with self.assertRaises(AIServiceError) as ctx:
                services.generate_trip_itinerary("test prompt")
            self.assertIn("AI travel concierge service unavailable", str(ctx.exception))

    @patch('trips.services._generate_with_gemini')
    @patch('trips.services._generate_with_groq')
    def test_orchestrator_falls_back_to_gemini_when_groq_returns_incomplete_days(self, mock_groq, mock_gemini):
        # Primary Groq returns truncated 7 days on both initial and retry
        mock_groq.return_value = get_mock_itinerary_schema(7)
        # Secondary Gemini returns full 10 days
        mock_gemini.return_value = get_mock_itinerary_schema(10)

        with self.settings(AI_PROVIDER='groq'):
            result = services.generate_trip_itinerary("prompt for 10 days", expected_days=10)
            self.assertEqual(result.tripTitle, "Tokyo Exploration: Neon & Tradition")
            self.assertEqual(len(result.days), 10)
            # Groq attempted twice (initial + 1 retry) before fallback
            self.assertEqual(mock_groq.call_count, 2)
            # Gemini called as fallback and succeeded
            mock_gemini.assert_called_once()

    @patch('trips.services._dispatch_ai_generation')
    def test_day_count_validation_triggers_automatic_retry(self, mock_dispatch):
        # 1st call returns truncated 1 day; 2nd call (retry) returns all 3 days
        mock_dispatch.side_effect = [
            get_mock_itinerary_schema(1),
            get_mock_itinerary_schema(3),
        ]

        result = services.generate_trip_itinerary("prompt for 3 days", expected_days=3)
        self.assertEqual(len(result.days), 3)
        self.assertEqual(mock_dispatch.call_count, 2)

    @patch('trips.services._dispatch_ai_generation')
    def test_day_count_validation_fails_after_retry(self, mock_dispatch):
        # Both calls return only 1 day instead of expected 3
        mock_dispatch.side_effect = [
            get_mock_itinerary_schema(1),
            get_mock_itinerary_schema(1),
        ]

        with self.assertRaises(AIServiceError) as ctx:
            services.generate_trip_itinerary("prompt for 3 days", expected_days=3)
        self.assertIn("completeness validation", str(ctx.exception))

    def test_validate_itinerary_structure_rules(self):
        valid = get_mock_itinerary_schema(3)
        # Should pass without raising
        services.validate_itinerary_structure(valid, expected_days=3)

        # Mismatched day count
        with self.assertRaises(ValueError):
            services.validate_itinerary_structure(valid, expected_days=4)

        # Fewer than 2 activities
        invalid_act = get_mock_itinerary_schema(2)
        invalid_act.days[0].activities = invalid_act.days[0].activities[:1]
        with self.assertRaises(ValueError):
            services.validate_itinerary_structure(invalid_act, expected_days=2)

        # Missing restaurant pick
        invalid_rest = get_mock_itinerary_schema(2)
        invalid_rest.days[0].restaurantPicks = []
        with self.assertRaises(ValueError):
            services.validate_itinerary_structure(invalid_rest, expected_days=2)

    @patch('groq.resources.chat.completions.Completions.create')
    def test_generate_with_groq_direct_call(self, mock_create):
        mock_schema_json = get_mock_itinerary_schema(3).model_dump_json()
        mock_choice = MagicMock()
        mock_choice.message.content = mock_schema_json
        mock_response = MagicMock()
        mock_response.choices = [mock_choice]
        mock_create.return_value = mock_response

        with self.settings(GROQ_API_KEY='fake-test-key', GROQ_MODEL='llama-3.3-70b-versatile'):
            result = services._generate_with_groq("test prompt")
            self.assertEqual(result.tripTitle, "Tokyo Exploration: Neon & Tradition")
            self.assertEqual(len(result.days), 3)

    def test_hero_images_deduplication(self):
        duplicate_urls = [
            "https://images.unsplash.com/photo-1",
            "https://images.unsplash.com/photo-2",
            "https://images.unsplash.com/photo-1",
            "https://images.unsplash.com/photo-3",
            "https://images.unsplash.com/photo-2",
        ]
        schema = get_mock_itinerary_schema(3)
        schema.heroImages = duplicate_urls
        processed = services.post_process_itinerary(schema)
        self.assertEqual(
            processed.heroImages,
            [
                "https://images.unsplash.com/photo-1",
                "https://images.unsplash.com/photo-2",
                "https://images.unsplash.com/photo-3",
            ],
        )

    def test_build_prompt_full_flight_routing_rules(self):
        prompt = services.build_prompt(
            origin="Kannur (CNN)",
            destination="Paris (CDG)",
            days=5,
            members=2,
            budget=250000.0,
            currency="INR",
            travel_style="Balanced",
            extra_notes="Vegetarian dining",
        )
        self.assertIn("Kannur (CNN)", prompt)
        self.assertIn("Paris (CDG)", prompt)
        self.assertIn("Complete Origin-to-Destination Flight Options", prompt)
        self.assertIn("ABSOLUTE ROUTE MANDATE", prompt)
        self.assertIn("Multi-Leg & 2-Ticket Connection Support", prompt)
        self.assertIn("flights+from+Kannur+(CNN)+to+Paris+(CDG)", prompt)
        self.assertIn("3 to 5 distinct, high-resolution landscape photo URLs", prompt)

    def test_post_process_itinerary_normalizes_flight_booking_url(self):
        schema = get_mock_itinerary_schema(3)
        schema.flightOptions[0].bookingSearchUrl = ""
        processed = services.post_process_itinerary(schema, origin="Kannur (CNN)", destination="Paris (CDG)")
        self.assertIn("flights+from+Kannur+(CNN)+to+Paris+(CDG)", processed.flightOptions[0].bookingSearchUrl)


class TripGenerationTests(APITestCase):
    def setUp(self):
        self.generate_url = reverse('trip-generate')
        self.user = User.objects.create_user(
            username="traveler1",
            email="traveler1@example.com",
            password="Password123!"
        )

    def test_generate_trip_missing_required_fields(self):
        payload = {
            "origin": "Kochi",
            # missing destination and days
        }
        response = self.client.post(self.generate_url, payload, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertFalse(response.data["success"])
        self.assertEqual(response.data["error"]["code"], "VALIDATION_ERROR")

    def test_generate_trip_invalid_days_range(self):
        payload = {
            "origin": "Kochi",
            "destination": "Tokyo",
            "days": 0,  # min is 1
        }
        response = self.client.post(self.generate_url, payload, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data["error"]["code"], "VALIDATION_ERROR")

    @patch('trips.services.generate_trip_itinerary')
    def test_generate_trip_guest_success(self, mock_itinerary):
        mock_itinerary.return_value = get_mock_itinerary_schema(3)

        payload = {
            "origin": "Kochi",
            "destination": "Tokyo",
            "days": 3,
            "members": 2,
            "budget": 1500,
            "currency": "USD",
            "travelStyle": "Budget & Cultural",
            "extraNotes": "Love ramen and scenic viewpoints",
        }
        response = self.client.post(self.generate_url, payload, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertTrue(response.data["success"])
        data = response.data["data"]
        self.assertEqual(data["origin"], "Kochi")
        self.assertEqual(data["destination"], "Tokyo")
        self.assertEqual(data["days"], 3)
        self.assertIn("itinerary", data)
        self.assertEqual(data["itinerary"]["tripTitle"], "Tokyo Exploration: Neon & Tradition")
        self.assertIn("heroImages", data["itinerary"])
        self.assertEqual(len(data["itinerary"]["heroImages"]), 5)
        self.assertIn("imageUrl", data["itinerary"]["days"][0]["activities"][0])
        self.assertIn("imageUrl", data["itinerary"]["days"][0]["restaurantPicks"][0])

        # Verify DB persistence
        trip = TripPlan.objects.get(id=data["id"])
        self.assertIsNone(trip.user)
        self.assertEqual(trip.travel_style, "Budget & Cultural")

    @patch('trips.services.generate_trip_itinerary')
    def test_generate_trip_authenticated_user_success(self, mock_itinerary):
        mock_itinerary.return_value = get_mock_itinerary_schema(4)
        self.client.force_authenticate(user=self.user)

        payload = {
            "origin": "Paris",
            "destination": "Rome",
            "days": 4,
            "members": 1,
            "budget": 1000,
            "currency": "EUR",
            "travel_style": "Historical",
            "extra_notes": "Visit the Colosseum",
        }
        response = self.client.post(self.generate_url, payload, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertTrue(response.data["success"])

        trip = TripPlan.objects.get(id=response.data["data"]["id"])
        self.assertEqual(trip.user, self.user)
        self.assertEqual(trip.origin, "Paris")

    @patch('trips.services.generate_trip_itinerary')
    def test_generate_trip_ai_service_error_handling(self, mock_itinerary):
        mock_itinerary.side_effect = AIServiceError("All AI providers unavailable.")

        payload = {
            "origin": "London",
            "destination": "Dublin",
            "days": 2,
        }
        response = self.client.post(self.generate_url, payload, format='json')
        self.assertEqual(response.status_code, status.HTTP_502_BAD_GATEWAY)
        self.assertFalse(response.data["success"])
        self.assertEqual(response.data["error"]["code"], "AI_SERVICE_ERROR")


class TripHistoryAndDetailTests(APITestCase):
    def setUp(self):
        self.user1 = User.objects.create_user(username="user1", email="user1@example.com", password="Password123!")
        self.user2 = User.objects.create_user(username="user2", email="user2@example.com", password="Password123!")

        mock_schema = get_mock_itinerary_schema(5).model_dump()

        self.trip1 = TripPlan.objects.create(
            user=self.user1,
            origin="New York",
            destination="London",
            days=5,
            members=2,
            budget=2000,
            currency="USD",
            travel_style="Luxury",
            itinerary_json=mock_schema,
        )

        self.trip2 = TripPlan.objects.create(
            user=self.user2,
            origin="Berlin",
            destination="Prague",
            days=3,
            members=1,
            budget=500,
            currency="EUR",
            travel_style="Budget",
            itinerary_json=mock_schema,
        )

        self.guest_trip = TripPlan.objects.create(
            user=None,
            origin="Madrid",
            destination="Barcelona",
            days=2,
            members=1,
            budget=400,
            currency="EUR",
            itinerary_json=mock_schema,
        )

    def test_list_trips_unauthenticated(self):
        url = reverse('trip-list')
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertEqual(response.data["error"]["code"], "NOT_AUTHENTICATED")

    def test_list_trips_authenticated_only_shows_own_trips(self):
        url = reverse('trip-list')
        self.client.force_authenticate(user=self.user1)

        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data["success"])
        trips = response.data["data"]
        self.assertEqual(len(trips), 1)
        self.assertEqual(trips[0]["id"], self.trip1.id)
        self.assertEqual(trips[0]["origin"], "New York")

    def test_get_trip_detail_guest_trip(self):
        url = reverse('trip-detail', kwargs={'pk': self.guest_trip.id})
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data["success"])
        self.assertEqual(response.data["data"]["id"], self.guest_trip.id)
        self.assertIn("itinerary", response.data["data"])

    def test_get_trip_detail_own_trip(self):
        self.client.force_authenticate(user=self.user1)
        url = reverse('trip-detail', kwargs={'pk': self.trip1.id})
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["data"]["id"], self.trip1.id)

    def test_get_trip_detail_forbidden_for_other_user(self):
        self.client.force_authenticate(user=self.user1)
        # Attempt to access user2's trip
        url = reverse('trip-detail', kwargs={'pk': self.trip2.id})
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(response.data["error"]["code"], "PERMISSION_DENIED")

    def test_get_trip_detail_not_found(self):
        url = reverse('trip-detail', kwargs={'pk': 99999})
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(response.data["error"]["code"], "TRIP_NOT_FOUND")


class TripEmailRoadmapTests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="sender", email="sender@example.com", password="Password123!")
        mock_schema = get_mock_itinerary_schema(3).model_dump()
        self.trip = TripPlan.objects.create(
            user=self.user,
            origin="Kochi",
            destination="Tokyo",
            days=3,
            members=2,
            budget=1500,
            currency="USD",
            travel_style="Balanced",
            itinerary_json=mock_schema,
        )
        self.guest_trip = TripPlan.objects.create(
            user=None,
            origin="San Francisco",
            destination="Seattle",
            days=2,
            members=1,
            budget=600,
            currency="USD",
            itinerary_json=mock_schema,
        )

    def test_email_roadmap_authenticated_default_to_user_email(self):
        self.client.force_authenticate(user=self.user)
        url = reverse('trip-email-roadmap', kwargs={'pk': self.trip.id})

        response = self.client.post(url, {}, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data["success"])
        self.assertEqual(response.data["data"]["recipient_email"], "sender@example.com")

        self.assertEqual(len(mail.outbox), 1)
        sent = mail.outbox[0]
        self.assertEqual(sent.to, ["sender@example.com"])
        self.assertIn("Your Waypoint Travel Roadmap: Kochi to Tokyo", sent.subject)
        self.assertIn("FLIGHT OPTIONS", sent.body)
        self.assertIn("HOTEL RECOMMENDATIONS", sent.body)
        self.assertIn("DAY-BY-DAY ROADMAP", sent.body)
        self.assertIn("https://www.google.com/travel/flights", sent.body)

    def test_email_roadmap_guest_trip_with_explicit_email(self):
        url = reverse('trip-email-roadmap', kwargs={'pk': self.guest_trip.id})
        response = self.client.post(url, {"email": "guest@example.com"}, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["data"]["recipient_email"], "guest@example.com")
        self.assertEqual(len(mail.outbox), 1)

    def test_email_roadmap_guest_trip_missing_email(self):
        url = reverse('trip-email-roadmap', kwargs={'pk': self.guest_trip.id})
        response = self.client.post(url, {}, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data["error"]["code"], "VALIDATION_ERROR")

    def test_email_roadmap_not_found(self):
        url = reverse('trip-email-roadmap', kwargs={'pk': 99999})
        response = self.client.post(url, {"email": "test@example.com"}, format='json')
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(response.data["error"]["code"], "TRIP_NOT_FOUND")
