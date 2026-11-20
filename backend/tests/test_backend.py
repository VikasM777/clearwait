import pytest
from datetime import date, datetime, timedelta
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.main import app
from app.db.session import Base, get_db
from app.models.models import User, Machine, BlockedHour, UsageRecord, Booking, UserRole, MachineStatus, BookingStatus
from app.core.security import get_password_hash
from app.services.analytics import run_kmeans

# Use an in-memory SQLite database with StaticPool so all connections share the same memory DB
SQLALCHEMY_DATABASE_URL = "sqlite:///:memory:"
test_engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)

@pytest.fixture(scope="function")
def db_session():
    Base.metadata.create_all(bind=test_engine)
    session = TestingSessionLocal()
    try:
        # Seed test admin & test resident
        admin = User(
            name="Admin User",
            email="admin@test.com",
            hashed_password=get_password_hash("adminpass123"),
            role=UserRole.ADMIN
        )
        resident = User(
            name="Resident User",
            email="resident@test.com",
            hashed_password=get_password_hash("residentpass123"),
            role=UserRole.RESIDENT
        )
        resident2 = User(
            name="Second Resident",
            email="resident2@test.com",
            hashed_password=get_password_hash("residentpass123"),
            role=UserRole.RESIDENT
        )
        session.add_all([admin, resident, resident2])

        # Seed machines
        m1 = Machine(id="M1", name="Machine 1", status=MachineStatus.AVAILABLE)
        m2 = Machine(id="M2", name="Machine 2", status=MachineStatus.AVAILABLE)
        m3 = Machine(id="M3", name="Machine 3", status=MachineStatus.MAINTENANCE)
        session.add_all([m1, m2, m3])

        session.commit()
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=test_engine)

@pytest.fixture(scope="function")
def client(db_session):
    def override_get_db():
        session = TestingSessionLocal()
        try:
            yield session
        finally:
            session.close()

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()

def get_auth_token(client, email, password):
    res = client.post("/api/auth/login", json={"email": email, "password": password})
    assert res.status_code == 200, f"Login failed: {res.text}"
    return res.json()["access_token"]


# =====================================================================
# 1. AUTHENTICATION & ACCESS CONTROL TESTS
# =====================================================================

def test_register_and_login(client):
    reg_res = client.post("/api/auth/register", json={
        "name": "New Person",
        "email": "new@test.com",
        "password": "secretpassword"
    })
    assert reg_res.status_code == 201
    assert "access_token" in reg_res.json()
    assert reg_res.json()["user"]["email"] == "new@test.com"

    # Duplicate registration rejection
    dup_res = client.post("/api/auth/register", json={
        "name": "New Person",
        "email": "new@test.com",
        "password": "secretpassword"
    })
    assert dup_res.status_code == 400

    # Login
    login_res = client.post("/api/auth/login", json={
        "email": "new@test.com",
        "password": "secretpassword"
    })
    assert login_res.status_code == 200
    token = login_res.json()["access_token"]

    # Current user /me
    me_res = client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert me_res.status_code == 200
    assert me_res.json()["email"] == "new@test.com"

def test_admin_route_protection(client):
    res_token = get_auth_token(client, "resident@test.com", "residentpass123")
    adm_token = get_auth_token(client, "admin@test.com", "adminpass123")

    # Resident trying to add machine -> 403 Forbidden
    res = client.post("/api/machines", json={"name": "Machine X"}, headers={"Authorization": f"Bearer {res_token}"})
    assert res.status_code == 403

    # Admin adding machine -> 201 Created
    res_adm = client.post("/api/machines", json={"name": "Machine X"}, headers={"Authorization": f"Bearer {adm_token}"})
    assert res_adm.status_code == 201


# =====================================================================
# 2. BOOKING CONFLICT & VALIDATION TESTS
# =====================================================================

