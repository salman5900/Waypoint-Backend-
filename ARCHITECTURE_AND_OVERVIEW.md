# Waypoint Backend — Architecture & System Overview

> **Version:** 1.2.0  
> **Framework:** Django 5+ / 6.1 + Django REST Framework 3.18  
> **Database:** PostgreSQL (with `psycopg` 3.3 binary & `JSONField`)  
> **Primary AI Engine:** Groq LPU Inference SDK (`groq` 1.7) with Pydantic JSON Schema enforcement  
> **Secondary AI Engine:** Google Gemini GenAI SDK (`google-genai` 3.5) with Search Grounding & Pydantic Schema Validation  
> **Authentication:** Hybrid (Classical Password + Cryptographic Passwordless Email OTP + SimpleJWT)  

---

## 1. Architectural Philosophy & Zero-Spaghetti Rules

The Waypoint backend is built with strict modular domain isolation following the **Thin Views, Fat Services, Dedicated Selectors** paradigm. Spaghetti code (mixing business logic, database queries, hashing, external SDKs, or email dispatching directly inside views or serializers) is strictly forbidden.

### Core Architectural Principles
1. **Thin Views:**
   - `views.py` files are strictly limited to request parsing, DRF serializer validation (`is_valid(raise_exception=True)`), dispatching to domain services in `services.py`, and returning standard envelopes.
   - Views **never** run ORM queries directly, hash passwords/OTPs, call the Gemini/Groq SDKs, or send emails.
2. **Dedicated Selectors (`selectors.py`):**
   - All read-only database queries, filtering, lookups, and connection health checks live exclusively in `selectors.py`.
   - Business services and views consume selectors, keeping query logic centralized, testable, and reusable.
3. **Fat Services (`services.py`):**
   - All state mutations, transactions, OTP generation/hashing, user registration, JWT issuance, Groq/Gemini AI calls, day-count validation, automated retry orchestration, and email dispatching reside in `services.py`.
4. **Pure Serializers (`serializers.py`):**
   - DRF serializers validate data contracts, field constraints, types, and serialize model outputs. They contain no side effects or business queries.
5. **Centralized Exception Handling & Standard Envelope:**
   - Every endpoint produces a standardized, predictable JSON response envelope:
     - **Success:** `{ "success": true, "data": { ... } }`
     - **Error:** `{ "success": false, "error": { "code": "ERROR_CODE", "message": "Human readable message", "details": ... } }`
   - Custom domain exceptions (`InvalidOTPError`, `OTPExpiredError`, `OTPMaxAttemptsError`, `OTPNotFoundError`, `AuthenticationFailedError`, `UserAlreadyExistsError`, `AIServiceError`, `TripNotFoundError`, `PermissionDeniedError`) are converted into standard error responses with appropriate HTTP status codes via `core.exceptions.custom_exception_handler`.

---

## 2. Directory Tree Structure

```text
Waypoint Backend/
├── config/
│   ├── __init__.py
│   ├── settings/
│   │   ├── __init__.py
│   │   ├── base.py              # Base configuration, JWT, CORS, email & Groq/Gemini settings
│   │   └── local.py             # Local dev settings (inherits base, DEBUG=True)
│   ├── urls.py                  # Root URL dispatcher (/api/health/, /api/auth/, /api/trips/)
│   └── wsgi.py                  # WSGI application entrypoint
├── core/
│   ├── __init__.py
│   ├── apps.py
│   ├── exceptions.py            # Custom domain exceptions & centralized DRF exception handler
│   ├── permissions.py           # Reusable DRF permissions (e.g. IsTripOwner)
│   └── responses.py             # Standard API envelope helpers (success_response, error_response)
├── accounts/
│   ├── __init__.py
│   ├── apps.py
│   ├── models.py                # User(AbstractUser) with unique email + EmailOTP
│   ├── selectors.py             # Read-only DB queries for users and OTP records
│   ├── services.py              # Password auth, OTP lifecycle, user onboarding, JWT tokens
│   ├── serializers.py           # Register, login, OTP request/verify request serializers
│   ├── views.py                 # Thin auth views
│   ├── urls.py                  # /api/auth/* routes
│   └── tests.py                 # Automated unit and integration tests (19 tests)
├── trips/
│   ├── __init__.py
│   ├── apps.py
│   ├── models.py                # TripPlan with PostgreSQL JSONField
│   ├── schemas.py               # Pydantic schemas for AI structured output + photo URLs
│   ├── services.py              # Groq Primary + Gemini Fallback + Email Roadmap engine
│   ├── selectors.py             # Trip queries & DB health ping
│   ├── serializers.py           # Trip request & response serializers
│   ├── views.py                 # Thin trip generation, history, detail, and email views
│   ├── urls.py                  # /api/trips/* routes
│   └── tests.py                 # Automated unit and integration tests (23 tests)
├── ARCHITECTURE_AND_OVERVIEW.md # This document
├── API_CONTRACT.md              # Frontend integration contract & API reference
├── manage.py
├── requirements.txt             # Pinned production dependencies
├── .env                         # Local environment variables (ignored by Git)
├── .env.example                 # Environment template
└── .gitignore                   # Ignores venv/, .env, __pycache__/, *.pyc, .DS_Store
```

