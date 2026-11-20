from datetime import datetime, date
import enum
from sqlalchemy import (
    Column, Integer, String, Enum, ForeignKey, Date, DateTime, UniqueConstraint, Index
)
from sqlalchemy.orm import relationship
from app.db.session import Base

class UserRole(str, enum.Enum):
    RESIDENT = "resident"
    ADMIN = "admin"

class MachineStatus(str, enum.Enum):
    AVAILABLE = "available"
    OCCUPIED = "occupied"
    MAINTENANCE = "maintenance"

class BookingStatus(str, enum.Enum):
    CONFIRMED = "confirmed"
    CANCELLED = "cancelled"

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False)
    email = Column(String(255), unique=True, index=True, nullable=False)
    hashed_password = Column(String(255), nullable=False)
    role = Column(Enum(UserRole), default=UserRole.RESIDENT, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    bookings = relationship("Booking", back_populates="user", cascade="all, delete-orphan")

class Machine(Base):
    __tablename__ = "machines"

    id = Column(String(50), primary_key=True, index=True) # e.g. M1, M2
    name = Column(String(100), nullable=False)
    status = Column(Enum(MachineStatus), default=MachineStatus.AVAILABLE, nullable=False)

    records = relationship("UsageRecord", back_populates="machine", cascade="all, delete-orphan")
    bookings = relationship("Booking", back_populates="machine", cascade="all, delete-orphan")

class BlockedHour(Base):
    __tablename__ = "blocked_hours"

    id = Column(Integer, primary_key=True, index=True)
    hour = Column(Integer, unique=True, nullable=False) # 6 to 22

class UsageRecord(Base):
    __tablename__ = "usage_records"

    id = Column(Integer, primary_key=True, index=True)
    date = Column(Date, index=True, nullable=False)
    hour = Column(Integer, nullable=False) # 6 to 22
    machine_id = Column(String(50), ForeignKey("machines.id", ondelete="CASCADE"), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    machine = relationship("Machine", back_populates="records")

    __table_args__ = (
        Index("idx_usage_date_hour", "date", "hour"),
    )

class Booking(Base):
    __tablename__ = "bookings"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    machine_id = Column(String(50), ForeignKey("machines.id", ondelete="CASCADE"), nullable=False)
    date = Column(Date, nullable=False)
    hour = Column(Integer, nullable=False) # 6 to 22
    status = Column(Enum(BookingStatus), default=BookingStatus.CONFIRMED, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    user = relationship("User", back_populates="bookings")
    machine = relationship("Machine", back_populates="bookings")

    __table_args__ = (
        # Note: server-side conflict check explicitly validates confirmed bookings
        Index("idx_booking_d_h_m", "date", "hour", "machine_id"),
    )
