import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.main import app
from app.db.session import Base, get_db
from app.models.models import Appointment, Patient, Record, Prescription

SQLALCHEMY_DATABASE_URL = "sqlite:///:memory:"
test_engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)

@pytest.fixture(scope="function")
def client():
    Base.metadata.create_all(bind=test_engine)
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
    Base.metadata.drop_all(bind=test_engine)

def test_health_check(client):
    r = client.get("/")
    assert r.status_code == 200
    assert r.json()["status"] == "online"

def test_appointments_crud(client):
    # Create
    r = client.post("/api/appts", json={
        "name": "Priya Sharma",
        "phone": "+919999988888",
        "date": "2026-11-25",
        "time": "11:00",
        "status": "booked"
    })
    assert r.status_code == 200
    item = r.json()
    assert item["name"] == "Priya Sharma"
    item_id = item["id"]

    # Update / Reschedule
    r_upd = client.patch(f"/api/appts/{item_id}", json={
        "time": "12:00",
        "status": "arrived"
    })
    assert r_upd.status_code == 200
    assert r_upd.json()["time"] == "12:00"
    assert r_upd.json()["status"] == "arrived"

    # List
    r_list = client.get("/api/appts")
    assert r_list.status_code == 200
    assert len(r_list.json()) == 1

    # Delete
    r_del = client.delete(f"/api/appts/{item_id}")
    assert r_del.status_code == 200

def test_patients_queue_crud(client):
    r = client.post("/api/patients", json={
        "name": "Aakash Patel",
        "code": "4921",
        "status": "waiting"
    })
    assert r.status_code == 200
    pid = r.json()["id"]

    # Call in
    r_call = client.patch(f"/api/patients/{pid}", json={"status": "in"})
    assert r_call.status_code == 200
    assert r_call.json()["status"] == "in"

def test_records_and_rx_crud(client):
    # Add record
    r_rec = client.post("/api/records", json={
        "name": "Amit Shah",
        "phone": "9820011223",
        "age": "32",
        "allergies": "None",
        "history": "Hypertension"
    })
    assert r_rec.status_code == 200
    rid = r_rec.json()["id"]

    # Add prescription
    r_rx = client.post("/api/rx", json={
        "patient": rid,
        "doctor": "Dr. Anjali Rao",
        "meds": "Amlodipine 5mg OD x 30 days",
        "advice": "Low salt diet"
    })
    assert r_rx.status_code == 200
    assert r_rx.json()["patient"] == rid
