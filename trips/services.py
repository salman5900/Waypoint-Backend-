import json
import logging
from typing import Dict, Any, Optional

from django.conf import settings
from django.core.mail import send_mail
from groq import Groq
from google import genai
from google.genai import types

from core.exceptions import AIServiceError, TripNotFoundError
from .models import TripPlan
from .schemas import TripItinerarySchema
from .selectors import get_trip_by_id

logger = logging.getLogger(__name__)


def clean_json_text(raw_text: str) -> str:
    """Strips markdown code fences and returns pure JSON string."""
    text = raw_text.strip()
    if text.startswith("```"):
        lines = text.splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].startswith("```"):
            lines = lines[:-1]
        text = "\n".join(lines).strip()
    return text


def build_system_instruction() -> str:
    return (
        "You are Waypoint's Principal AI Travel Concierge. "
        "Your mission is to craft ultra-actionable, search-grounded, day-by-day travel roadmaps "
        "tailored for travelers who manual-book their own trips.\n\n"
        "ACCURACY & CURRENCY MANDATES:\n"
        "1. Active Airlines Only: Only recommend currently operating airlines with real active routes "
        "(e.g., Air India, IndiGo, Japan Airlines (JAL), All Nippon Airways (ANA), Singapore Airlines, Emirates, "
        "Qatar Airways, AirAsia). NEVER recommend defunct, rebranded, or merged carriers (such as Vistara).\n"
        "2. Real Dining & Dietary Verifiability: Recommend only real, verifiable, currently operating restaurants, "
        "izakayas, and cafes. Pay strict attention to traveler dietary notes (e.g., for vegetarian/vegan ramen in Tokyo, "
        "recommend renowned verifiable spots like T's TanTan, Afuri, or Kyushu Jangara; for Dubai, authentic spots like Al Mallah, Ravi Restaurant, or Zuma).\n"
        "3. Rich Daily Dining: Provide 2 to 3 distinct restaurant picks per day (e.g. lunch, dinner, cafe/sweet treat).\n"
        "4. Real Accommodations: Recommend real, verified hotels matching the budget and travel style.\n"
        "5. Valid Booking Search URLs:\n"
        "   - Flights: Direct Google Flights search links (https://www.google.com/travel/flights?q=flights+from+{origin}+to+{destination}) or Skyscanner.\n"
        "   - Hotels: Direct Google Hotels search links (https://www.google.com/travel/hotels?q=hotels+in+{destination}) or Booking.com.\n"
        "   - Activities & Dining: Direct Google Maps search URLs (https://www.google.com/maps/search/?api=1&query={query}).\n"
        "6. High-Resolution Visual Photography URLs:\n"
        "   - 'heroImages': MUST provide an array of exactly 5 distinct, high-resolution landscape photo URLs matching the destination city and its most iconic landmarks (e.g. for Dubai: Burj Khalifa, Dubai Marina, Desert Safari, Palm Jumeirah, Dubai Creek; for Paris: Eiffel Tower, Louvre, Seine, Montmartre, Arc de Triomphe). NEVER provide images of a different city.\n"
        "   - Every 'ActivityItem': MUST include 'imageUrl' with a high-resolution landscape photo URL matching that specific stop/landmark (e.g. Burj Khalifa, Dubai Mall, Meiji Shrine).\n"
        "   - Every 'RestaurantPick': MUST include 'imageUrl' with a high-resolution photo URL matching the restaurant's cuisine, signature dish, or dining ambiance (e.g. Lebanese grill for Al Mallah, biryani for Ravi, black cod/sushi for Zuma).\n"
        "   - Use valid, high-resolution Unsplash URLs (e.g., https://images.unsplash.com/photo-... with appropriate photo IDs or parameters) or Wikimedia Commons URLs.\n"
        "7. Complete Multi-Day Coverage & Concise Descriptions: Never truncate, summarize, or omit later days. "
        "The 'days' array in your output MUST contain complete, unabbreviated plans for every single requested day (Day 1 through Day N). "
        "To ensure all days fit within the token budget without cutting off, keep each activity description concise (1-2 crisp, vivid sentences). "
        "Provide at least 2 activities and 2 to 3 restaurant picks per day."
    )


