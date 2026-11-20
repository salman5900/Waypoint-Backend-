# Waypoint API Contract & Frontend Integration Guide

> **Base URL:** `http://localhost:8000/api`  
> **CORS Allowed Origins:** `http://localhost:5173`, `http://127.0.0.1:5173`  
> **Authentication:** Bearer JWT (`Authorization: Bearer <access_token>`)  
> **Data Format:** JSON (`Content-Type: application/json`)  

---

## 1. Global Response Envelope

All API endpoints strictly return a predictable JSON envelope.

### 1.1 Success Response (`200 OK`, `201 Created`)
```json
{
  "success": true,
  "data": { ... }
}
```

### 1.2 Error Response (`400`, `401`, `403`, `404`, `500`, `502`)
```json
{
  "success": false,
  "error": {
    "code": "ERROR_CODE",
    "message": "Human-readable message explaining the failure.",
    "details": { ... }
  }
}
```

---

## 2. Error Codes Catalog

| Error Code | HTTP Status | Description |
|---|---|---|
| `VALIDATION_ERROR` | 400 | Payload failed schema validation (e.g. missing fields, invalid types). `details` contains field-level errors. |
| `USER_ALREADY_EXISTS` | 400 | User with the requested email or username is already registered. |
| `INVALID_OTP` | 400 | The entered 6-digit verification code is incorrect. Details include remaining attempts. |
| `OTP_EXPIRED` | 400 | The verification code has expired (valid for 10 minutes). User must request a new code. |
| `OTP_MAX_ATTEMPTS_EXCEEDED` | 400 | Exceeded 5 failed verification attempts. The code has been locked out. |
| `OTP_NOT_FOUND` | 404 | No active or unconsumed OTP found for the given email address. |
| `NOT_AUTHENTICATED` | 401 | Missing `Authorization: Bearer <token>` header on a protected endpoint. |
| `AUTHENTICATION_FAILED` | 401 | Invalid username/email or password, or expired/malformed JWT. |
| `PERMISSION_DENIED` | 403 | Authenticated user is not permitted to view or email the requested trip. |
| `TRIP_NOT_FOUND` | 404 | The requested trip ID does not exist in the database. |
| `AI_SERVICE_ERROR` | 502 | Upstream AI concierge rate limit or model capacity error. Frontend should retry or inform user. |
| `METHOD_NOT_ALLOWED` | 405 | HTTP method (e.g. PUT/DELETE) not supported on this endpoint. |
| `INTERNAL_SERVER_ERROR` | 500 | Unexpected server error. |

---

## 3. Endpoints Reference

### 3.1 System Health Check

#### `GET /api/health/`
Checks database connectivity. Does not require authentication.

- **Request:**
  - Headers: None required
- **Success Response (`200 OK`):**
  ```json
  {
    "success": true,
    "data": {
      "status": "ok",
      "database": "connected"
    }
  }
  ```

---

### 3.2 Authentication Endpoints (`/api/auth/*`)

#### `POST /api/auth/register/`
Registers a new user with classical email and password authentication.

- **Request Body:**
  ```json
  {
    "username": "traveler_dan",
    "email": "dan@example.com",
    "password": "SecurePassword123!"
  }
  ```
- **Success Response (`201 Created`):**
  ```json
  {
    "success": true,
    "data": {
      "access": "eyJhbGciOi...",
      "refresh": "eyJhbGciOi...",
      "user": {
        "id": 1,
        "username": "traveler_dan",
        "email": "dan@example.com"
      }
    }
  }
  ```

---

#### `POST /api/auth/login/`
Authenticates a user via either their username or email, plus password.

- **Request Body:**
  ```json
  {
    "identifier": "dan@example.com",
    "password": "SecurePassword123!"
  }
  ```
- **Success Response (`200 OK`):**
  ```json
  {
    "success": true,
    "data": {
      "access": "eyJhbGciOi...",
      "refresh": "eyJhbGciOi...",
      "user": {
        "id": 1,
        "username": "traveler_dan",
        "email": "dan@example.com"
      }
    }
  }
  ```

---

#### `POST /api/auth/request-otp/`
Initiates passwordless login or signup. Generates a cryptographic 6-digit OTP and dispatches it via email.

- **Request Body:**
  ```json
  {
    "email": "dan@example.com"
  }
  ```
- **Success Response (`200 OK`):**
  ```json
  {
    "success": true,
    "data": {
      "email": "dan@example.com",
      "expires_in_minutes": 10
    }
  }
  ```

---

#### `POST /api/auth/verify-otp/`
Validates the 6-digit OTP code. If the user does not exist, it automatically creates an account with an auto-generated username (`{prefix}_{4char_hex}`) and sets an unusable password.

