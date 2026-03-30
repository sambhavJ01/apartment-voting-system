# Apartment Voting System

A **secure, scalable apartment society voting system** built with FastAPI + Streamlit, featuring WhatsApp OTP verification, anonymous & identified voting modes, and full audit trails.

---

## Architecture

```
voting-system/
├── backend/                 ← FastAPI backend (port 8000)
│   ├── models/              ← SQLAlchemy ORM models
│   ├── schemas/             ← Pydantic request/response schemas
│   ├── services/            ← Business logic (auth, OTP, voting, reporting)
│   │   └── otp_provider.py  ← Pluggable WhatsApp OTP (console/Twilio/Gupshup/Meta)
│   ├── routes/              ← FastAPI route handlers
│   ├── config.py            ← Settings (pydantic-settings, .env-based)
│   ├── database.py          ← SQLAlchemy engine + WAL mode + session
│   └── main.py              ← FastAPI app entry point
├── ui/                      ← Streamlit frontend (port 8501)
│   ├── app.py               ← Main app + page routing (session-state)
│   ├── pages/               ← register, login, vote, admin_panel, reports
│   └── utils/               ← api_client.py, components.py
├── scripts/
│   ├── init_db.py           ← Create tables
│   └── seed_data.py         ← Sample data + demo credentials
├── Dockerfile.backend
├── Dockerfile.frontend
├── docker-compose.yml
└── requirements.txt
```

---

## Quick Start (Local)

### 1. Install dependencies

```bash
cd voting-system
python -m venv .venv

# Windows
.venv\Scripts\activate
# Mac/Linux
source .venv/bin/activate

pip install -r requirements.txt
```

### 2. Configure environment

```bash
copy .env.example .env   # Windows
# or
cp .env.example .env     # Mac/Linux
```

Edit `.env` and at minimum set:
```
SECRET_KEY=<random 64-char hex>
OTP_SECRET_SALT=<random 32-char hex>
ANON_VOTE_SALT=<random 32-char hex>
ADMIN_REGISTRATION_KEY=<your admin key>
OTP_PROVIDER=console     # for development (prints OTP to terminal)
```

> Generate secure keys: `python -c "import secrets; print(secrets.token_hex(32))"`

### 3. Seed database

```bash
python -m scripts.seed_data
```

This creates tables and inserts sample apartments, voters, and topics.

**Demo credentials** (printed after seeding):
| Role  | Phone          | Password   |
|-------|----------------|------------|
| Admin | +919000000000  | Admin@1234 |
| Voter | +919000000001  | Test@1234  |
| Voter | +919000000002  | Test@1234  |

### 4. Start the backend

```bash
uvicorn backend.main:app --reload --port 8000
```

API docs available at: http://localhost:8000/docs

### 5. Start the frontend (new terminal)

```bash
streamlit run ui/app.py
```

Opens at: http://localhost:8501

---

## Docker Deployment

```bash
# Copy and edit env file
cp .env.example .env

# Build & start both services
docker compose up --build

# Frontend: http://localhost:8501
# Backend API: http://localhost:8000
# Swagger docs: http://localhost:8000/docs
```

---

## WhatsApp OTP Providers

Switch providers by setting `OTP_PROVIDER` in `.env`:

| Value     | Description                    | Required env vars                                             |
|-----------|--------------------------------|---------------------------------------------------------------|
| `console` | Prints OTP to server stdout    | None (dev only)                                               |
| `twilio`  | Twilio WhatsApp Sandbox/API    | `TWILIO_ACCOUNT_SID`, `TWILIO_AUTH_TOKEN`, `TWILIO_WHATSAPP_FROM` |
| `gupshup` | Gupshup WhatsApp API           | `GUPSHUP_API_KEY`, `GUPSHUP_APP_NAME`, `GUPSHUP_SRC_NAME`    |
| `meta`    | Meta WhatsApp Cloud API        | `META_PHONE_NUMBER_ID`, `META_ACCESS_TOKEN`                   |

To add a new provider: subclass `OTPProvider` in `backend/services/otp_provider.py` and add a branch in `get_otp_provider()`. No other code changes needed.

---

## User Registration Flow