def build_prompt(
    origin: str,
    destination: str,
    days: int,
    members: int,
    budget: Optional[float],
    currency: str,
    travel_style: str,
    extra_notes: str,
) -> str:
    budget_str = f"{budget} {currency}" if budget else f"Flexible budget ({currency})"
    style_str = travel_style or "Balanced (culture, leisure, food)"
    notes_str = extra_notes or "None"

    return f"""
Plan a detailed, realistic travel roadmap for:
- Origin: {origin}
- Destination: {destination}
- Duration: {days} days
- Group Size: {members} traveler(s)
- Total Estimated Budget: {budget_str}
- Preferred Currency: {currency}
- Travel Style: {style_str}
- Traveler Notes / Special Requests: {notes_str}

Requirements:
1. Search and provide 2-3 realistic flight options with routes, airlines, duration, and direct booking links.
   Only include currently operating airlines (e.g., Air India, IndiGo, JAL, ANA, Singapore Airlines, Emirates, AirAsia; never defunct or merged carriers like Vistara).
2. Search and recommend 2-3 verified hotels matching nightly budget, neighborhood, and ratings with direct Google Hotels booking links.
3. Destination Hero Photography:
   Provide 'heroImages' containing exactly 5 distinct, high-resolution landscape photo URLs showcasing {destination} and its top iconic sights (never use photos of other cities).
4. Construct a full, realistic day-by-day itinerary:
   CRITICAL: The 'days' array MUST contain exactly {days} complete objects numbered Day 1 through Day {days}. Never truncate, summarize, or omit later days.
   Keep each activity description concise (strictly 1-2 crisp sentences) so the entire {days}-day roadmap fits comfortably within token limits without truncation.
   Each day object MUST contain:
   - At least 2 distinct activities, each with a concise description (1-2 crisp sentences) and an accurate 'imageUrl' matching that specific stop or landmark.
   - 2 to 3 authentic restaurant picks per day matching any dietary requirements in Traveler Notes, each with an accurate 'imageUrl' matching the cuisine, signature dish, or dining ambiance.
5. Calculate an itemized budget breakdown in {currency} covering flights, accommodation, food, activities, and total.
"""


def validate_itinerary_structure(itinerary: TripItinerarySchema, expected_days: Optional[int] = None) -> None:
    """
    Validates that the generated itinerary contains the exact expected day count
    and that each day meets the minimum required completeness:
    - Exactly expected_days day objects.
    - At least 2 activities per day.
    - At least 1 restaurant pick per day.
    """
    if expected_days is not None:
        if len(itinerary.days) != expected_days:
            raise ValueError(
                f"Expected exactly {expected_days} day(s), but received {len(itinerary.days)} day(s)."
            )
        for d in itinerary.days:
            if len(d.activities) < 2:
                raise ValueError(
                    f"Day {d.day} has only {len(d.activities)} activity/activities; minimum 2 required."
                )
            if len(d.restaurantPicks) < 1:
                raise ValueError(
                    f"Day {d.day} has no restaurant picks; minimum 1 required."
                )