---

## 3. Database Schema & Data Models

### 3.1 `accounts.User` (`AUTH_USER_MODEL = 'accounts.User'`)
Inherits from Django's `AbstractUser` with customized constraints:
- `id`: BigAutoField (Primary Key)
- `email`: `EmailField(unique=True, db_index=True)`
- `username`: `CharField(max_length=150, unique=True)`
  - For classical signups: chosen by user.
  - For passwordless OTP signups: auto-generated cleanly as `{email_prefix}_{4_char_hex}` (e.g. `john_a8f2`).
- `password`: Hashed using PBKDF2/SHA256 (set to unusable password for OTP-only users).

### 3.2 `accounts.EmailOTP`
Stores temporary verification codes for passwordless signin/signup:
- `id`: BigAutoField
- `email`: `EmailField(db_index=True)`
- `code_hash`: `CharField(max_length=255)` (Hashed using `django.contrib.auth.hashers.make_password`, plaintext code is never stored in DB)
- `created_at`: `DateTimeField(auto_now_add=True)`
- `expires_at`: `DateTimeField()` (+10 minutes from creation)
- `attempts`: `PositiveSmallIntegerField(default=0)` (Max 5 attempts before lockout)
- `is_used`: `BooleanField(default=False)`
- **Indexes:** `[email, is_used, expires_at]` composite index for rapid lookup and validation.

### 3.3 `trips.TripPlan`
Stores generated travel itineraries and trip parameters:
- `id`: BigAutoField
- `user`: `ForeignKey(User, null=True, blank=True, on_delete=models.CASCADE, related_name='trips')`
  - Nullable to support unauthenticated guest generation and seamless testing from the React frontend.
- `origin`: `CharField(max_length=255)`
- `destination`: `CharField(max_length=255)`
- `days`: `PositiveIntegerField()`
- `members`: `PositiveIntegerField(default=1)`
- `budget`: `DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)`
- `currency`: `CharField(max_length=10, default='USD')`
- `travel_style`: `CharField(max_length=100, blank=True, default='')`
- `extra_notes`: `TextField(blank=True, default='')`
- `itinerary_json`: `JSONField()` conforming strictly to `TripItinerarySchema`:
  - `tripTitle`: Catchy journey title
  - `summary`: High-level overview
  - `heroImages`: Array of 5 distinct, high-resolution landscape photo URLs showcasing the destination city and its iconic landmarks
  - `budgetBreakdown`: Itemized financial breakdown (`flights`, `accommodation`, `foodAndDining`, `activitiesAndLocalTransit`, `totalEstimated`, `currency`)
  - `flightOptions`: 2-3 flight options with active operating airlines and direct Google Flights search URLs
  - `hotelRecommendations`: 2-3 verified properties with direct Google Hotels booking links
  - `days`: Array of exactly `days` day objects, each containing:
    - `activities`: $\ge 2$ activities per day, each with an accurate `imageUrl` matching the landmark
    - `restaurantPicks`: 2-3 curated dining options per day, each with an accurate `imageUrl` matching the cuisine, dish, or ambiance
- `created_at`: `DateTimeField(auto_now_add=True)`
- **Indexes:** `[user, -created_at]` index for fast user trip history pagination.

---

## 4. Authentication Architecture

Waypoint supports a **dual authentication model**:

```
                       ┌────────────────────────────────────────────────────────┐
                       │                   Waypoint Auth Engine                 │
                       └───────────────────────────┬────────────────────────────┘
                                                   │
                  ┌────────────────────────────────┴────────────────────────────────┐
                  ▼                                                                 ▼
      [ Classical Password Auth ]                                       [ Passwordless Email OTP ]
   1. POST /api/auth/register/                                        1. POST /api/auth/request-otp/
      -> Creates User with hashed password.                              -> Invalidates older pending OTPs.
      -> Returns Access + Refresh JWT.                                   -> Generates 6-digit random code.
   2. POST /api/auth/login/                                              -> Stores PBKDF2/SHA-256 hash in DB.
      -> Accepts identifier (username or email).                         -> Dispatches email (console or SMTP).
      -> Checks password hash.                                        2. POST /api/auth/verify-otp/
      -> Returns Access + Refresh JWT.                                   -> Checks attempts <= 5 and not expired.
                                                                         -> Atomically matches hash.
                                                                         -> If new user: auto-creates user.
                                                                         -> Marks OTP as used.
                                                                         -> Returns Access + Refresh JWT + isNewUser.
```

