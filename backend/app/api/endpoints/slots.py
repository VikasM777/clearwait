from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.db.session import get_db
from app.models.models import BlockedHour, User
from app.schemas.schemas import BlockedHourToggle
from app.api.deps import get_current_admin

router = APIRouter(prefix="/slots", tags=["Time Slots"])

@router.get("/blocked", response_model=List[int])
def get_blocked_hours(db: Session = Depends(get_db)):
    blocked = db.query(BlockedHour).all()
    return [b.hour for b in blocked]

@router.post("/toggle", response_model=List[int])
def toggle_blocked_hour(
    payload: BlockedHourToggle,
    db: Session = Depends(get_db),
    admin: User = Depends(get_current_admin)
):
    hour = payload.hour
    existing = db.query(BlockedHour).filter(BlockedHour.hour == hour).first()
    if existing:
        db.delete(existing)
    else:
        new_blocked = BlockedHour(hour=hour)
        db.add(new_blocked)
    db.commit()
    
    blocked = db.query(BlockedHour).all()
    return [b.hour for b in blocked]