def _generate_with_groq(prompt: str) -> TripItinerarySchema:
    """
    Primary AI generation provider using Groq LPU inference.
    Enforces pure structured JSON according to TripItinerarySchema.model_json_schema().
    Includes max_tokens=8192 and temperature=0.4 to prevent early multi-day truncation.
    """
    api_key = getattr(settings, 'GROQ_API_KEY', '').strip()
    if not api_key:
        raise AIServiceError("GROQ_API_KEY is not configured in environment settings.")

    client = Groq(api_key=api_key)
    schema_dict = TripItinerarySchema.model_json_schema()
    schema_json = json.dumps(schema_dict, indent=2)

    groq_system_instruction = (
        f"{build_system_instruction()}\n\n"
        "CRITICAL JSON FORMATTING REQUIREMENT:\n"
        "You must return ONLY a single JSON object strictly matching this schema definition:\n"
        f"{schema_json}\n\n"
        "Ensure every single key is present: 'tripTitle', 'summary', 'heroImages', 'budgetBreakdown', "
        "'flightOptions', 'hotelRecommendations', 'days'.\n"
        "'heroImages' must be an array of exactly 5 high-resolution landscape photo URLs matching the destination.\n"
        "Each activity in 'days' must include an 'imageUrl' for that landmark/attraction.\n"
        "Each restaurant in 'days' must include an 'imageUrl' for that cuisine/dish, with 2-3 restaurant picks per day.\n"
        "All booking search URLs for flights must be direct Google Flights or Skyscanner search links.\n"
        "All hotel booking search URLs must be direct Google Hotels or Booking.com search links.\n"
        "All activity and restaurant URLs must be direct Google Maps search links.\n"
        "Do NOT wrap output in markdown code blocks. Output raw valid JSON only."
    )

    primary_model = getattr(settings, 'GROQ_MODEL', 'llama-3.3-70b-versatile').strip() or 'llama-3.3-70b-versatile'
    candidate_models = [primary_model]
    for fallback in ['openai/gpt-oss-120b', 'openai/gpt-oss-20b', 'qwen/qwen3.8-27b']:
        if fallback not in candidate_models:
            candidate_models.append(fallback)

    last_error = None
    for model_name in candidate_models:
        try:
            logger.info("Attempting Groq itinerary generation with model '%s' (max_tokens=8192, temp=0.4)...", model_name)
            response = client.chat.completions.create(
                model=model_name,
                messages=[
                    {"role": "system", "content": groq_system_instruction},
                    {"role": "user", "content": prompt},
                ],
                response_format={"type": "json_object"},
                temperature=0.4,
                max_tokens=8192,
            )
            raw_text = clean_json_text(response.choices[0].message.content)
            return TripItinerarySchema.model_validate_json(raw_text)

        except Exception as err:
            logger.warning("Groq generation with model '%s' encountered: %s", model_name, err)
            last_error = err
            continue

    error_msg = f"Failed to generate travel itinerary with Groq: {last_error}"
    logger.error(error_msg)
    raise AIServiceError(error_msg)


def _generate_with_gemini(prompt: str) -> TripItinerarySchema:
    """
    Secondary AI generation provider using Google Gemini GenAI SDK.
    Supports Search Grounding and structured output validation with fallback models.
    """
    api_key = getattr(settings, 'GEMINI_API_KEY', '').strip()
    if not api_key:
        raise AIServiceError("GEMINI_API_KEY is not configured in environment settings.")

    client = genai.Client(api_key=api_key)
    system_instruction = build_system_instruction()

    configured_model = getattr(settings, 'GEMINI_MODEL', 'gemini-3.8-flash').strip() or 'gemini-3.8-flash'
    candidate_models = [configured_model]
    for fallback in ['gemini-3.8-flash', 'gemini-3.5-flash', 'gemini-3.7-flash', 'gemini-3.5-flash-lite']:
        if fallback not in candidate_models:
            candidate_models.append(fallback)

    last_error = None

    for model_name in candidate_models:
        # Strategy A: Google Search Grounding + Structured Schema
        try:
            logger.info("Attempting Gemini generation with model '%s' and search grounding...", model_name)
            config = types.GenerateContentConfig(
                system_instruction=system_instruction,
                tools=[types.Tool(google_search=types.GoogleSearch())],
                response_mime_type="application/json",
                response_schema=TripItinerarySchema,
                temperature=0.4,
            )
            response = client.models.generate_content(
                model=model_name,
                contents=prompt,
                config=config,
            )
            raw_text = clean_json_text(response.text)
            return TripItinerarySchema.model_validate_json(raw_text)

        except Exception as err:
            err_str = str(err)
            if "429" in err_str or "RESOURCE_EXHAUSTED" in err_str:
                logger.error("Gemini API quota exhausted: %s", err)
                raise AIServiceError("Gemini API rate limit or quota exceeded. Please check your Gemini API plan or try again shortly.")

            logger.warning("Strategy A with model '%s' encountered: %s", model_name, err)
            last_error = err

            # Strategy B: Structured Schema without Search Grounding
            try:
                logger.info("Attempting Gemini generation with model '%s' and structured schema...", model_name)
                config_b = types.GenerateContentConfig(
                    system_instruction=system_instruction,
                    response_mime_type="application/json",
                    response_schema=TripItinerarySchema,
                    temperature=0.4,
                )
                response = client.models.generate_content(
                    model=model_name,
                    contents=prompt,
                    config=config_b,
                )
                raw_text = clean_json_text(response.text)
                return TripItinerarySchema.model_validate_json(raw_text)
            except Exception as err_b:
                err_b_str = str(err_b)
                if "429" in err_b_str or "RESOURCE_EXHAUSTED" in err_b_str:
                    logger.error("Gemini API quota exhausted: %s", err_b)
                    raise AIServiceError("Gemini API rate limit or quota exceeded. Please check your Gemini API plan or try again shortly.")
                logger.warning("Strategy B with model '%s' encountered: %s", model_name, err_b)
                last_error = err_b
                continue

    error_msg = f"Failed to generate travel itinerary from Gemini AI concierge: {last_error}"
    logger.error(error_msg)
    raise AIServiceError(error_msg)