def test_booking_in_past_rejected(client):
    token = get_auth_token(client, "resident@test.com", "residentpass123")
    yesterday = (date.today() - timedelta(days=1)).isoformat()
    res = client.post("/api/bookings", json={
        "date": yesterday,
        "hour": 10,
        "machine_id": "M1"
    }, headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 400
    assert "past" in res.json()["detail"].lower()

def test_booking_maintenance_machine_rejected(client):
    token = get_auth_token(client, "resident@test.com", "residentpass123")
    tomorrow = (date.today() + timedelta(days=1)).isoformat()
    # M3 is in MAINTENANCE
    res = client.post("/api/bookings", json={
        "date": tomorrow,
        "hour": 10,
        "machine_id": "M3"
    }, headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 400
    assert "no longer available" in res.json()["detail"].lower()

def test_booking_blocked_hour_rejected(client, db_session):
    adm_token = get_auth_token(client, "admin@test.com", "adminpass123")
    res_token = get_auth_token(client, "resident@test.com", "residentpass123")
    tomorrow = (date.today() + timedelta(days=1)).isoformat()

    # Admin blocks hour 14
    block_res = client.post("/api/slots/toggle", json={"hour": 14}, headers={"Authorization": f"Bearer {adm_token}"})
    assert block_res.status_code == 200
    assert 14 in block_res.json()

    # Resident attempts booking for hour 14
    res = client.post("/api/bookings", json={
        "date": tomorrow,
        "hour": 14,
        "machine_id": "M1"
    }, headers={"Authorization": f"Bearer {res_token}"})
    assert res.status_code == 400
    assert "blocked" in res.json()["detail"].lower()

def test_double_booking_conflict(client):
    res_token1 = get_auth_token(client, "resident@test.com", "residentpass123")
    res_token2 = get_auth_token(client, "resident2@test.com", "residentpass123")
    tomorrow = (date.today() + timedelta(days=1)).isoformat()

    # User 1 books M1 at hour 10
    b1 = client.post("/api/bookings", json={
        "date": tomorrow,
        "hour": 10,
        "machine_id": "M1"
    }, headers={"Authorization": f"Bearer {res_token1}"})
    assert b1.status_code == 201

    # User 2 tries to book the same M1 at hour 10 -> Conflict / rejected
    b2 = client.post("/api/bookings", json={
        "date": tomorrow,
        "hour": 10,
        "machine_id": "M1"
    }, headers={"Authorization": f"Bearer {res_token2}"})
    assert b2.status_code == 400
    assert "no longer available" in b2.json()["detail"].lower()

    # User 1 tries to book another machine (M2) at the same time -> One booking per user per slot rule
    b3 = client.post("/api/bookings", json={
        "date": tomorrow,
        "hour": 10,
        "machine_id": "M2"
    }, headers={"Authorization": f"Bearer {res_token1}"})
    assert b3.status_code == 400
    assert "already have a booking" in b3.json()["detail"].lower()

def test_any_machine_auto_assignment(client):
    res_token1 = get_auth_token(client, "resident@test.com", "residentpass123")
    res_token2 = get_auth_token(client, "resident2@test.com", "residentpass123")
    tomorrow = (date.today() + timedelta(days=1)).isoformat()

    # User 1 requests 'any' machine at hour 11
    b1 = client.post("/api/bookings", json={
        "date": tomorrow,
        "hour": 11,
        "machine_id": "any"
    }, headers={"Authorization": f"Bearer {res_token1}"})
    assert b1.status_code == 201
    assigned_m1 = b1.json()["machine_id"]
    assert assigned_m1 in ["M1", "M2"]

    # User 2 requests 'any' machine at the same hour 11 -> gets the remaining machine
    b2 = client.post("/api/bookings", json={
        "date": tomorrow,
        "hour": 11,
        "machine_id": "any"
    }, headers={"Authorization": f"Bearer {res_token2}"})
    assert b2.status_code == 201
    assigned_m2 = b2.json()["machine_id"]
    assert assigned_m2 in ["M1", "M2"]
    assert assigned_m1 != assigned_m2

def test_booking_cancel(client):
    res_token = get_auth_token(client, "resident@test.com", "residentpass123")
    tomorrow = (date.today() + timedelta(days=1)).isoformat()

    b = client.post("/api/bookings", json={
        "date": tomorrow,
        "hour": 12,
        "machine_id": "M1"
    }, headers={"Authorization": f"Bearer {res_token}"}).json()

    cancel_res = client.patch(f"/api/bookings/{b['id']}/cancel", headers={"Authorization": f"Bearer {res_token}"})
    assert cancel_res.status_code == 200
    assert cancel_res.json()["status"] == "cancelled"


# =====================================================================
# 3. K-MEANS CLUSTERING & ORDERED CENTROID LABELS TEST
# =====================================================================

def test_kmeans_centroid_ordering_and_labels(db_session):
    today = date.today()
    records = []
    # Hour 7: very high usage
    for i in range(14):
        d = today - timedelta(days=i)
        for m in ["M1", "M2", "M3"]:
            records.append(UsageRecord(date=d, hour=7, machine_id=m))
    # Hour 14: very low usage (only 1 record across all 14 days)
    records.append(UsageRecord(date=today, hour=14, machine_id="M1"))

    db_session.bulk_save_objects(records)
    db_session.commit()

    km = run_kmeans(db_session, k=3, machine_id="all")
    cents = km["cents"]
    assert len(cents) > 0
    # Verify centroids are strictly sorted by average usage
    for i in range(len(cents) - 1):
        assert cents[i]["avg"] <= cents[i+1]["avg"]

    # Verify labels correspond to sorted order (Low < Medium < High)
    assert cents[0]["name"] == "Low"
    assert cents[-1]["name"] == "High"
    assert cents[0]["color"] == "#16a34a" # green
    assert cents[-1]["color"] == "#dc2626" # red


# =====================================================================
# 4. CSV BULK UPLOAD TEST
# =====================================================================

def test_csv_upload_and_validation(client):
    adm_token = get_auth_token(client, "admin@test.com", "adminpass123")
    csv_content = """date,hour,machine
2026-11-01,8,M1
2026-11-01,8,M2
2026-11-01,9,Machine 1
2026-11-01,25,M1
invalid-row
"""
    files = {"file": ("test.csv", csv_content.encode("utf-8"), "text/csv")}
    res = client.post("/api/records/upload-csv", files=files, headers={"Authorization": f"Bearer {adm_token}"})
    assert res.status_code == 200
    # Exactly 3 valid rows imported, 2 invalid ignored
    assert res.json()["imported_count"] == 3
