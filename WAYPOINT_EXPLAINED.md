# Waypoint — Complete Application Guide & Current State
*An easy-to-understand, non-technical explanation of what Waypoint is, how it works, and its current health.*

---

## 🌟 Executive Summary: What is Waypoint?

Imagine you want to go on a vacation to Tokyo for 5 days with a budget of $1,500. 

Normally, planning this means:
- Spending 10+ hours researching on travel blogs and Reddit.
- Opening 40 different browser tabs comparing flights on Skyscanner, hotels on Booking.com, and sights on TripAdvisor.
- Manually calculating costs in an Excel spreadsheet.
- Trying to piece together which neighborhood to stay in and which sights make sense to visit on the same day without crisscrossing the city endlessly.

**Waypoint solves this completely.**

Waypoint is an **AI-powered personal travel concierge**. In less than 15 seconds, a traveler can simply say:
> *"I'm flying from Kochi to Tokyo for 3 days with a friend, our budget is $1,500, we love ramen and historic temples, and we want a balanced pace."*

Waypoint instantly builds a complete, day-by-day vacation roadmap with:
1. **Realistic Flights:** Operating airlines, flight duration, estimated prices, and direct one-click booking search links.
2. **Verified Hotels:** Neighborhood explanations, star ratings, nightly rates, and direct booking search links.
3. **Day-by-Day Itineraries:** Morning, afternoon, and evening activities with landmark photos and Google Maps links.
4. **Curated Dining:** Top local restaurant picks matching the traveler's diet and food preferences with dish recommendations.
5. **Itemized Budget Breakdown:** Total calculated spending across flights, lodging, meals, transit, and activities.
6. **One-Click Email Delivery:** The traveler can send the entire formatted roadmap straight to their email inbox so they have it on their phone while on the go.

Crucially, **Waypoint does not force you into a rigid tour package**. It is built for independent travelers who want the freedom to manual-book their own trips, but want an expert to do all the heavy research for them.

---

## 🏛️ How It Works: The 4 Main Pillars (In Plain English)

The application is composed of 4 key pillars working together seamlessly:

```
┌─────────────────────────────────────────────────────────────────────────┐
│                           THE TRAVELER (YOU)                            │
│           Enters trip details: Origin, Destination, Days, Budget        │
└────────────────────────────────────┬────────────────────────────────────┘
                                     │
                                     ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                       1. THE FRONT DOOR (API Views)                     │
│  Checks that the request has valid info (e.g. days > 0, valid cities).  │
└────────────────────────────────────┬────────────────────────────────────┘
                                     │
                                     ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                       2. THE BRAIN (Dual AI Engine)                     │
│  Primary: Groq (ultra-fast) ──[If busy/fails]──> Backup: Google Gemini  │
│  Crafts the roadmap, searches flights/hotels, and picks photography.    │
└────────────────────────────────────┬────────────────────────────────────┘
                                     │
                                     ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                       3. THE SAFETY INSPECTOR                           │
│  Verifies the AI didn't skip any days and included all required meals.  │
│  If something is missing, it asks the AI to fix it automatically.       │
└────────────────────────────────────┬────────────────────────────────────┘
                                     │
                                     ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                     4. THE VAULT & POSTMAN (DB & Email)                 │
│  Saves the itinerary in PostgreSQL and emails the roadmap to the user.  │
└─────────────────────────────────────────────────────────────────────────┘
```

---

### Pillar 1: The Front Door (Web API)
When you click "Plan My Trip" on the website, your request travels to the backend server.
- The server checks your input: Is the destination filled out? Is the number of days a positive number?
- If something is wrong (e.g. typing 0 days), it immediately sends back a polite message explaining what needs to be fixed.
- If everything looks good, it hands the request off to the AI engine.

### Pillar 2: The Brain (Dual AI Engine)
Waypoint doesn't rely on just one AI. It has a **Dual-Engine System** — think of it like an airplane with two engines:
1. **Primary Engine (Groq LPU):** Groq is an ultra-fast AI chip that produces full, rich travel itineraries in just a few seconds. It uses high-intelligence open-weights models (`llama-3.3-70b`) to write detailed, realistic schedules.
2. **Backup Engine (Google Gemini):** If Groq ever experiences high demand, network hiccups, or runs out of capacity, Waypoint automatically switches to Google Gemini without the traveler ever noticing an interruption.

### Pillar 3: The Quality Inspector (Automatic Verification)
A common problem with generative AI is that it sometimes gets "lazy" — if you ask for a 7-day trip, it might only give you 4 days and say *"repeat for remaining days"*.

**Waypoint refuses to let that happen.**
- The moment the AI answers, a built-in inspector checks:
  - Did the AI return *exactly* the requested number of days?
  - Does every single day have at least 2 distinct activities?
  - Does every day have curated restaurant recommendations?
- If the AI missed anything, Waypoint rejects the answer and automatically tells the AI: *"You only gave me 4 days, but the user requested 7. Generate all 7 days completely."*
- Only when the itinerary is 100% complete does it get approved.

### Pillar 4: The Vault & Postman (Database & Email)
- **The Vault (PostgreSQL Database):** Every generated trip is securely stored in a professional database. Even guest travelers who haven't logged in get a permanent trip ID so their itinerary is never lost.
- **The Postman (Email Engine):** With a single click, Waypoint formats the entire trip into a clean, easy-to-read travel guide and sends it to the traveler's Gmail or inbox.

---