def _generate_with_provider(
    provider_name: str,
    prompt: str,
    expected_days: Optional[int] = None,
) -> TripItinerarySchema:
    """
    Executes itinerary generation for a single provider ('groq' or 'gemini').
    If expected_days is specified and completeness validation fails (e.g. day count mismatch),
    automatically retries once with an explicit correction prompt before raising ValueError.
    """
    gen_func = _generate_with_groq if provider_name == 'groq' else _generate_with_gemini
    itinerary = gen_func(prompt)
    if expected_days is not None:
        try:
            validate_itinerary_structure(itinerary, expected_days)
        except ValueError as val_err:
            logger.warning(
                "%s itinerary completeness validation failed on initial attempt: %s. Retrying once...",
                provider_name.capitalize(),
                val_err,
            )
            retry_prompt = (
                prompt +
                f"\n\nCRITICAL CORRECTION REQUIRED:\n"
                f"Your previous output failed completeness validation: {val_err}\n"
                f"You MUST generate exactly {expected_days} complete day objects in the 'days' array (numbered Day 1 to Day {expected_days}). "
                f"Keep each activity description strictly to 1-2 concise sentences so the full multi-day plan does not exceed token limits. "
                f"Every single day must contain at least 2 distinct activities and at least 1 authentic restaurant pick. "
                f"Do NOT truncate, compress, or omit any day."
            )
            itinerary = gen_func(retry_prompt)
            validate_itinerary_structure(itinerary, expected_days)
    return itinerary


def _dispatch_ai_generation(prompt: str, expected_days: Optional[int] = None) -> TripItinerarySchema:
    """
    Dispatches generation to configured primary provider with automatic single-retry on day count mismatch.
    If the primary provider fails (via exception or incomplete day count after retry), falls back
    to the secondary provider (which also gets a single retry) before raising AIServiceError.
    """
    primary_provider = getattr(settings, 'AI_PROVIDER', 'groq').strip().lower()
    secondary_provider = 'gemini' if primary_provider == 'groq' else 'groq'

    primary_error = None
    try:
        return _generate_with_provider(primary_provider, prompt, expected_days=expected_days)
    except Exception as prim_err:
        primary_error = prim_err
        logger.warning(
            "Primary %s provider failed: %s. Initiating %s fallback...",
            primary_provider,
            prim_err,
            secondary_provider,
        )

    try:
        return _generate_with_provider(secondary_provider, prompt, expected_days=expected_days)
    except Exception as sec_err:
        logger.error(
            "Both %s and %s providers failed. %s: %s | %s: %s",
            primary_provider,
            secondary_provider,
            primary_provider,
            primary_error,
            secondary_provider,
            sec_err,
        )
        raise AIServiceError(
            f"AI travel concierge service unavailable. Primary ({primary_provider}) error: {primary_error}; "
            f"Secondary ({secondary_provider}) error: {sec_err}"
        )


