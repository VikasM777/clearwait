from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.db.session import get_db
from app.models.models import Machine, MachineStatus, User
from app.schemas.schemas import MachineCreate, MachineResponse, MachineUpdateStatus
from app.api.deps import get_current_admin

router = APIRouter(prefix="/machines", tags=["Machines"])

@router.get("", response_model=List[MachineResponse])
def list_machines(db: Session = Depends(get_db)):
    return db.query(Machine).order_by(Machine.id).all()

@router.post("", response_model=MachineResponse, status_code=status.HTTP_201_CREATED)
def create_machine(
    machine_in: MachineCreate,
    db: Session = Depends(get_db),
    admin: User = Depends(get_current_admin)
):
    # Auto-generate ID if not provided (e.g. M1, M2...)
    if not machine_in.id:
        existing = db.query(Machine.id).all()
        existing_nums = []
        for (m_id,) in existing:
            if m_id.startswith("M") and m_id[1:].isdigit():
                existing_nums.append(int(m_id[1:]))
            elif m_id.isdigit():
                existing_nums.append(int(m_id))
        next_num = max(existing_nums) + 1 if existing_nums else 1
        m_id = f"M{next_num}"
    else:
        m_id = machine_in.id

    if db.query(Machine).filter(Machine.id == m_id).first():
        raise HTTPException(status_code=400, detail="Machine ID already exists")

    machine = Machine(
        id=m_id,
        name=machine_in.name,
        status=machine_in.status
    )
    db.add(machine)
    db.commit()
    db.refresh(machine)
    return machine

@router.patch("/{machine_id}/status", response_model=MachineResponse)
def update_machine_status(
    machine_id: str,
    status_update: MachineUpdateStatus,
    db: Session = Depends(get_db),
    admin: User = Depends(get_current_admin)
):
    machine = db.query(Machine).filter(Machine.id == machine_id).first()
    if not machine:
        raise HTTPException(status_code=404, detail="Machine not found")
    
    machine.status = status_update.status
    db.commit()
    db.refresh(machine)
    return machine

@router.delete("/{machine_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_machine(
    machine_id: str,
    db: Session = Depends(get_db),
    admin: User = Depends(get_current_admin)
):
    machine = db.query(Machine).filter(Machine.id == machine_id).first()
    if not machine:
        raise HTTPException(status_code=404, detail="Machine not found")
    
    db.delete(machine)
    db.commit()
    return None