## 🔒 User Accounts & Security: Simple, Fast, and Safe

Waypoint supports two different ways for people to use the platform:

### 1. Guest Mode (No Account Required)
- Travelers don't need to create an account just to plan a trip.
- You can visit the site, enter your destination, generate an itinerary, and even email it to yourself immediately.

### 2. Member Account (Save & Access All Trips)
For travelers who want to see their full travel history across multiple devices, Waypoint offers two sign-in options:
- **Option A: Traditional Password:** Sign up with an email, username, and password.
- **Option B: Passwordless Magic Code (Email OTP):**
  - No passwords to create or remember.
  - You type in your email address.
  - Waypoint emails you a secure, random 6-digit code.
  - You type the 6 digits into the screen, and you are logged in!
  - If you're a first-time visitor, Waypoint automatically creates your account for you in one step.

#### How Security is Handled:
- **Codes Self-Destruct:** Each 6-digit code expires in 10 minutes.
- **No Peeking:** Even if someone broke into the database, they cannot see your code because it is scrambled (cryptographically hashed with PBKDF2) the microsecond it is generated.
- **Brute-Force Shield:** If someone tries guessing codes and gets it wrong 5 times, that code is permanently locked and destroyed.
- **Anti-Replay:** Once a code is used, it cannot be used again.

---

## 🗺️ What a Finished Waypoint Itinerary Looks Like

When Waypoint finishes generating a trip, the traveler receives a complete dossier containing:

| Section | What the Traveler Sees | Why It Matters |
|---|---|---|
| **Trip Header** | Catchy trip title, inspiring summary, and 5 curated landscape photos of the destination. | Gives the traveler an immediate visual feel for the city. |
| **Budget Breakdown** | Itemized costs for flights, hotels, dining, and activities in the chosen currency (USD, EUR, INR, etc.). | Prevents budget surprises before booking. |
| **Flight Options** | 2–3 active airlines, flight routes, duration, stops, and a direct Google Flights search button. | Only operating airlines are shown; no dead links. |
| **Hotel Picks** | 2–3 vetted hotels matching budget, with neighborhood vibes, star ratings, and Google Hotels links. | Traveler can choose their preferred neighborhood and book directly. |
| **Day-by-Day Plan** | Morning, afternoon, and evening activities with landmark photos and direct Google Maps links. | Logically sequenced stops so travelers don't spend all day stuck in transit. |
| **Food & Dining** | Curated local restaurants for each day, highlighting signature dishes and matching dietary preferences. | Ensures travelers eat authentic local food without getting trapped in tourist traps. |

---

## 📊 Current State of the Application (System Health)

As of **November 2026**, the backend system is in **clean, production-ready health**:

### 1. Automated Test Suite: 100% Passing
The entire system is continuously verified by **42 automated tests**. Every single test passes:

- **19 Authentication Tests:** Registration, login, password checks, magic OTP email generation, expiration, rate limiting, and brute-force protection.
- **23 Trip & AI Engine Tests:** System health checks, Groq AI generation, Gemini AI fallback, day-count validation, guest trips, member trip history, and email delivery.

```text
Found 42 test(s).
System check identified no issues (0 silenced).
..........................................
----------------------------------------------------------------------
Ran 42 tests in 2.943s

OK
```

### 2. Architecture: Zero Spaghetti Code
The codebase strictly separates concerns into clean compartments:
- **Views:** Only handle web traffic and incoming requests.
- **Services:** Contain all the smart business logic (AI communication, emailing, calculations).
- **Selectors:** Handle reading from the database safely.
- **Schemas:** Guarantee that the AI always speaks standard, error-free data formats.

### 3. Error Handling: No Ugly Crashes
If an external service (like an AI provider or mail server) is temporarily down, Waypoint doesn't show an ugly crash screen. Instead, it catches the error, logs what happened for developers, and returns a clean, friendly notification to the user.

---

## 🚀 Key Files & What They Do

If you open the project folder, here is what each important file does:

| Folder / File | What It Does in Plain English |
|---|---|
| `trips/services.py` | **The Brain:** Talks to Groq and Gemini AI, validates the day counts, and formats travel emails. |
| `trips/schemas.py` | **The Blueprint:** Defines what a valid trip looks like (flights, hotels, days, activities, budget). |
| `trips/models.py` | **The Travel Diary:** Stores every saved trip in the PostgreSQL database. |
| `accounts/services.py` | **The Security Guard:** Generates 6-digit magic codes, logs users in, and issues security tokens. |
| `accounts/models.py` | **The User Registry:** Stores user accounts and active login codes securely. |
| `config/settings/base.py` | **The Master Control Panel:** Manages API keys, database settings, and email configurations. |
| `manage.py` | **The Remote Control:** The command-line tool used to run tests, start the server, and update the database. |

---

## 🔮 What's Next? (Future Possibilities)

The foundation of Waypoint is solid and modular. Here are natural features that can be added in future versions:
1. **Multi-City Trips:** Planning complex routes (e.g. London -> Paris -> Rome over 10 days).
2. **Downloadable PDF Roadmaps:** Generating beautifully styled, printable PDF travel booklets.
3. **Live Currency Exchange:** Converting estimated budgets into real-time local currencies.
4. **Calendar Sync:** Adding planned activities directly to Google Calendar or Apple Calendar.

---

*Document prepared for the Waypoint team. This document explains the full architecture, design decisions, and live operational state in accessible terms for all stakeholders.*