def generate_trip_itinerary(prompt: str, expected_days: Optional[int] = None) -> TripItinerarySchema:
    """
    Main AI Orchestrator:
    Dispatches generation to AI providers and enforces day count and activity/restaurant completeness.
    If the primary provider returns fewer days than requested or fails, retries once, then falls back
    to the secondary provider before raising AIServiceError.
    """
    try:
        itinerary = _dispatch_ai_generation(prompt, expected_days=expected_days)
        if expected_days is not None:
            validate_itinerary_structure(itinerary, expected_days)
        return itinerary
    except ValueError as val_err:
        logger.warning("Itinerary completeness validation failed: %s. Retrying generation once...", val_err)
        retry_prompt = (
            prompt +
            f"\n\nCRITICAL CORRECTION REQUIRED:\n"
            f"Your previous output failed completeness validation: {val_err}\n"
            f"You MUST generate exactly {expected_days} complete day objects in the 'days' array (numbered Day 1 to Day {expected_days}). "
            f"Keep each activity description strictly to 1-2 crisp sentences. "
            f"Every single day must contain at least 2 distinct activities and at least 1 authentic restaurant pick. "
            f"Do NOT truncate, compress, or omit any day."
        )
        try:
            itinerary = _dispatch_ai_generation(retry_prompt, expected_days=expected_days)
            if expected_days is not None:
                validate_itinerary_structure(itinerary, expected_days)
            return itinerary
        except Exception as retry_err:
            logger.error("Retry generation failed completeness validation: %s", retry_err)
            raise AIServiceError(f"Itinerary generation failed day count / completeness validation: {retry_err}")
    except AIServiceError:
        raise
    except Exception as exc:
        logger.error("Unexpected error during itinerary generation: %s", exc)
        raise AIServiceError(f"AI travel concierge service encountered an error: {exc}")


# Maintain backward compatibility alias
call_gemini_api = generate_trip_itinerary


def generate_trip_plan(
    origin: str,
    destination: str,
    days: int,
    members: int = 1,
    budget: Optional[float] = None,
    currency: str = "USD",
    travel_style: str = "",
    extra_notes: str = "",
    user: Optional[Any] = None,
) -> TripPlan:
    """
    Coordinates AI itinerary generation, schema validation, and persistence into PostgreSQL.
    """
    prompt = build_prompt(
        origin=origin,
        destination=destination,
        days=days,
        members=members,
        budget=budget,
        currency=currency,
        travel_style=travel_style,
        extra_notes=extra_notes,
    )

    itinerary_schema = generate_trip_itinerary(prompt, expected_days=days)
    itinerary_dict = itinerary_schema.model_dump()

    trip_plan = TripPlan.objects.create(
        user=user if (user and user.is_authenticated) else None,
        origin=origin.strip(),
        destination=destination.strip(),
        days=days,
        members=members,
        budget=budget,
        currency=currency.strip().upper(),
        travel_style=travel_style.strip(),
        extra_notes=extra_notes.strip(),
        itinerary_json=itinerary_dict,
    )

    return trip_plan


