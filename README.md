# Waypoint Backend — AI Travel Concierge Engine

[![Python](https://img.shields.io/badge/Python-3.14+-3776AB?style=flat&logo=python&logoColor=white)](https://www.python.org/)
[![Django](https://img.shields.io/badge/Django-6.1-092E20?style=flat&logo=django&logoColor=white)](https://www.djangoproject.com/)
[![DRF](https://img.shields.io/badge/Django_REST_Framework-3.18-red?style=flat)](https://www.django-rest-framework.org/)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-18-336791?style=flat&logo=postgresql&logoColor=white)](https://www.postgresql.org/)
[![Groq](https://img.shields.io/badge/Groq_LPU-openai%2Fgpt--oss-F05A28?style=flat)](https://groq.com/)
[![Gemini](https://img.shields.io/badge/Google_Gemini-3.8--flash-4285F4?style=flat&logo=google&logoColor=white)](https://ai.google.dev/)
[![Tests](https://img.shields.io/badge/Tests-43%20Passing%20(100%25)-brightgreen?style=flat)]()

Waypoint Backend is a high-performance, modular, zero-spaghetti backend service built with **Django 6.1**, **Django REST Framework (DRF)**, and **PostgreSQL**. It powers the Waypoint AI travel planner with search-grounded day-by-day itineraries, manual booking links, destination photography, hybrid authentication, and automated email roadmaps.

---

## Architecture & Design Principles

The backend strictly enforces the **Thin Views, Fat Services, Dedicated Selectors** paradigm:

- **Thin Views (`views.py`):** Strictly handle HTTP request parsing, payload validation via DRF Serializers, calling business service functions, and returning uniform JSON envelopes. No ORM queries, password/OTP hashing, AI SDK calls, or email dispatches ever occur inside views.
- **Dedicated Selectors (`selectors.py`):** Centralize all read-only database queries, filtering, and connection health checks.
- **Fat Services (`services.py`):** Own all state mutations, database writes, OTP generation and verification, SimpleJWT issuance, Groq LPU and Gemini GenAI orchestration, day-count completeness validation, retry handling, and email formatting.
- **Pydantic Schemas (`trips/schemas.py`):** Guarantee that all LLM outputs match strict structured types (`TripItinerarySchema`) before saving into PostgreSQL `JSONField`.
- **Standard JSON Envelope:** Every endpoint returns a consistent response contract:
  - **Success:** `{ "success": true, "data": { ... } }`
  - **Error:** `{ "success": false, "error": { "code": "...", "message": "...", "details": ... } }`

---

## Key Capabilities

1. **Dual AI Engine with Automatic Failover:**
   - **Primary Provider (Groq LPU):** Blazing-fast inference using `openai/gpt-oss-120b`, `openai/gpt-oss-20b`, or `llama-3.3-70b-versatile` with an `8192` output token limit.
   - **Secondary Provider (Google Gemini):** Google GenAI SDK fallback with Search Grounding support (`gemini-3.8-flash`, `gemini-3.5-flash`).
   - **Multi-Day Completeness & Auto-Retry:** Generates complete 1–14 day itineraries without truncation. If an upstream model returns fewer days than requested, the system automatically retries with a strict correction prompt or cascades to the secondary provider before returning an error.
2. **Visual Travel Photography:**
   - **5 Destination Hero Images:** High-resolution landscape URLs representing iconic sights of the destination.
   - **Activity Images:** Accurate landscape photo URLs for each landmark or tour stop.
   - **Dining Images:** Cuisine, signature dish, or ambiance photography for 2–3 dining picks per day.
3. **Manual Booking Links:**
   - Direct search query links for Google Flights, Google Hotels, and Google Maps (for activities and restaurants).
4. **Hybrid Authentication:**
   - Classical username/email + password registration and login.
   - Passwordless 6-digit cryptographic Email OTP (auto-provisions new users, 10-minute expiry, 5-attempt rate-limit lockout).
   - SimpleJWT authentication (1-day access tokens, 7-day refresh tokens).
5. **Roadmap Email Delivery:**
   - Plain-text formatted itinerary summaries with itemized budget breakdowns and manual booking links dispatched via Gmail SMTP (`smtp.gmail.com:587` with TLS).

---

## Directory Structure

```text
Waypoint Backend/
├── config/
│   ├── settings/
│   │   ├── base.py              # Core settings, CORS, JWT, email, Groq & Gemini configuration
│   │   └── local.py             # Development settings (DEBUG=True)
│   ├── urls.py                  # Root URL routing (/api/health/, /api/auth/, /api/trips/)
│   └── wsgi.py                  # WSGI entrypoint
├── core/
│   ├── exceptions.py            # Domain exceptions & centralized exception handler
│   ├── permissions.py           # Object permissions (e.g. IsTripOwner)
│   └── responses.py             # Standard JSON envelope helpers
├── accounts/
│   ├── models.py                # Custom User (AbstractUser with unique email) + EmailOTP
│   ├── selectors.py             # Read-only user & OTP queries
│   ├── services.py              # Password & OTP auth, JWT issuance, email delivery
│   ├── serializers.py           # Authentication payload validation
│   ├── views.py                 # Thin auth endpoints
│   ├── urls.py                  # Auth routes (/register, /login, /request-otp, /verify-otp, /me)
│   └── tests.py                 # Comprehensive unit & integration tests
├── trips/
│   ├── models.py                # TripPlan model with PostgreSQL JSONField itinerary_json
│   ├── schemas.py               # Pydantic structured schemas for LLM outputs
│   ├── selectors.py             # Read-only trip queries & health check selector
│   ├── services.py              # Groq/Gemini AI concierge, day-count validator, email dispatch
│   ├── serializers.py           # Trip request & response serializers
│   ├── views.py                 # Thin trip generation, listing, detail, and email views
│   ├── urls.py                  # Trip routes (/generate, /, /:id, /:id/email)
│   └── tests.py                 # Unit tests for AI orchestration, validation, and endpoints
├── API_CONTRACT.md              # Complete REST API specifications & TypeScript interfaces
├── ARCHITECTURE_AND_OVERVIEW.md # Comprehensive architectural breakdown
├── manage.py
├── requirements.txt
├── .env.example
└── README.md
```

---

## Quick Local Setup

### 1. Prerequisites
- **Python 3.12+** (Python 3.14 recommended)
- **PostgreSQL 15+** running locally on port `5432`

### 2. Clone & Environment Setup
```bash
git clone https://github.com/salman5900/Waypoint-Backend-.git
cd "Waypoint-Backend-"

# Create virtual environment
python3 -m venv venv
source venv/bin/activate

# Install pinned dependencies
pip install -r requirements.txt
```

### 3. Configure Secrets (`.env`)
Copy the example environment template:
```bash
cp .env.example .env
```

Ensure `.env` contains your API credentials and database configuration:
```ini
SECRET_KEY=your-secure-50-character-secret-key
DEBUG=True
DATABASE_URL=postgres://postgres:postgres@localhost:5432/waypoint_db

# Primary AI Provider: Groq LPU
AI_PROVIDER=groq
GROQ_API_KEY=your_groq_api_key_here
GROQ_MODEL=llama-3.3-70b-versatile

# Secondary AI Provider: Google Gemini GenAI
GEMINI_API_KEY=your_gemini_api_key_here
GEMINI_MODEL=gemini-3.8-flash

# Email Dispatch (Gmail SMTP)
EMAIL_HOST=smtp.gmail.com
EMAIL_PORT=587
EMAIL_HOST_USER=your_email@gmail.com
EMAIL_HOST_PASSWORD=your_gmail_16_character_app_password
```

### 4. Database Initialization & Migrations
Ensure PostgreSQL service is running and database `waypoint_db` exists:
```bash
# Apply database migrations
./venv/bin/python manage.py migrate
```

### 5. Run Automated Tests
Execute the full test suite (43 tests covering auth, OTP, AI orchestration, retry mechanisms, and trip endpoints):
```bash
./venv/bin/python manage.py test
```

### 6. Start the Development Server
```bash
./venv/bin/python manage.py runserver 0.0.0.0:8000
```
The API is now live at `http://localhost:8000/api/`.

---

## API Endpoints Summary

| Method | Endpoint | Auth | Description |
|---|---|---|---|
| `GET` | `/api/health/` | Public | System & PostgreSQL health check |
| `POST` | `/api/auth/register/` | Public | Classical username/email/password registration |
| `POST` | `/api/auth/login/` | Public | Classical password login (returns JWT tokens) |
| `POST` | `/api/auth/request-otp/` | Public | Request 6-digit cryptographic email OTP |
| `POST` | `/api/auth/verify-otp/` | Public | Verify OTP code & receive JWT tokens (auto-onboards) |
| `GET` | `/api/auth/me/` | Bearer JWT | Retrieve currently authenticated user profile |
| `POST` | `/api/trips/generate/` | Optional JWT | Generate AI travel roadmap (Groq primary / Gemini fallback) |
| `GET` | `/api/trips/` | Bearer JWT | List saved trip plans for authenticated user |
| `GET` | `/api/trips/:id/` | Optional JWT | Fetch full trip plan details and JSON itinerary |
| `POST` | `/api/trips/:id/email/` | Optional JWT | Email formatted roadmap & booking links |

For exhaustive request/response payloads, TypeScript interfaces, and error catalogs, refer to:
- [API_CONTRACT.md](API_CONTRACT.md) — Frontend integration contracts and TypeScript types.
- [ARCHITECTURE_AND_OVERVIEW.md](ARCHITECTURE_AND_OVERVIEW.md) — Detailed technical architecture and service layer design.

---

## License

Internal proprietary software developed for the Waypoint AI travel platform.
