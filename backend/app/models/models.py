from sqlalchemy import Column, Integer, String, Text, Float, DateTime
from datetime import datetime
from app.db.session import Base

class Appointment(Base):
    __tablename__ = "appointments"

    id = Column(String(50), primary_key=True, index=True)
    name = Column(String(150), nullable=False)
    phone = Column(String(50), nullable=True)
    date = Column(String(20), nullable=False) # YYYY-MM-DD
    time = Column(String(20), nullable=False) # HH:MM
    status = Column(String(30), default="booked", nullable=False) # booked, cancelled, noshow, arrived
    remindedAt = Column(Float, nullable=True) # unix ms timestamp
    rescheduled = Column(Integer, default=0, nullable=False)
    created = Column(Float, default=lambda: datetime.utcnow().timestamp() * 1000)

class Patient(Base):
    __tablename__ = "patients"

    id = Column(String(50), primary_key=True, index=True)
    name = Column(String(150), nullable=False)
    code = Column(String(10), index=True, nullable=False) # 4 digit code
    status = Column(String(30), default="waiting", nullable=False) # waiting, in, done
    startedAt = Column(Float, nullable=True)
    doneAt = Column(Float, nullable=True)
    created = Column(Float, default=lambda: datetime.utcnow().timestamp() * 1000)

class Record(Base):
    __tablename__ = "records"

    id = Column(String(50), primary_key=True, index=True)
    name = Column(String(150), nullable=False)
    phone = Column(String(50), nullable=True)
    age = Column(String(20), nullable=True)
    allergies = Column(Text, nullable=True)
    history = Column(Text, nullable=True)
    created = Column(Float, default=lambda: datetime.utcnow().timestamp() * 1000)

class Prescription(Base):
    __tablename__ = "prescriptions"

    id = Column(String(50), primary_key=True, index=True)
    patient = Column(String(50), nullable=False, index=True) # refers to Record.id
    doctor = Column(String(150), nullable=True)
    meds = Column(Text, nullable=False)
    advice = Column(Text, nullable=True)
    created = Column(Float, default=lambda: datetime.utcnow().timestamp() * 1000)
