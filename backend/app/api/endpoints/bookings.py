from typing import List
from datetime import datetime, date, timezone
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import and_

from app.db.session import get_db
from app.models.models import Booking, BookingStatus, Machine, MachineStatus, BlockedHour, User, UserRole
from app.schemas.schemas import BookingCreate, BookingResponse
from app.api.deps import get_current_user

router = APIRouter(prefix="/bookings", tags=["Bookings"])

def format_booking_response(b: Booking) -> BookingResponse:
    return BookingResponse(
        id=b.id,
        date=b.date.isoformat(),
        hour=b.hour,
        machine_id=b.machine_id,
        machine_name=b.machine.name if b.machine else b.machine_id,
        status=b.status,
        user_email=b.user.email if b.user else "",
        user_name=b.user.name if b.user else "",
        created_at=b.created_at.isoformat() if b.created_at else ""
    )

@router.get("", response_model=List[BookingResponse])
def list_bookings(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    query = db.query(Booking)
    if current_user.role != UserRole.ADMIN:
        query = query.filter(Booking.user_id == current_user.id)
    
    bookings = query.order_by(Booking.date.desc(), Booking.hour.desc()).all()
    return [format_booking_response(b) for b in bookings]

@router.post("", response_model=BookingResponse, status_code=status.HTTP_201_CREATED)
def create_booking(
    booking_in: BookingCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    req_date = booking_in.date
    req_hour = booking_in.hour
    req_machine = booking_in.machine_id

    # 1. No booking in the past
    now = datetime.now()
    today = now.date()
    current_hour = now.hour
    if req_date < today or (req_date == today and req_hour <= current_hour):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot book time slots in the past"
        )

    # 2. No booking on blocked hours
    is_blocked = db.query(BlockedHour).filter(BlockedHour.hour == req_hour).first()
    if is_blocked:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="This hour is currently blocked by administration"
        )

    # 3. One confirmed booking per user per slot
    user_existing = db.query(Booking).filter(
        Booking.user_id == current_user.id,
        Booking.date == req_date,
        Booking.hour == req_hour,
        Booking.status == BookingStatus.CONFIRMED
    ).first()
    if user_existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="You already have a booking at this time"
        )

    # 4. Determine available machines (not in maintenance, not booked by confirmed booking)
    active_machines = db.query(Machine).filter(Machine.status != MachineStatus.MAINTENANCE).all()
    if not active_machines:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No machines available"
        )

    confirmed_booked_machine_ids = {
        b.machine_id for b in db.query(Booking.machine_id).filter(
            Booking.date == req_date,
            Booking.hour == req_hour,
            Booking.status == BookingStatus.CONFIRMED
        ).all()
    }

    free_machines = [m for m in active_machines if m.id not in confirmed_booked_machine_ids]

    assigned_machine_id = None
    if req_machine == "any":
        if not free_machines:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="That slot is no longer available"
            )
        # Select first free machine
        assigned_machine_id = free_machines[0].id
    else:
        # Check specific machine
        target_machine = next((m for m in free_machines if m.id == req_machine), None)
        if not target_machine:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="That slot is no longer available"
            )
        assigned_machine_id = target_machine.id

    # Create booking inside transaction with double-check
    # Double check no race condition occurred
    race_check = db.query(Booking).filter(
        Booking.date == req_date,
        Booking.hour == req_hour,
        Booking.machine_id == assigned_machine_id,
        Booking.status == BookingStatus.CONFIRMED
    ).first()
    if race_check:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="That slot is no longer available"
        )

    new_booking = Booking(
        user_id=current_user.id,
        machine_id=assigned_machine_id,
        date=req_date,
        hour=req_hour,
        status=BookingStatus.CONFIRMED,
        created_at=datetime.utcnow()
    )
    db.add(new_booking)
    db.commit()
    db.refresh(new_booking)

    return format_booking_response(new_booking)

@router.patch("/{booking_id}/cancel", response_model=BookingResponse)
def cancel_booking(
    booking_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    booking = db.query(Booking).filter(Booking.id == booking_id).first()
    if not booking:
        raise HTTPException(status_code=404, detail="Booking not found")

    if current_user.role != UserRole.ADMIN and booking.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized to cancel this booking")

    booking.status = BookingStatus.CANCELLED
    db.commit()
    db.refresh(booking)
    return format_booking_response(booking)