```
User fills form → OTP sent to WhatsApp
       ↓
User enters OTP → Phone verified
       ↓
Status: PENDING_APPROVAL
       ↓
Admin approves → Password auto-generated & shown to admin
       ↓
Admin shares password → User can login
```

---

## Voting Flow

```
Login → Select active topic → Choose option
       ↓
WhatsApp OTP sent to user
       ↓
User enters OTP → Vote recorded atomically
       ↓
Results shown for 60 s → Hidden (anonymous mode)
```

---

## Admin Features

| Feature               | Details                                          |
|-----------------------|--------------------------------------------------|
| User approval         | Review pending registrations, approve/reject     |
| Password generation   | Auto-generated secure password on approval       |
| User enable/disable   | Revoke access without deleting data              |
| Apartment management  | Set per-apartment voter limits                   |
| Topic creation        | Anonymous or Identified mode, time windows       |
| Topic status control  | Draft → Active → Closed → Disabled              |
| Dashboard             | Eligibility, participation, active topic count   |
| Reports               | CSV + Excel export per topic                     |
| Audit log             | Full immutable audit trail                       |

---

## Security Design

| Concern                   | Implementation                                           |
|---------------------------|----------------------------------------------------------|
| Passwords                 | bcrypt (passlib), minimum 8 chars                        |
| OTP storage               | HMAC-SHA256 hash only — raw OTP never stored             |
| OTP timing attack         | `hmac.compare_digest()` for constant-time comparison     |
| OTP brute force           | Max 3 attempts then invalidated                          |
| OTP flooding              | Rate limit: 1 OTP per 60 s per phone+purpose             |
| JWT tokens                | HS256, 60-min expiry                                     |
| Anonymous vote identity   | HMAC-SHA256(user_id:topic_id, ANON_SALT) — not reversible|
| Double-vote prevention    | DB UNIQUE constraint on vote_tracking enforced atomically |
| SQL injection             | SQLAlchemy ORM with parameterised queries only           |
| SQLite concurrency        | WAL mode + 5 s busy_timeout                              |

---

## Database Migration (SQLite → PostgreSQL)

1. Update `.env`: `DATABASE_URL=postgresql://user:pass@host:5432/voting_db`
2. Install driver: `pip install psycopg2-binary`
3. Re-run: `python -m scripts.init_db`

No model or service code changes needed — SQLAlchemy abstracts the dialect.

---

## API Reference

Interactive docs: **http://localhost:8000/docs**

| Method | Path                                 | Auth     | Description                 |
|--------|--------------------------------------|----------|-----------------------------|
| POST   | /auth/register                       | —        | Register new voter          |
| POST   | /auth/register/verify-otp            | —        | Verify registration OTP     |
| POST   | /auth/resend-otp                     | —        | Resend OTP                  |
| POST   | /auth/login                          | —        | Login, get JWT              |
| GET    | /vote/topics                         | User     | List active topics          |
| POST   | /vote/initiate                       | User     | Send vote-confirmation OTP  |
| POST   | /vote/cast                           | User     | Submit vote with OTP        |
| GET    | /vote/topics/{id}/results            | User     | View results                |
| GET    | /admin/dashboard                     | Admin    | Dashboard stats             |
| GET    | /admin/users/pending                 | Admin    | Pending approvals           |
| POST   | /admin/users/approve                 | Admin    | Approve user                |
| POST   | /admin/users/reject                  | Admin    | Reject user                 |
| POST   | /admin/topics                        | Admin    | Create topic                |
| PUT    | /admin/topics/{id}/status            | Admin    | Update topic status         |
| GET    | /reports/topics/{id}/export/csv      | Admin    | CSV export                  |
| GET    | /reports/topics/{id}/export/excel    | Admin    | Excel export                |
| GET    | /reports/audit-logs                  | Admin    | Audit log                   |
| POST   | /admin/bootstrap                     | Key      | First-time admin creation   |


## Screenshots

<img width="1920" height="911" alt="image" src="https://github.com/user-attachments/assets/28ba9787-16d2-4fa9-8ca4-7c9efd3d7eb3" />

<img width="1551" height="704" alt="image" src="https://github.com/user-attachments/assets/2dd9db50-757e-44e7-8a84-666f34811a7e" />