- **Request Body:**
  ```json
  {
    "email": "dan@example.com",
    "code": "481923"
  }
  ```
- **Success Response (`200 OK`):**
  ```json
  {
    "success": true,
    "data": {
      "access": "eyJhbGciOi...",
      "refresh": "eyJhbGciOi...",
      "isNewUser": true,
      "user": {
        "id": 2,
        "username": "dan_95a1",
        "email": "dan@example.com"
      }
    }
  }
  ```

---

#### `GET /api/auth/me/`
Protected endpoint returning the profile of the currently authenticated user.

- **Headers:**
  - `Authorization: Bearer <access_token>`
- **Success Response (`200 OK`):**
  ```json
  {
    "success": true,
    "data": {
      "id": 2,
      "username": "dan_95a1",
      "email": "dan@example.com"
    }
  }
  ```

---

### 3.3 Trip Itinerary Endpoints (`/api/trips/*`)

#### `POST /api/trips/generate/`
Generates a search-grounded travel roadmap using Groq LPU (with Gemini fallback) and Pydantic structured output validation, and persists the itinerary into PostgreSQL.

- **Authentication:** Optional. If an `Authorization: Bearer <token>` header is present, the trip is linked to the authenticated user's account. If unauthenticated, the trip is saved with `user: null` (guest session).
- **Request Body:**
  Supports both camelCase and snake_case properties:
  ```json
  {
    "origin": "Kochi",
    "destination": "Dubai",
    "days": 3,
    "members": 2,
    "budget": 6000,
    "currency": "AED",
    "travelStyle": "Sightseeing & Foodie",
    "extraNotes": "Love skyline views, desert safari, Lebanese mezze and Pakistani grills"
  }
  ```
