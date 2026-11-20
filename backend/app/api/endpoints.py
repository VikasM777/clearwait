import uuid
from typing import List, Dict, Any
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.db.session import get_db
from app.models.models import Appointment, Patient, Record, Prescription
from app.schemas.schemas import (
    AppointmentCreate, AppointmentUpdate, AppointmentOut,
    PatientCreate, PatientUpdate, PatientOut,
    RecordCreate, RecordOut,
    PrescriptionCreate, PrescriptionOut
)

router = APIRouter()

# --- Sync endpoint: get all data in one call for fast initial load ---
@router.get("/all")
def get_all_data(db: Session = Depends(get_db)):
    return {
        "appts": db.query(Appointment).all(),
        "patients": db.query(Patient).all(),
        "records": db.query(Record).all(),
        "rx": db.query(Prescription).all()
    }

# --- Appointments ---
@router.get("/appts", response_model=List[AppointmentOut])
def get_appointments(db: Session = Depends(get_db)):
    return db.query(Appointment).all()

@router.post("/appts", response_model=AppointmentOut)
def create_appointment(data: AppointmentCreate, db: Session = Depends(get_db)):
    item = Appointment(id=f"a_{uuid.uuid4().hex[:10]}", **data.model_dump())
    db.add(item)
    db.commit()
    db.refresh(item)
    return item

@router.patch("/appts/{id}", response_model=AppointmentOut)
def update_appointment(id: str, data: AppointmentUpdate, db: Session = Depends(get_db)):
    item = db.query(Appointment).filter(Appointment.id == id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Not found")
    update_data = data.model_dump(exclude_unset=True)
    for k, v in update_data.items():
        setattr(item, k, v)
    db.commit()
    db.refresh(item)
    return item

@router.delete("/appts/{id}")
def delete_appointment(id: str, db: Session = Depends(get_db)):
    item = db.query(Appointment).filter(Appointment.id == id).first()
    if item:
        db.delete(item)
        db.commit()
    return {"ok": True}

# --- Patients (Live Queue) ---
@router.get("/patients", response_model=List[PatientOut])
def get_patients(db: Session = Depends(get_db)):
    return db.query(Patient).all()

@router.post("/patients", response_model=PatientOut)
def create_patient(data: PatientCreate, db: Session = Depends(get_db)):
    item = Patient(id=f"p_{uuid.uuid4().hex[:10]}", **data.model_dump())
    db.add(item)
    db.commit()
    db.refresh(item)
    return item

@router.patch("/patients/{id}", response_model=PatientOut)
def update_patient(id: str, data: PatientUpdate, db: Session = Depends(get_db)):
    item = db.query(Patient).filter(Patient.id == id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Not found")
    update_data = data.model_dump(exclude_unset=True)
    for k, v in update_data.items():
        setattr(item, k, v)
    db.commit()
    db.refresh(item)
    return item

@router.delete("/patients/{id}")
def delete_patient(id: str, db: Session = Depends(get_db)):
    item = db.query(Patient).filter(Patient.id == id).first()
    if item:
        db.delete(item)
        db.commit()
    return {"ok": True}

# --- Records ---
@router.get("/records", response_model=List[RecordOut])
def get_records(db: Session = Depends(get_db)):
    return db.query(Record).all()

@router.post("/records", response_model=RecordOut)
def create_record(data: RecordCreate, db: Session = Depends(get_db)):
    item = Record(id=f"r_{uuid.uuid4().hex[:10]}", **data.model_dump())
    db.add(item)
    db.commit()
    db.refresh(item)
    return item

@router.delete("/records/{id}")
def delete_record(id: str, db: Session = Depends(get_db)):
    item = db.query(Record).filter(Record.id == id).first()
    if item:
        db.delete(item)
        db.commit()
    return {"ok": True}

# --- Prescriptions (Rx) ---
@router.get("/rx", response_model=List[PrescriptionOut])
def get_prescriptions(db: Session = Depends(get_db)):
    return db.query(Prescription).all()

@router.post("/rx", response_model=PrescriptionOut)
def create_prescription(data: PrescriptionCreate, db: Session = Depends(get_db)):
    item = Prescription(id=f"x_{uuid.uuid4().hex[:10]}", **data.model_dump())
    db.add(item)
    db.commit()
    db.refresh(item)
    return item

@router.delete("/rx/{id}")
def delete_prescription(id: str, db: Session = Depends(get_db)):
    item = db.query(Prescription).filter(Prescription.id == id).first()
    if item:
        db.delete(item)
        db.commit()
    return {"ok": True}