### Security Measures in OTP Service
1. **Plaintext Protection:** Raw 6-digit OTP codes are hashed via `make_password(...)` prior to database insertion.
2. **Older OTP Invalidation:** Generating a new OTP automatically sets all prior unused OTPs for that email to `is_used=True`.
3. **Brute Force Lockout:** After 5 failed verification attempts, the OTP is permanently marked `is_used=True` and rejects subsequent attempts with `OTP_MAX_ATTEMPTS_EXCEEDED`.
4. **Time-To-Live (TTL):** Hard expiry enforced at 10 minutes (`OTP_EXPIRED`).
5. **Replay Protection:** Once verified, an OTP cannot be reused.

---

## 5. Dual AI Engine: Groq LPU (Primary) + Gemini (Fallback)

Waypoint employs an enterprise dual-provider AI orchestration pipeline in `trips/services.py` designed to ensure zero downtime, eliminate upstream rate-limiting bottlenecks, and enforce strict Pydantic JSON schema compliance.

```
                    ┌────────────────────────────────────────────────────────┐
                    │               Waypoint AI Orchestrator                 │
                    │         (trips.services.generate_trip_itinerary)       │
                    └───────────────────────────┬────────────────────────────┘
                                                │
                          ┌─────────────────────┴─────────────────────┐
                          ▼                                           ▼
             [ Primary Provider: Groq ]                  [ Secondary: Gemini ]
           • SDK: groq.Groq                            • SDK: google-genai
           • Models: llama-3.3-70b-versatile           • Models: gemini-3.8-flash,
             / openai/gpt-oss-120b                       gemini-3.5-flash
           • Max Tokens: 6000, Temp: 0.4               • Search Grounding Tools
           • Schema Injection: model_json_schema()     • Fallback if Groq unavailable
                          │                                           ▲
                          └──────────(On Error / Rate Limit)──────────┘
```

### 5.1 Primary Provider: Groq LPU Inference (`_generate_with_groq`)
- **Fast, Predictable Generation:** Uses Groq's low-latency inference engine with `response_format={"type": "json_object"}`.
- **Large Token Window & Determinism:** Configured with `max_tokens=6000` and `temperature=0.4` so multi-day itineraries never truncate early.
- **Pydantic Schema Injection:** Embeds the full JSON schema generated by `TripItinerarySchema.model_json_schema()` directly into the system prompt to guarantee all required keys (`tripTitle`, `summary`, `heroImages`, `budgetBreakdown`, `flightOptions`, `hotelRecommendations`, `days`) are produced.
- **Model Cascade:** Uses `settings.GROQ_MODEL` (`llama-3.3-70b-versatile` by default), with automatic cascade to high-performance available models (`openai/gpt-oss-120b`, `qwen/qwen3.8-27b`) if a catalog model is unavailable.
- **Validation:** Every response is validated using `TripItinerarySchema.model_validate_json(raw_text)` before being returned.

### 5.2 Secondary Fallback: Google Gemini GenAI (`_generate_with_gemini`)
- **Search Grounding:** Uses `types.GenerateContentConfig(tools=[types.Tool(google_search=types.GoogleSearch())], response_schema=TripItinerarySchema)`.
- **Automatic Triggering:** Triggered automatically if Groq encounters an error, missing API key, or rate limit.
- **Resilience:** Maps upstream 429 quota exhaustion cleanly to `AIServiceError` without crashing or returning unhandled 500 errors.

### 5.3 Programmatic Day-Count Completeness Validation & Single Retry
- `validate_itinerary_structure` enforces:
  - Exactly `expected_days` day objects in the `days` array.
  - At least 2 distinct activities per day.
  - At least 1 restaurant pick per day (with prompt instructing 2–3 picks).
- If the model returns fewer days or incomplete days, `generate_trip_itinerary` catches the violation and automatically re-queries once with an amplified correction prompt before raising `AIServiceError`.