- **Success Response (`201 Created`):**
  ```json
  {
    "success": true,
    "data": {
      "id": 14,
      "origin": "Kochi",
      "destination": "Dubai",
      "days": 3,
      "itinerary": {
        "tripTitle": "Dubai Skyline & Desert Adventure from Kochi",
        "summary": "A 3-day high-energy journey through Dubai balancing futuristic skyline architecture, ancient creek souks, desert dune safaris, and legendary dining.",
        "heroImages": [
          "https://images.unsplash.com/photo-1549921296-3c9b9e5c5c5a?auto=format&fit=crop&w=1600&q=80",
          "https://images.unsplash.com/photo-1512453970808-5e9e5e5c9c3b?auto=format&fit=crop&w=1600&q=80",
          "https://images.unsplash.com/photo-1507525428034-b723cf961d3e?auto=format&fit=crop&w=1600&q=80",
          "https://images.unsplash.com/photo-1563720225-1c2c5e1b7a5c?auto=format&fit=crop&w=1600&q=80",
          "https://images.unsplash.com/photo-1526401485004-6c8c8c5e2a9b?auto=format&fit=crop&w=1600&q=80"
        ],
        "budgetBreakdown": {
          "flights": 2400.0,
          "accommodation": 1600.0,
          "foodAndDining": 1200.0,
          "activitiesAndLocalTransit": 770.0,
          "totalEstimated": 5970.0,
          "currency": "AED"
        },
        "flightOptions": [
          {
            "airline": "Emirates",
            "route": "COK to DXB (Direct)",
            "estimatedPrice": 1200.0,
            "duration": "4h 15m",
            "stops": "Nonstop",
            "bookingSearchUrl": "https://www.google.com/travel/flights?q=flights+from+Kochi+to+Dubai",
            "tip": "Book 4-6 weeks in advance for direct evening departures on Emirates."
          },
          {
            "airline": "flydubai",
            "route": "COK to DXB (Direct)",
            "estimatedPrice": 950.0,
            "duration": "4h 25m",
            "stops": "Nonstop",
            "bookingSearchUrl": "https://www.google.com/travel/flights?q=flights+from+Kochi+to+Dubai",
            "tip": "Budget direct alternative with generous baggage packages."
          },
          {
            "airline": "Air India",
            "route": "COK to DXB (Direct)",
            "estimatedPrice": 1050.0,
            "duration": "4h 20m",
            "stops": "Nonstop",
            "bookingSearchUrl": "https://www.google.com/travel/flights?q=flights+from+Kochi+to+Dubai",
            "tip": "Includes full hot meal service and standard 30kg check-in allowance."
          }
        ],
        "hotelRecommendations": [
          {
            "name": "Rove Downtown",
            "neighborhood": "Downtown Dubai",
            "pricePerNight": 480.0,
            "rating": "4.6/5",
            "whyItFits": "Prime location directly facing Burj Khalifa, walkable to Dubai Mall.",
            "bookingSearchUrl": "https://www.google.com/travel/hotels?q=hotels+in+Downtown+Dubai"
          },
          {
            "name": "Aloft Palm Jumeirah",
            "neighborhood": "Palm Jumeirah",
            "pricePerNight": 550.0,
            "rating": "4.5/5",
            "whyItFits": "Beachfront lifestyle and resort views at a balanced price point.",
            "bookingSearchUrl": "https://www.google.com/travel/hotels?q=hotels+in+Palm+Jumeirah"
          },
          {
            "name": "Al Seef Heritage Hotel",
            "neighborhood": "Dubai Creek / Al Fahidi",
            "pricePerNight": 420.0,
            "rating": "4.5/5",
            "whyItFits": "Traditional Emirati architecture on the banks of Dubai Creek.",
            "bookingSearchUrl": "https://www.google.com/travel/hotels?q=hotels+in+Al+Seef+Dubai"
          }
        ],
        "days": [
          {
            "day": 1,
            "theme": "Arrival, Downtown Glitz & Iconic Skyline",
            "activities": [
              {
                "time": "11:00 AM",
                "title": "Burj Khalifa – At The Top Observation Deck",
                "category": "sightseeing",
                "description": "Ascend to levels 124 & 125 for 360-degree views across Dubai's desert, sea, and skyscrapers.",
                "estimatedCost": 179.0,
                "mapOrBookingUrl": "https://www.google.com/maps/search/?api=1&query=Burj+Khalifa+Dubai",
                "imageUrl": "https://images.unsplash.com/photo-1549921296-3c9b9e5c5c5a?auto=format&fit=crop&w=1200&q=80"
              },
              {
                "time": "03:00 PM",
                "title": "Dubai Mall & Underwater Aquarium",
                "category": "shopping",
                "description": "Explore the massive retail center, indoor waterfalls, and the giant aquarium viewing panel.",
                "estimatedCost": 0.0,
                "mapOrBookingUrl": "https://www.google.com/maps/search/?api=1&query=Dubai+Mall",
                "imageUrl": "https://images.unsplash.com/photo-1512453970808-5e9e5e5c9c3b?auto=format&fit=crop&w=1200&q=80"
              },
              {
                "time": "07:30 PM",
                "title": "Dubai Fountain Show at Burj Lake",
                "category": "experience",
                "description": "Witness the choreographed water dance set to Arabian and global hits under the illuminated Burj Khalifa.",
                "estimatedCost": 0.0,
                "mapOrBookingUrl": "https://www.google.com/maps/search/?api=1&query=Dubai+Fountain",
                "imageUrl": "https://images.unsplash.com/photo-1512453970808-5e9e5e5c9c3b?auto=format&fit=crop&w=1200&q=80"
              }
            ],
            "restaurantPicks": [
              {
                "name": "Al Mallah",
                "cuisine": "Lebanese Grill & Mezze",
                "priceRange": "$",
                "signatureDish": "Shish Tawook & Garlic Cream with Fresh Pita",
                "mapUrl": "https://www.google.com/maps/search/?api=1&query=Al+Mallah+Dhiyafa+Dubai",
                "imageUrl": "https://images.unsplash.com/photo-1600891964599-f61ba0e24092?auto=format&fit=crop&w=1200&q=80"
              },
              {
                "name": "Ravi Restaurant",
                "cuisine": "Pakistani Grills & Curries",
                "priceRange": "$",
                "signatureDish": "Chicken Mutton Peshawari Karahi & Fresh Naan",
                "mapUrl": "https://www.google.com/maps/search/?api=1&query=Ravi+Restaurant+Satwa+Dubai",
                "imageUrl": "https://images.unsplash.com/photo-1586190848861-99aa4a171e90?auto=format&fit=crop&w=1200&q=80"
              },
              {
                "name": "% Arabica Dubai Mall",
                "cuisine": "Artisan Specialty Coffee",
                "priceRange": "$$",
                "signatureDish": "Kyoto Drip Coffee & Spanish Latte",
                "mapUrl": "https://www.google.com/maps/search/?api=1&query=Arabica+Dubai+Mall",
                "imageUrl": "https://images.unsplash.com/photo-1511920170033-f8396924c348?auto=format&fit=crop&w=1200&q=80"
              }
            ]
          }
        ]
      }
    }
  }
  ```

---

#### `GET /api/trips/`
Lists all trip plans created by the authenticated user.

