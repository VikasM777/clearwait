from pydantic import BaseModel
from typing import Optional

class AppointmentBase(BaseModel):
    name: str
    phone: Optional[str] = ""
    date: str
    time: str
    status: Optional[str] = "booked"
    remindedAt: Optional[float] = None
    rescheduled: Optional[int] = 0
    created: Optional[float] = None

class AppointmentCreate(AppointmentBase):
    pass

class AppointmentUpdate(BaseModel):
    name: Optional[str] = None
    phone: Optional[str] = None
    date: Optional[str] = None
    time: Optional[str] = None
    status: Optional[str] = None
    remindedAt: Optional[float] = None
    rescheduled: Optional[int] = None

class AppointmentOut(AppointmentBase):
    id: str
    class Config:
        from_attributes = True


class PatientBase(BaseModel):
    name: str
    code: str
    status: Optional[str] = "waiting"
    startedAt: Optional[float] = None
    doneAt: Optional[float] = None
    created: Optional[float] = None

class PatientCreate(PatientBase):
    pass

class PatientUpdate(BaseModel):
    name: Optional[str] = None
    code: Optional[str] = None
    status: Optional[str] = None
    startedAt: Optional[float] = None
    doneAt: Optional[float] = None

class PatientOut(PatientBase):
    id: str
    class Config:
        from_attributes = True


class RecordBase(BaseModel):
    name: str
    phone: Optional[str] = ""
    age: Optional[str] = ""
    allergies: Optional[str] = ""
    history: Optional[str] = ""
    created: Optional[float] = None

class RecordCreate(RecordBase):
    pass

class RecordOut(RecordBase):
    id: str
    class Config:
        from_attributes = True


class PrescriptionBase(BaseModel):
    patient: str
    doctor: Optional[str] = ""
    meds: str
    advice: Optional[str] = ""
    created: Optional[float] = None

class PrescriptionCreate(PrescriptionBase):
    pass

class PrescriptionOut(PrescriptionBase):
    id: str
    class Config:
        from_attributes = True
