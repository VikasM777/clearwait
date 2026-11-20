import csv
import io
from typing import List, Optional
from datetime import date
from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Query
from sqlalchemy.orm import Session
from app.db.session import get_db
from app.models.models import UsageRecord, Machine, User
from app.schemas.schemas import UsageRecordCreate, UsageRecordResponse, CSVImportResult
from app.api.deps import get_current_user, get_current_admin

router = APIRouter(prefix="/records", tags=["Usage Records"])

@router.get("", response_model=List[UsageRecordResponse])
def list_records(
    from_date: Optional[date] = None,
    to_date: Optional[date] = None,
    machine_id: Optional[str] = None,
    limit: int = Query(500, ge=1, le=5000),
    db: Session = Depends(get_db)
):
    query = db.query(UsageRecord)
    if from_date:
        query = query.filter(UsageRecord.date >= from_date)
    if to_date:
        query = query.filter(UsageRecord.date <= to_date)
    if machine_id and machine_id != "all":
        query = query.filter(UsageRecord.machine_id == machine_id)
    
    return query.order_by(UsageRecord.date.desc(), UsageRecord.hour.desc()).limit(limit).all()

@router.post("", response_model=UsageRecordResponse, status_code=status.HTTP_201_CREATED)
def create_record(
    record_in: UsageRecordCreate,
    db: Session = Depends(get_db),
    admin: User = Depends(get_current_admin)
):
    # Verify machine exists
    machine = db.query(Machine).filter(Machine.id == record_in.machine_id).first()
    if not machine:
        raise HTTPException(status_code=400, detail=f"Machine {record_in.machine_id} does not exist")
    
    record = UsageRecord(
        date=record_in.date,
        hour=record_in.hour,
        machine_id=record_in.machine_id
    )
    db.add(record)
    db.commit()
    db.refresh(record)
    return record

@router.post("/upload-csv", response_model=CSVImportResult)
async def upload_csv(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    admin: User = Depends(get_current_admin)
):
    if not file.filename.endswith(".csv"):
        raise HTTPException(status_code=400, detail="File must be a CSV")

    contents = await file.read()
    text = contents.decode("utf-8-sig", errors="ignore")
    reader = csv.reader(io.StringIO(text))
    
    machines = {m.id: m for m in db.query(Machine).all()}
    name_to_id = {m.name.lower(): m.id for m in machines.values()}
    
    records_to_insert = []
    imported_count = 0

    for row in reader:
        if not row or len(row) < 3:
            continue
        d_str, h_str, m_str = [cell.strip() for cell in row[:3]]
        
        # Skip header if present
        if d_str.lower() == "date" or h_str.lower() == "hour":
            continue
        
        try:
            parts = [int(p) for p in d_str.split("-")]
            record_date = date(parts[0], parts[1], parts[2])
            record_hour = int(h_str)
            if not (6 <= record_hour <= 22):
                continue
            
            # Match machine by ID or Name
            m_id = None
            if m_str in machines:
                m_id = m_str
            elif m_str.lower() in name_to_id:
                m_id = name_to_id[m_str.lower()]
            
            if not m_id:
                continue

            records_to_insert.append(UsageRecord(
                date=record_date,
                hour=record_hour,
                machine_id=m_id
            ))
            imported_count += 1
        except Exception:
            continue

    if records_to_insert:
        db.bulk_save_objects(records_to_insert)
        db.commit()

    return CSVImportResult(
        imported_count=imported_count,
        message=f"{imported_count} records imported successfully"
    )

@router.delete("/{record_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_record(
    record_id: int,
    db: Session = Depends(get_db),
    admin: User = Depends(get_current_admin)
):
    record = db.query(UsageRecord).filter(UsageRecord.id == record_id).first()
    if not record:
        raise HTTPException(status_code=404, detail="Usage record not found")
    
    db.delete(record)
    db.commit()
    return None