- **Authentication:** Required (`Authorization: Bearer <access_token>`)
- **Success Response (`200 OK`):**
  ```json
  {
    "success": true,
    "data": [
      {
        "id": 14,
        "tripTitle": "Dubai Skyline & Desert Adventure from Kochi",
        "origin": "Kochi",
        "destination": "Dubai",
        "days": 3,
        "members": 2,
        "budget": "6000.00",
        "currency": "AED",
        "travelStyle": "Sightseeing & Foodie",
        "createdAt": "2026-11-20T08:58:18.123456Z"
      }
    ]
  }
  ```

---

#### `GET /api/trips/:id/`
Retrieves full itinerary details for a trip by ID.
- Accessible if:
  1. The trip is a guest trip (`user: null`), or
  2. The authenticated user is the owner of the trip.
- **Success Response (`200 OK`):**
  ```json
  {
    "success": true,
    "data": {
      "id": 14,
      "origin": "Kochi",
      "destination": "Dubai",
      "days": 3,
      "members": 2,
      "budget": "6000.00",
      "currency": "AED",
      "travelStyle": "Sightseeing & Foodie",
      "travel_style": "Sightseeing & Foodie",
      "extraNotes": "Love skyline views, desert safari, Lebanese mezze and Pakistani grills",
      "extra_notes": "Love skyline views, desert safari, Lebanese mezze and Pakistani grills",
      "itinerary": {
        "tripTitle": "Dubai Skyline & Desert Adventure from Kochi",
        "summary": "A 3-day high-energy journey through Dubai balancing futuristic skyline architecture, ancient creek souks, desert dune safaris, and legendary dining.",
        "heroImages": [
          "https://images.unsplash.com/photo-1549921296-3c9b9e5c5c5a?auto=format&fit=crop&w=1600&q=80",
          "https://images.unsplash.com/photo-1512453970808-5e9e5e5c9c3b?auto=format&fit=crop&w=1600&q=80",
          "https://images.unsplash.com/photo-1507525428034-b723cf961d3e?auto=format&fit=crop&w=1600&q=80",
          "https://images.unsplash.com/photo-1563720225-1c2c5e1b7a5c?auto=format&fit=crop&w=1600&q=80",
          "https://images.unsplash.com/photo-1526401485004-6c8c8c5e2a9b?auto=format&fit=crop&w=1600&q=80"
        ],
        "budgetBreakdown": {
          "flights": 2400.0,
          "accommodation": 1600.0,
          "foodAndDining": 1200.0,
          "activitiesAndLocalTransit": 770.0,
          "totalEstimated": 5970.0,
          "currency": "AED"
        },
        "flightOptions": [
          {
            "airline": "Emirates",
            "route": "COK to DXB (Direct)",
            "estimatedPrice": 1200.0,
            "duration": "4h 15m",
            "stops": "Nonstop",
            "bookingSearchUrl": "https://www.google.com/travel/flights?q=flights+from+Kochi+to+Dubai",
            "tip": "Book 4-6 weeks in advance for direct evening departures on Emirates."
          }
        ],
        "hotelRecommendations": [
          {
            "name": "Rove Downtown",
            "neighborhood": "Downtown Dubai",
            "pricePerNight": 480.0,
            "rating": "4.6/5",
            "whyItFits": "Prime location directly facing Burj Khalifa, walkable to Dubai Mall.",
            "bookingSearchUrl": "https://www.google.com/travel/hotels?q=hotels+in+Downtown+Dubai"
          }
        ],
        "days": [
          {
            "day": 1,
            "theme": "Arrival, Downtown Glitz & Iconic Skyline",
            "activities": [
              {
                "time": "11:00 AM",
                "title": "Burj Khalifa – At The Top Observation Deck",
                "category": "sightseeing",
                "description": "Ascend to levels 124 & 125 for 360-degree views across Dubai's desert, sea, and skyscrapers.",
                "estimatedCost": 179.0,
                "mapOrBookingUrl": "https://www.google.com/maps/search/?api=1&query=Burj+Khalifa+Dubai",
                "imageUrl": "https://images.unsplash.com/photo-1549921296-3c9b9e5c5c5a?auto=format&fit=crop&w=1200&q=80"
              }
            ],
            "restaurantPicks": [
              {
                "name": "Al Mallah",
                "cuisine": "Lebanese Grill & Mezze",
                "priceRange": "$",
                "signatureDish": "Shish Tawook & Garlic Cream with Fresh Pita",
                "mapUrl": "https://www.google.com/maps/search/?api=1&query=Al+Mallah+Dhiyafa+Dubai",
                "imageUrl": "https://images.unsplash.com/photo-1600891964599-f61ba0e24092?auto=format&fit=crop&w=1200&q=80"
              }
            ]
          }
        ]
      },
      "createdAt": "2026-11-20T08:58:18.123456Z",
      "created_at": "2026-11-20T08:58:18.123456Z"
    }
  }
  ```

