import time
from app.db.session import SessionLocal, engine, Base
from app.models.models import Appointment, Patient, Record, Prescription

def seed_database():
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        now_ms = time.time() * 1000

        # Seed sample appointments if empty
        if db.query(Appointment).count() == 0:
            a1 = Appointment(
                id="a_101",
                name="Ravi Kumar",
                phone="+919876543210",
                date="2026-11-21",
                time="10:30",
                status="booked",
                created=now_ms
            )
            a2 = Appointment(
                id="a_102",
                name="Sunita Sharma",
                phone="+919876543211",
                date="2026-11-21",
                time="11:15",
                status="booked",
                created=now_ms
            )
            db.add_all([a1, a2])

        # Seed sample queue patients if empty
        if db.query(Patient).count() == 0:
            p1 = Patient(
                id="p_101",
                name="Deepak Verma",
                code="1245",
                status="in",
                startedAt=now_ms - 300000,
                created=now_ms - 900000
            )
            p2 = Patient(
                id="p_102",
                name="Ananya Roy",
                code="3892",
                status="waiting",
                created=now_ms - 600000
            )
            p3 = Patient(
                id="p_103",
                name="Kavita Mehta",
                code="7421",
                status="waiting",
                created=now_ms - 300000
            )
            db.add_all([p1, p2, p3])

        # Seed sample records if empty
        if db.query(Record).count() == 0:
            r1 = Record(
                id="r_101",
                name="Ravi Kumar",
                phone="+919876543210",
                age="45",
                allergies="Penicillin",
                history="Diabetic type 2 since 2015. On Metformin 500mg BD.",
                created=now_ms
            )
            db.add(r1)

        db.commit()
        print("Clearwait database seeded successfully.")
    finally:
        db.close()

if __name__ == "__main__":
    seed_database()
