"""
FastAPI entrypoint — the 5 required REST endpoints for patient records.

Every response (success or error) uses the { "data": ..., "error": ... }
envelope required by the spec. The two exception handlers below are what
make that consistent even for errors FastAPI generates itself (validation
errors, 404s) rather than ones we raise by hand in each endpoint.
"""

import logging
from uuid import UUID

from fastapi import FastAPI, Depends, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session

from database.connect import get_db
from app import crud
from api.schemas import PatientCreate, PatientUpdate, PatientResponse

# Logs to stdout by default — satisfies the "log agent conversations / the
# final collected data payload to stdout" requirement. Whatever hosts this
# (Railway, your terminal) captures stdout automatically, so no log file
# management is needed for a project this size.
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("patient_api")

app = FastAPI(title="Patient Registration API")


# --- Error envelope -----------------------------------------------------
# FastAPI's defaults return {"detail": "..."} on errors. These two handlers
# override that so every error also comes back as {"data": null, "error": "..."}
# matching the same envelope successful responses use.

@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    return JSONResponse(status_code=exc.status_code, content={"data": None, "error": exc.detail})


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    # exc.errors() is Pydantic's structured list of what failed and why —
    # more useful to a caller than a generic "bad request".
    return JSONResponse(status_code=422, content={"data": None, "error": exc.errors()})


@app.exception_handler(IntegrityError)
async def integrity_error_handler(request: Request, exc: IntegrityError):
    # Raised when a write violates a DB-level CHECK/NOT NULL constraint —
    # e.g. something Pydantic's validators didn't catch. This is the
    # "database write fails" case the spec calls out: the caller gets a
    # clean 422, not silence and not a raw Postgres stack trace.
    logger.warning("DB constraint violation: %s", exc)
    return JSONResponse(status_code=422, content={"data": None, "error": "Invalid data — could not save patient record"})


@app.exception_handler(SQLAlchemyError)
async def db_error_handler(request: Request, exc: SQLAlchemyError):
    # Catches anything else DB-related (e.g. connection dropped mid-query).
    # Also the caller's fallback if the write genuinely fails for reasons
    # outside their control — still a clean envelope, never a silent crash.
    logger.error("Unexpected database error: %s", exc)
    return JSONResponse(status_code=500, content={"data": None, "error": "Database error — please try again"})


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    # Last-resort catch-all so no bug anywhere in the app can produce a bare
    # 500 with no body. The voice agent always gets *something* it can
    # relay to the caller as a graceful error message, never a silent hang.
    logger.error("Unhandled exception: %s", exc, exc_info=True)
    return JSONResponse(status_code=500, content={"data": None, "error": "Internal server error"})


# --- Health check ---------------------------------------------------------

@app.get("/health")
def health_check(db: Session = Depends(get_db)):
    db.execute(text("SELECT 1"))
    return {"data": {"status": "ok"}, "error": None}


# --- Patient endpoints ------------------------------------------------------

@app.get("/patients")
def list_patients(
    last_name: str | None = None,
    date_of_birth: str | None = None,
    phone_number: str | None = None,
    db: Session = Depends(get_db),
):
    patients = crud.list_patients(db, last_name, date_of_birth, phone_number)
    data = [PatientResponse.model_validate(p).model_dump(mode="json") for p in patients]
    return {"data": data, "error": None}


@app.get("/patients/{patient_id}")
def get_patient(patient_id: UUID, db: Session = Depends(get_db)):
    patient = crud.get_patient(db, patient_id)
    if patient is None:
        raise HTTPException(status_code=404, detail="Patient not found")
    return {"data": PatientResponse.model_validate(patient).model_dump(mode="json"), "error": None}


@app.post("/patients", status_code=201)
def create_patient(patient_in: PatientCreate, db: Session = Depends(get_db)):
    patient = crud.create_patient(db, patient_in)
    logger.info(
        "Patient registered: patient_id=%s name=%s %s phone=%s",
        patient.patient_id, patient.first_name, patient.last_name, patient.phone_number,
    )
    return {"data": PatientResponse.model_validate(patient).model_dump(mode="json"), "error": None}


@app.put("/patients/{patient_id}")
def update_patient(patient_id: UUID, patient_in: PatientUpdate, db: Session = Depends(get_db)):
    patient = crud.get_patient(db, patient_id)
    if patient is None:
        raise HTTPException(status_code=404, detail="Patient not found")
    patient = crud.update_patient(db, patient, patient_in)
    return {"data": PatientResponse.model_validate(patient).model_dump(mode="json"), "error": None}


@app.delete("/patients/{patient_id}")
def delete_patient(patient_id: UUID, db: Session = Depends(get_db)):
    patient = crud.get_patient(db, patient_id)
    if patient is None:
        raise HTTPException(status_code=404, detail="Patient not found")
    crud.soft_delete_patient(db, patient)
    return {"data": {"patient_id": str(patient_id), "deleted": True}, "error": None}