def format_trip_email_content(trip: TripPlan) -> str:
    """Formats a clean, human-readable plain-text summary of the trip itinerary and booking links."""
    itinerary = trip.itinerary_json
    lines = []
    lines.append("=" * 60)
    lines.append(f"WAYPOINT TRAVEL ROADMAP: {itinerary.get('tripTitle', f'{trip.origin} to {trip.destination}')}")
    lines.append("=" * 60)
    lines.append(f"Origin: {trip.origin}")
    lines.append(f"Destination: {trip.destination}")
    lines.append(f"Duration: {trip.days} Days | Travelers: {trip.members}")
    if trip.travel_style:
        lines.append(f"Style: {trip.travel_style}")
    lines.append("")
    lines.append(f"Summary: {itinerary.get('summary', '')}")
    lines.append("")

    # Budget Breakdown
    budget = itinerary.get('budgetBreakdown', {})
    curr = budget.get('currency', trip.currency)
    lines.append("-" * 40)
    lines.append(f"ESTIMATED BUDGET BREAKDOWN ({curr})")
    lines.append("-" * 40)
    lines.append(f"  • Flights: {curr} {budget.get('flights', 0):,.2f}")
    lines.append(f"  • Accommodation: {curr} {budget.get('accommodation', 0):,.2f}")
    lines.append(f"  • Food & Dining: {curr} {budget.get('foodAndDining', 0):,.2f}")
    lines.append(f"  • Activities & Transit: {curr} {budget.get('activitiesAndLocalTransit', 0):,.2f}")
    lines.append(f"  TOTAL ESTIMATED: {curr} {budget.get('totalEstimated', 0):,.2f}")
    lines.append("")

    # Flights
    flight_options = itinerary.get('flightOptions', [])
    if flight_options:
        lines.append("-" * 40)
        lines.append("FLIGHT OPTIONS (MANUAL BOOKING LINKS)")
        lines.append("-" * 40)
        for i, f in enumerate(flight_options, 1):
            lines.append(f"[{i}] {f.get('airline', 'Flight')} - {f.get('route', '')}")
            lines.append(f"    Est. Price: {curr} {f.get('estimatedPrice', 0):,.2f} | Duration: {f.get('duration', '')} | Stops: {f.get('stops', '')}")
            lines.append(f"    Booking Link: {f.get('bookingSearchUrl', '')}")
            if f.get('tip'):
                lines.append(f"    Tip: {f.get('tip')}")
            lines.append("")

    # Hotels
    hotel_options = itinerary.get('hotelRecommendations', [])
    if hotel_options:
        lines.append("-" * 40)
        lines.append("HOTEL RECOMMENDATIONS (MANUAL BOOKING LINKS)")
        lines.append("-" * 40)
        for i, h in enumerate(hotel_options, 1):
            lines.append(f"[{i}] {h.get('name', 'Hotel')} ({h.get('neighborhood', '')})")
            lines.append(f"    Nightly Rate: {curr} {h.get('pricePerNight', 0):,.2f} | Rating: {h.get('rating', '')}")
            lines.append(f"    Why it fits: {h.get('whyItFits', '')}")
            lines.append(f"    Booking Link: {h.get('bookingSearchUrl', '')}")
            lines.append("")

    # Day-by-Day Itinerary
    days_list = itinerary.get('days', [])
    if days_list:
        lines.append("-" * 40)
        lines.append("DAY-BY-DAY ROADMAP")
        lines.append("-" * 40)
        for d in days_list:
            lines.append(f"\nDAY {d.get('day', 1)}: {d.get('theme', '')}")
            lines.append("  Activities:")
            for a in d.get('activities', []):
                cost_str = f" ({curr} {a.get('estimatedCost', 0):,.2f})" if a.get('estimatedCost') else ""
                lines.append(f"    [{a.get('time', '')}] {a.get('title', '')}{cost_str}")
                lines.append(f"        {a.get('description', '')}")
                if a.get('mapOrBookingUrl'):
                    lines.append(f"        Map/Link: {a.get('mapOrBookingUrl')}")

            restaurants = d.get('restaurantPicks', [])
            if restaurants:
                lines.append("  Dining Picks:")
                for r in restaurants:
                    lines.append(f"    • {r.get('name', '')} ({r.get('cuisine', '')}, {r.get('priceRange', '')})")
                    if r.get('signatureDish'):
                        lines.append(f"      Signature: {r.get('signatureDish')}")
                    if r.get('mapUrl'):
                        lines.append(f"      Map: {r.get('mapUrl')}")

    lines.append("")
    lines.append("=" * 60)
    lines.append("Safe travels! Prepared by Waypoint AI.")
    lines.append("=" * 60)

    return "\n".join(lines)


def send_trip_roadmap_email(trip_id: int, recipient_email: str) -> Dict[str, Any]:
    """
    Retrieves the TripPlan, formats its roadmap, and emails it to the recipient.
    """
    clean_email = recipient_email.strip().lower()
    trip = get_trip_by_id(trip_id)
    if not trip:
        raise TripNotFoundError(f"Trip with ID {trip_id} not found.")

    subject = f"Your Waypoint Travel Roadmap: {trip.origin} to {trip.destination}"
    body = format_trip_email_content(trip)

    send_mail(
        subject=subject,
        message=body,
        from_email=None,
        recipient_list=[clean_email],
        fail_silently=False,
    )

    return {
        "trip_id": trip.id,
        "recipient_email": clean_email,
        "status": "sent",
    }
