# QuietHours Backend API

Production-ready backend for **QuietHours** – Smart Scheduling and Usage Analysis for shared washing machines in hostels, PGs, and apartments.

Powered by:
- **FastAPI** with async ASGI speed and automatic OpenAPI documentation
- **SQLAlchemy 2.0** ORM supporting SQLite (local development) and PostgreSQL (production)
- **Alembic** database migrations
- **scikit-learn** K-Means clustering with feature standardization (`StandardScaler`) and sorted centroid labelling
- **Pydantic v2** validation with strict type checking
- **Bcrypt & JWT** authentication with role-based access control (Resident & Admin)
- **SlowAPI** rate limiting on authentication routes

---

## 📁 Project Architecture

```
backend/
├── alembic/              # Alembic migration scripts and versions
│   └── versions/         # Migration versions
├── alembic.ini           # Alembic configuration
├── app/
│   ├── api/
│   │   ├── deps.py       # Current user, Admin role dependencies, OAuth2 bearer
│   │   └── endpoints/
│   │       ├── auth.py       # Register, Login, Current User (/me), Logout
│   │       ├── machines.py   # Machine management (CRUD, status)
│   │       ├── slots.py      # Blocked hours management
│   │       ├── records.py    # Usage records, CSV bulk upload, filter & list
│   │       ├── bookings.py   # Atomic bookings, slot conflict check, auto-assign
│   │       └── analytics.py  # Dashboard stats, K-Means clustering, recommendations
│   ├── core/
│   │   ├── config.py     # Pydantic BaseSettings, database & CORS configuration
│   │   └── security.py   # Bcrypt password hashing & JWT token issuance
│   ├── db/
│   │   └── session.py    # SQLAlchemy database engine and session factory
│   ├── models/
│   │   └── models.py     # SQLAlchemy models (User, Machine, BlockedHour, UsageRecord, Booking)
│   ├── schemas/
│   │   └── schemas.py    # Pydantic schemas for requests and responses
│   ├── services/
│   │   └── analytics.py  # Real scikit-learn KMeans & statistical calculations
│   └── main.py           # FastAPI app entry point, CORS middleware, rate limiters
├── tests/
│   └── test_backend.py   # Pytest suite (auth, bookings, race conditions, K-Means, CSV)
├── requirements.txt      # Production Python dependencies
├── Dockerfile            # Container build for Railway, Render, Fly.io, etc.
├── render.yaml           # One-click Render Blueprint definition
├── seed.py               # Generates 28 days of realistic usage data & demo users
└── .env.example          # Environment variables template
```

---

## 🚀 Local Development Setup

### 1. Prerequisites
- Python 3.10+ (tested on Python 3.12)
- Git

### 2. Clone and Setup Environment
```bash
git clone https://github.com/VikasM777/QuietHours.git
cd QuietHours/backend

# Create virtual environment
python -m venv venv

# Activate virtual environment
# Windows:
.\venv\Scripts\activate
# Linux/macOS:
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

### 3. Environment Configuration
Copy `.env.example` to `.env`:
```bash
cp .env.example .env
```
Default `.env`:
```env
PROJECT_NAME="QuietHours API"
ENVIRONMENT=development
SECRET_KEY=super-secret-key-min-32-characters-for-jwt-signing
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=1440
DATABASE_URL=sqlite:///./quiethours.db
CORS_ORIGINS=https://vikasm777.github.io,http://localhost:3000,http://localhost:8000,http://127.0.0.1:5500
```

### 4. Run Migrations & Seed Sample Data
```bash
# Seed initial demo users, machines, and 28 days of realistic wash cycle usage
python seed.py
```
This generates:
- **Admin**: `admin@smartlaundry.com` / `admin123`
- **Demo Resident**: `demo@smartlaundry.com` / `demo123`
- 6 Machines (`M1` to `M6`)
- 28 days of realistic wash cycles (weekday morning/evening peaks, weekend afternoon peaks)
- Sample upcoming bookings

### 5. Start the Server
```bash
uvicorn app.main:app --reload --port 8000
```
Open **Interactive API Docs (Swagger UI)**: [http://localhost:8000/docs](http://localhost:8000/docs)  
Alternative Redoc: [http://localhost:8000/redoc](http://localhost:8000/redoc)

---

## 🧪 Running Automated Tests

Run the test suite verifying authentication, booking conflicts, past booking blocks, auto-machine assignment, K-Means centroid ordering, and CSV upload:

```bash
python -m pytest tests/test_backend.py -v
```
All 10 tests run in an isolated in-memory SQLite database.

---

## 🌐 Production Deployment Guide

You can deploy the backend to **Render** or **Railway** for free.

### Option A: Deploy on Render

1. **Push your code to GitHub** (make sure your repo has the `backend/` folder or is dedicated).
2. Go to [Render Dashboard](https://dashboard.render.com/) and click **New +** -> **Blueprint** (or **Web Service**).
3. If using **Blueprint**, connect your GitHub repo. Render will automatically read `backend/render.yaml` and provision:
   - A PostgreSQL database (`quiethours-db`)
   - A Python Web Service with auto-generated `SECRET_KEY` and connected `DATABASE_URL`.
4. If setting up manually as a **Web Service**:
   - **Environment**: `Python 3`
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: `python seed.py && uvicorn app.main:app --host 0.0.0.0 --port $PORT`
   - **Environment Variables**:
     - `SECRET_KEY`: `<Generate a random 32-character string>`
     - `DATABASE_URL`: `<Your PostgreSQL connection string or internal SQLite>`
     - `CORS_ORIGINS`: `https://vikasm777.github.io,http://localhost:3000`
5. Note your live backend URL (e.g. `https://quiethours-backend.onrender.com`).

### Option B: Deploy on Railway

1. Go to [Railway.app](https://railway.app/) and create a **New Project**.
2. Select **Deploy from GitHub repo**.
3. Add a **PostgreSQL** database service in the same project.
4. Set the backend service environment variables:
   - `DATABASE_URL`: `${{Postgres.DATABASE_URL}}`
   - `SECRET_KEY`: `<Your 32+ character secret string>`
   - `CORS_ORIGINS`: `https://vikasm777.github.io`
5. Railway will detect the `Dockerfile` and deploy automatically.

---

## 🔗 Connecting Frontend to the Live Backend

1. In `index.html`, set the `API_URL` configuration constant:
   ```javascript
   const API_BASE = "https://your-backend-app.onrender.com/api";
   ```
2. Commit and push `index.html` to your GitHub repo's `main` branch.
3. GitHub Pages will build and deploy your frontend automatically at `https://vikasm777.github.io/QuietHours/`.
