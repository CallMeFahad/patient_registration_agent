"""
Vapi tool handlers.

Each function here corresponds to one "tool" the voice agent can call
mid-conversation (defined in the Vapi dashboard — see README). They reuse
the same Pydantic schemas and crud functions the REST API uses, per the
spec's "directly invoke the same service layer" option — there's no reason
to have the agent make an HTTP call to our own API when we can call the
same Python functions directly and skip a network hop.

Every handler returns a plain string. That string is what gets spoken back
to the caller by the voice agent's LLM, so these are written as short,
natural sentences — not JSON, not error codes.
"""

from typing import Any
from sqlalchemy.orm import Session
from pydantic import ValidationError

from app import crud
from api.schemas import PatientCreate, PatientUpdate


def _patient_summary(patient) -> str:
    return f"{patient.first_name} {patient.last_name}, date of birth {patient.date_of_birth}, patient ID {patient.patient_id}"


def _first_validation_error(exc: ValidationError) -> str:
    """
    Pydantic's exc.errors() is a list of every field that failed, meant for
    developers. The voice agent only needs to know about ONE problem at a
    time (so it can ask the caller to repeat just that field) — so we
    surface just the first error, phrased simply.
    """
    err = exc.errors()[0]
    field = err["loc"][-1]
    return f"the {field} field is invalid: {err['msg']}"


def check_existing_patient(db: Session, args: dict[str, Any]) -> str:
    """Looks up a patient by phone number — used for the duplicate-detection
    bonus. The LLM calls this BEFORE create_patient so it can offer to
    update an existing record instead of creating a duplicate."""
    digits = "".join(c for c in str(args.get("phone_number", "")) if c.isdigit())
    patient = crud.get_patient_by_phone(db, digits)
    if patient is None:
        return "No existing patient found with that phone number."
    return f"Existing patient found: {_patient_summary(patient)}."


def create_patient(db: Session, args: dict[str, Any]) -> str:
    try:
        patient_in = PatientCreate(**args)
    except ValidationError as exc:
        return f"Could not save the record — {_first_validation_error(exc)}. Please ask the caller to repeat that."
    patient = crud.create_patient(db, patient_in)
    return f"Patient successfully registered. {_patient_summary(patient)}."


def update_patient(db: Session, args: dict[str, Any]) -> str:
    args = dict(args)  # don't mutate the caller's dict
    patient_id = args.pop("patient_id", None)
    if not patient_id:
        return "Missing patient ID — cannot update without it."
    patient = crud.get_patient(db, patient_id)
    if patient is None:
        return "No patient found with that ID — cannot update."
    try:
        patient_in = PatientUpdate(**args)
    except ValidationError as exc:
        return f"Could not update the record — {_first_validation_error(exc)}."
    patient = crud.update_patient(db, patient, patient_in)
    return f"Patient record updated. {_patient_summary(patient)}."


# Maps the tool "name" Vapi sends us to the function that handles it.
# main.py's webhook route uses this to dispatch each incoming tool call.
TOOL_DISPATCH = {
    "check_existing_patient": check_existing_patient,
    "create_patient": create_patient,
    "update_patient": update_patient,
}
