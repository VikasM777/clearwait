import random
from datetime import datetime, date, timedelta
from app.db.session import SessionLocal, engine, Base
from app.models.models import User, Machine, BlockedHour, UsageRecord, Booking, UserRole, MachineStatus, BookingStatus
from app.core.security import get_password_hash

HRS = list(range(6, 23)) # 6 to 22

def seed_database():
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        print("🌱 Seeding database...")

        # 1. Users
        admin_email = "admin@smartlaundry.com"
        demo_email = "demo@smartlaundry.com"

        admin = db.query(User).filter(User.email == admin_email).first()
        if not admin:
            admin = User(
                name="Administrator",
                email=admin_email,
                hashed_password=get_password_hash("admin123"),
                role=UserRole.ADMIN
            )
            db.add(admin)
            print(f"Created admin: {admin_email}")

        demo = db.query(User).filter(User.email == demo_email).first()
        if not demo:
            demo = User(
                name="Demo Resident",
                email=demo_email,
                hashed_password=get_password_hash("demo123"),
                role=UserRole.RESIDENT
            )
            db.add(demo)
            print(f"Created demo resident: {demo_email}")

        db.commit()

        # 2. Machines
        existing_machines = {m.id for m in db.query(Machine).all()}
        for i in range(1, 7):
            m_id = f"M{i}"
            if m_id not in existing_machines:
                m = Machine(
                    id=m_id,
                    name=f"Machine {i}",
                    status=MachineStatus.AVAILABLE
                )
                db.add(m)
                print(f"Created machine: {m_id}")
        db.commit()

        # 3. Usage Records (28 days of realistic usage data)
        # Weekday peaks around 7–9 (indices 1..3 in HRS) and 19–21 (indices 13..15 in HRS)
        # Weekend peak 10–14 (indices 4..8 in HRS)
        record_count = db.query(UsageRecord).count()
        if record_count == 0:
            print("Generating 28 days of realistic sample usage records...")
            # Probabilities per hour (6..22)
            # HRS = [6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22]
            wd_curve = [1.0, 4.0, 5.0, 3.5, 2.0, 1.5, 1.5, 1.5, 1.5, 1.0, 1.5, 2.0, 3.5, 5.0, 5.0, 3.0, 1.5]
            we_curve = [0.5, 1.0, 2.0, 3.0, 4.5, 5.0, 5.0, 4.5, 4.0, 3.0, 2.5, 2.0, 2.5, 3.0, 3.0, 2.0, 1.0]

            random.seed(42)
            machine_ids = [f"M{i}" for i in range(1, 7)]
            records = []
            today = date.today()

            for days_back in range(28, 0, -1):
                cur_date = today - timedelta(days=days_back)
                # Sunday=0, Saturday=6 in JS; Python weekday(): Mon=0..Sun=6
                is_weekend = (cur_date.weekday() in (5, 6))
                curve = we_curve if is_weekend else wd_curve

                for h_idx, hour in enumerate(HRS):
                    base_expected = curve[h_idx]
                    noise = (random.random() - 0.5) * 2.0
                    n_machines = max(0, min(6, round(base_expected + noise)))
                    if n_machines > 0:
                        chosen_machines = random.sample(machine_ids, n_machines)
                        for m_id in chosen_machines:
                            records.append(UsageRecord(
                                date=cur_date,
                                hour=hour,
                                machine_id=m_id
                            ))

            db.bulk_save_objects(records)
            db.commit()
            print(f"Inserted {len(records)} realistic usage records.")

        # 4. Sample Bookings
        booking_count = db.query(Booking).count()
        if booking_count == 0:
            demo_user = db.query(User).filter(User.email == demo_email).first()
            if demo_user:
                tomorrow = date.today() + timedelta(days=1)
                sample_bookings = [
                    (8, "M1"),
                    (8, "M2"),
                    (19, "M1"),
                    (19, "M3"),
                ]
                for h, m_id in sample_bookings:
                    b = Booking(
                        user_id=demo_user.id,
                        machine_id=m_id,
                        date=tomorrow,
                        hour=h,
                        status=BookingStatus.CONFIRMED,
                        created_at=datetime.utcnow()
                    )
                    db.add(b)
                db.commit()
                print("Inserted sample bookings for tomorrow.")

        print("✅ Database seeding complete.")
    finally:
        db.close()

if __name__ == "__main__":
    seed_database()
