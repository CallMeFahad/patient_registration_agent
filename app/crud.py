"""
CRUD functions — the actual database logic, kept separate from the HTTP
layer (api/main.py). Each function takes a DB session and returns either
a Patient object, a list of them, or None. No HTTP concerns (status codes,
JSON shaping) live here — that's main.py's job.
"""

from datetime import date, datetime, timezone
from typing import Optional
from uuid import UUID

from sqlalchemy.orm import Session

from app.models import Patient
from api.schemas import PatientCreate, PatientUpdate


def _active_query(db: Session):
    """Base query excluding soft-deleted rows — used by every read function
    so a deleted patient never resurfaces in a GET."""
    return db.query(Patient).filter(Patient.deleted_at.is_(None))


def list_patients(
    db: Session,
    last_name: Optional[str] = None,
    date_of_birth: Optional[date] = None,
    phone_number: Optional[str] = None,
) -> list[Patient]:
    query = _active_query(db)
    if last_name:
        query = query.filter(Patient.last_name.ilike(last_name))
    if date_of_birth:
        query = query.filter(Patient.date_of_birth == date_of_birth)
    if phone_number:
        query = query.filter(Patient.phone_number == phone_number)
    return query.all()


def get_patient(db: Session, patient_id: UUID) -> Optional[Patient]:
    return _active_query(db).filter(Patient.patient_id == patient_id).first()


def get_patient_by_phone(db: Session, phone_number: str) -> Optional[Patient]:
    """Used for the duplicate-detection bonus: the voice agent checks this
    before creating a new record, to offer an update instead."""
    return _active_query(db).filter(Patient.phone_number == phone_number).first()


def create_patient(db: Session, patient_in: PatientCreate) -> Patient:
    patient = Patient(**patient_in.model_dump())
    db.add(patient)
    db.commit()
    db.refresh(patient)  # pulls back server-generated fields: patient_id, created_at, etc.
    return patient


def update_patient(db: Session, patient: Patient, patient_in: PatientUpdate) -> Patient:
    # exclude_unset=True means "only fields the caller actually sent" —
    # this is what makes PUT a partial update instead of overwriting
    # every field with None.
    updates = patient_in.model_dump(exclude_unset=True)
    for field, value in updates.items():
        setattr(patient, field, value)
    db.commit()
    db.refresh(patient)
    return patient


def soft_delete_patient(db: Session, patient: Patient) -> Patient:
    patient.deleted_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(patient)
    return patient