### 5.4 Accuracy & Photography Mandates
- **Active Airlines Only:** Restricts recommendations to currently operating active carriers (e.g., Air India, IndiGo, JAL, ANA, Singapore Airlines, Emirates, flydubai, AirAsia); strictly excludes defunct/merged carriers like Vistara.
- **Real Dining & Dietary Notes:** Recommends verified dining spots matching traveler dietary preferences (e.g., T's TanTan, Afuri for vegetarian ramen in Tokyo; Al Mallah, Ravi, Zuma in Dubai).
- **High-Resolution Photography URLs:**
  - `heroImages`: 5 distinct landscape photo URLs for the destination city.
  - `ActivityItem.imageUrl`: Specific landmark photo URL.
  - `RestaurantPick.imageUrl`: Cuisine, signature dish, or ambiance photo URL.

### 5.5 Manual Booking Roadmap Philosophy
Rather than attempting fragile automated checkout, Waypoint constructs an **actionable manual-booking roadmap**. Every flight and hotel includes direct, pre-populated deep-search links (e.g., `https://www.google.com/travel/flights?q=flights+from+COK+to+DXB`), allowing travelers to click and book directly on airline or hotel platforms.

### 5.6 Email Configuration (Gmail SMTP & Local Console Backend)
`config/settings/base.py` automatically configures email delivery:
- **Production / Gmail SMTP:** When `EMAIL_HOST_USER` and `EMAIL_HOST_PASSWORD` are populated in `.env`, Django routes emails via `smtp.gmail.com:587` with `EMAIL_USE_TLS=True` and `EMAIL_USE_SSL=False`. Magic OTP codes and roadmaps arrive directly in real Gmail inboxes.
- **Local Testing:** When credentials are left blank, Django automatically uses `django.core.mail.backends.console.EmailBackend`, printing clean emails to stdout.

---

## 6. Testing & Quality Assurance

The codebase includes comprehensive automated test coverage with **42 out of 42 tests passing** (100% pass rate):

| Test Suite | Tests | Scope | Status |
|---|---|---|---|
| `accounts.tests.ClassicAuthTests` | 8 | User registration, duplicate checks, short passwords, username/email login, invalid password failure | **PASS** |
| `accounts.tests.EmailOTPAuthTests` | 8 | Request OTP, email dispatch, invalidation of older OTPs, new user auto-signup, existing user login, wrong OTP attempt counter, lockout after 5 attempts, expired OTP rejection, reuse prevention | **PASS** |
| `accounts.tests.ProtectedMeEndpointTests` | 3 | Token presence check, invalid token rejection, valid token user profile response | **PASS** |
| `trips.tests.HealthCheckTests` | 1 | Database connection ping and `/api/health/` response | **PASS** |
| `trips.tests.AIProviderOrchestrationTests` | 7 | Groq primary preference, Gemini fallback, dual failure error handling, day-count validation retry, persistent failure handling, structure validation rules, Groq direct API call | **PASS** |
| `trips.tests.TripGenerationTests` | 5 | Missing fields, invalid day ranges, guest trip generation with heroImages/imageUrls, authenticated trip generation, AI error handling | **PASS** |
| `trips.tests.TripHistoryAndDetailTests` | 6 | Unauthorized listing, user trip isolation, guest trip detail, owner trip detail, cross-user permission denial, 404 trip not found | **PASS** |
| `trips.tests.TripEmailRoadmapTests` | 4 | Authenticated email roadmap, guest email roadmap with explicit email, missing email validation, 404 trip not found | **PASS** |

Run the test suite anytime:
```bash
./venv/bin/python manage.py test
```

---

## 7. Local Setup & Running Commands

### 7.1 Prerequisites
- PostgreSQL running on `localhost:5432` with user `postgres` and password `postgres`.
- Python 3.12+ (tested on Python 3.14).

### 7.2 Installation & Initialization
```bash
# Clone or navigate to the project directory
cd "Waypoint Backend"

# Create virtual environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Run migrations against waypoint_db
python manage.py migrate

# Run system checks
python manage.py check

# Run automated tests
python manage.py test

# Start local development server
python manage.py runserver 0.0.0.0:8000
```

### 7.3 Verifying Local Server with `curl`
```bash
# 1. Health Check
curl -s http://localhost:8000/api/health/

# 2. Register a new user
curl -s -X POST http://localhost:8000/api/auth/register/ \
  -H "Content-Type: application/json" \
  -d '{"username": "demo_traveler", "email": "demo@example.com", "password": "Password123!"}'

# 3. Login
curl -s -X POST http://localhost:8000/api/auth/login/ \
  -H "Content-Type: application/json" \
  -d '{"identifier": "demo@example.com", "password": "Password123!"}'

# 4. Request Passwordless OTP
curl -s -X POST http://localhost:8000/api/auth/request-otp/ \
  -H "Content-Type: application/json" \
  -d '{"email": "traveler@example.com"}'

# 5. Verify OTP
curl -s -X POST http://localhost:8000/api/auth/verify-otp/ \
  -H "Content-Type: application/json" \
  -d '{"email": "traveler@example.com", "code": "<6_DIGIT_CODE>"}'

# 6. Generate Trip Itinerary with Groq
curl -s -X POST http://localhost:8000/api/trips/generate/ \
  -H "Content-Type: application/json" \
  -d '{
    "origin": "Kochi",
    "destination": "Dubai",
    "days": 3,
    "members": 2,
    "budget": 6000,
    "currency": "AED",
    "travelStyle": "Sightseeing & Foodie",
    "extraNotes": "Love skyline views, desert safari, Lebanese mezze and Pakistani grills"
  }'
```
