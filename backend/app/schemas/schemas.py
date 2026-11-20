from typing import Optional, List
from datetime import date, datetime
from pydantic import BaseModel, EmailStr, Field
from app.models.models import UserRole, MachineStatus, BookingStatus

# --- Auth & User ---
class UserBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    email: EmailStr

class UserCreate(UserBase):
    password: str = Field(..., min_length=6, max_length=100)
    role: Optional[UserRole] = UserRole.RESIDENT

class UserLogin(BaseModel):
    email: EmailStr
    password: str

class UserResponse(UserBase):
    id: int
    role: UserRole
    created_at: datetime

    class Config:
        from_attributes = True

class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserResponse

# --- Machine ---
class MachineBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    status: MachineStatus = MachineStatus.AVAILABLE

class MachineCreate(MachineBase):
    id: Optional[str] = None # e.g. M1; if not provided, can be auto-generated

class MachineUpdateStatus(BaseModel):
    status: MachineStatus

class MachineResponse(BaseModel):
    id: str
    name: str
    status: MachineStatus

    class Config:
        from_attributes = True

# --- Blocked Hours ---
class BlockedHourToggle(BaseModel):
    hour: int = Field(..., ge=6, le=22)

# --- Usage Record ---
class UsageRecordCreate(BaseModel):
    date: date
    hour: int = Field(..., ge=6, le=22)
    machine_id: str

class UsageRecordResponse(BaseModel):
    id: int
    date: date
    hour: int
    machine_id: str
    created_at: datetime

    class Config:
        from_attributes = True

class CSVImportResult(BaseModel):
    imported_count: int
    message: str

# --- Booking ---
class BookingCreate(BaseModel):
    date: date
    hour: int = Field(..., ge=6, le=22)
    machine_id: str # 'any' or specific ID like 'M1'

class BookingResponse(BaseModel):
    id: int
    date: str # YYYY-MM-DD
    hour: int
    machine_id: str
    machine_name: Optional[str] = None
    status: BookingStatus
    user_email: str
    user_name: Optional[str] = None
    created_at: str

    class Config:
        from_attributes = True

# --- Dashboard Stats ---
class DashboardStats(BaseModel):
    total_machines: int
    occupied_now: int
    available_now: int
    confirmed_bookings: int
    total_wash_cycles: int
    average_utilisation: float
    current_demand_level: str
    current_demand_color: str
    today_demand_strip: List[dict]
    recommended_today: List[dict]

# --- Analytics Schemas ---
class AnalyticsSummary(BaseModel):
    dates: List[str]
    total_cycles: int
    hourly_avg: List[float]
    daily_trend: dict
    weekday_vs_weekend: dict
    machine_utilisation: List[dict]
    peak_hours: List[dict]
    low_demand_slots: List[dict]
    booking_trends: dict
    heatmap: dict

# --- KMeans Schemas ---
class CentroidInfo(BaseModel):
    c: int
    rank: int
    name: str
    color: str
    avg: float
    max: float
    n: int

class SlotCluster(BaseModel):
    d: int # 0=Sun..6=Sat
    h: int # 6..22
    avg: float
    max: float
    rank: int
    name: str
    color: str

class KMeansResponse(BaseModel):
    k: int
    inertia: float
    total_cycles: int
    total_days: int
    cents: List[CentroidInfo]
    slots: List[SlotCluster]

# --- Recommendations ---
class RecommendationSlot(BaseModel):
    hour: int
    label: str # e.g. "08:00 - 09:00"
    cluster_name: str
    cluster_color: str
    cluster_rank: int
    expected_demand_pct: float
    free_machines_count: int
    free_machine_ids: List[str]
    reason: str

class RecommendationResponse(BaseModel):
    date: str
    period: str
    machine: str
    recommendations: List[RecommendationSlot]
    peak_hours_to_avoid: List[int]
