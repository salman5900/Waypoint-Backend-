from typing import List
from pydantic import BaseModel, Field, field_validator


class FlightOption(BaseModel):
    airline: str = Field(..., description="Airline name or primary operating carrier")
    route: str = Field(..., description="Departure airport to destination airport code or route")
    estimatedPrice: float = Field(..., description="Estimated cost per traveler in the specified currency")
    duration: str = Field(..., description="Flight duration, e.g. 9h 45m")
    stops: str = Field(..., description="Number of stops, e.g. Nonstop, 1 stop")
    bookingSearchUrl: str = Field(..., description="Direct search link on Google Flights or Skyscanner")
    tip: str = Field(..., description="Actionable booking recommendation or best day to fly")


class HotelRecommendation(BaseModel):
    name: str = Field(..., description="Hotel or property name")
    neighborhood: str = Field(..., description="Neighborhood or area location")
    pricePerNight: float = Field(..., description="Estimated nightly rate in the specified currency")
    rating: str = Field(..., description="Guest rating or star rating, e.g. 4.6/5 or 4-star")
    whyItFits: str = Field(..., description="Why this accommodation matches the traveler's style and budget")
    bookingSearchUrl: str = Field(..., description="Direct search link on Google Hotels or Booking.com")


class ActivityItem(BaseModel):
    time: str = Field(..., description="Time of day or slot, e.g. 09:00 AM or Morning")
    title: str = Field(..., description="Title of the activity or attraction")
    category: str = Field(..., description="Category: sightseeing, transit, experience, or shopping")
    description: str = Field(..., description="Concise description and insider tips")
    estimatedCost: float = Field(..., description="Estimated entry fee or ticket cost per person")
    mapOrBookingUrl: str = Field(..., description="Direct Google Maps or official ticket booking link")
    imageUrl: str = Field(default="", description="High-resolution landscape photo URL matching this specific landmark or activity")


class RestaurantPick(BaseModel):
    name: str = Field(..., description="Restaurant, cafe, or eatery name")
    cuisine: str = Field(..., description="Cuisine type or culinary style")
    priceRange: str = Field(..., description="Price level indicator, e.g. $, $$, $$$")
    signatureDish: str = Field(..., description="Must-try local dish or specialty")
    mapUrl: str = Field(..., description="Google Maps search link for easy navigation")
    imageUrl: str = Field(default="", description="High-resolution photo URL matching the restaurant's cuisine, signature dish, or dining ambiance")


class DayPlan(BaseModel):
    day: int = Field(..., description="Day number (1, 2, 3...)")
    theme: str = Field(..., description="Theme or focus of the day, e.g. Historic Heart & Shrines")
    activities: List[ActivityItem] = Field(default_factory=list, description="Ordered schedule of activities")
    restaurantPicks: List[RestaurantPick] = Field(default_factory=list, description="Recommended dining options for the day (2-3 distinct spots per day)")


class BudgetBreakdown(BaseModel):
    flights: float = Field(..., description="Estimated total cost for flights")
    accommodation: float = Field(..., description="Estimated total cost for lodging")
    foodAndDining: float = Field(..., description="Estimated total cost for meals and drinks")
    activitiesAndLocalTransit: float = Field(..., description="Estimated total cost for activities and local transit")
    totalEstimated: float = Field(..., description="Overall sum of all estimated expenses")
    currency: str = Field(..., description="Currency code, e.g. USD, EUR, INR")


class TripItinerarySchema(BaseModel):
    tripTitle: str = Field(..., description="Catchy descriptive title for the journey")
    summary: str = Field(..., description="High-level overview of the travel itinerary")
    heroImages: List[str] = Field(
        default_factory=list,
        description="3 to 5 distinct, high-resolution landscape photo URLs matching the destination city and iconic landmarks (never repeat identical URLs)"
    )
    budgetBreakdown: BudgetBreakdown = Field(..., description="Itemized budget allocation")
    flightOptions: List[FlightOption] = Field(default_factory=list, description="Curated flight options with direct booking links")
    hotelRecommendations: List[HotelRecommendation] = Field(default_factory=list, description="Curated hotel options with direct booking links")
    days: List[DayPlan] = Field(default_factory=list, description="Day-by-day itinerary roadmap")

    @field_validator('heroImages', mode='after')
    @classmethod
    def deduplicate_hero_images(cls, v: List[str]) -> List[str]:
        seen = set()
        deduped = []
        for url in v:
            clean_url = url.strip() if isinstance(url, str) else ""
            if clean_url and clean_url not in seen:
                seen.add(clean_url)
                deduped.append(clean_url)
        return deduped