---

#### `POST /api/trips/:id/email-roadmap/`
Emails the generated travel roadmap (flights, hotel picks, day-by-day schedule with booking links) directly to the traveler.

- **Authentication:** Optional.
  - If authenticated: defaults to the user's registered email if not supplied in body.
  - If unauthenticated guest: `email` must be provided in the request body.
- **Request Body:**
  ```json
  {
    "email": "traveler@example.com"
  }
  ```
- **Success Response (`200 OK`):**
  ```json
  {
    "success": true,
    "data": {
      "trip_id": 14,
      "recipient_email": "traveler@example.com",
      "status": "sent"
    }
  }
  ```

---

## 4. TypeScript Frontend Types

```typescript
// Envelope Types
export interface ApiResponse<T> {
  success: boolean;
  data: T;
}

export interface ApiErrorResponse {
  success: false;
  error: {
    code: string;
    message: string;
    details?: Record<string, string[] | string>;
  };
}

// User & Auth
export interface UserProfile {
  id: number;
  username: string;
  email: string;
}

export interface AuthTokens {
  access: string;
  refresh: string;
  user: UserProfile;
  isNewUser?: boolean;
}

// Trip Itinerary Components
export interface FlightOption {
  airline: string;
  route: string;
  estimatedPrice: number;
  duration: string;
  stops: string;
  bookingSearchUrl: string;
  tip: string;
}

export interface HotelRecommendation {
  name: string;
  neighborhood: string;
  pricePerNight: number;
  rating: string;
  whyItFits: string;
  bookingSearchUrl: string;
}

export interface ActivityItem {
  time: string;
  title: string;
  category: 'sightseeing' | 'transit' | 'experience' | 'shopping' | string;
  description: string;
  estimatedCost: number;
  mapOrBookingUrl: string;
  imageUrl: string;
}

export interface RestaurantPick {
  name: string;
  cuisine: string;
  priceRange: string;
  signatureDish: string;
  mapUrl: string;
  imageUrl: string;
}

export interface DayPlan {
  day: number;
  theme: string;
  activities: ActivityItem[];
  restaurantPicks: RestaurantPick[];
}

export interface BudgetBreakdown {
  flights: number;
  accommodation: number;
  foodAndDining: number;
  activitiesAndLocalTransit: number;
  totalEstimated: number;
  currency: string;
}

export interface TripItinerary {
  tripTitle: string;
  summary: string;
  heroImages: string[];
  budgetBreakdown: BudgetBreakdown;
  flightOptions: FlightOption[];
  hotelRecommendations: HotelRecommendation[];
  days: DayPlan[];
}

export interface TripPlanSummary {
  id: number;
  tripTitle: string;
  origin: string;
  destination: string;
  days: number;
  members: number;
  budget: string | null;
  currency: string;
  travelStyle: string;
  createdAt: string;
}

export interface TripPlanDetail extends TripPlanSummary {
  travel_style: string;
  extraNotes: string;
  extra_notes: string;
  itinerary: TripItinerary;
  created_at: string;
}

export interface TripGenerateInput {
  origin: string;
  destination: string;
  days: number;
  members?: number;
  budget?: number | null;
  currency?: string;
  travelStyle?: string;
  travel_style?: string;
  extraNotes?: string;
  extra_notes?: string;
}
```

---

## 5. React / Axios Client Example

```typescript
import axios from 'axios';

const api = axios.create({
  baseURL: 'http://localhost:8000/api',
  headers: {
    'Content-Type': 'application/json',
  },
});

// Automatically inject JWT access token if present in localStorage
api.interceptors.request.use((config) => {
  const token = localStorage.getItem('waypoint_access_token');
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

// Example: Generate Trip
export async function generateTrip(params: TripGenerateInput) {
  const response = await api.post('/trips/generate/', params);
  return response.data.data;
}

// Example: Request Email OTP
export async function requestOTP(email: string) {
  const response = await api.post('/auth/request-otp/', { email });
  return response.data.data;
}

// Example: Verify Email OTP
export async function verifyOTP(email: string, code: string) {
  const response = await api.post('/auth/verify-otp/', { email, code });
  const { access, refresh, user } = response.data.data;
  localStorage.setItem('waypoint_access_token', access);
  localStorage.setItem('waypoint_refresh_token', refresh);
  return user;
}
```
