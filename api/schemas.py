"""
Pydantic schemas — these define what counts as *valid* API input/output.

Why duplicate validation that's already in the SQL CHECK constraints?
Because Pydantic validation runs before we ever touch the database, so a bad
request gets a clean 422 with a specific field-level error message instead
of a raw Postgres constraint-violation error. The DB constraints are the
last line of defense; these are the first.
"""

from datetime import date, datetime
from enum import Enum
from typing import Optional
from uuid import UUID
from pydantic import BaseModel, EmailStr, field_validator


class Sex(str, Enum):
    male = "Male"
    female = "Female"
    other = "Other"
    decline = "Decline to Answer"


class PatientBase(BaseModel):
    """Shared validators used by both create and update schemas."""

    @field_validator("phone_number", "emergency_contact_phone", check_fields=False)
    @classmethod
    def validate_phone(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        digits = v.replace("-", "").replace(" ", "").replace("(", "").replace(")", "")
        if not digits.isdigit() or len(digits) != 10:
            raise ValueError("must be a valid 10-digit U.S. phone number")
        return digits

    @field_validator("date_of_birth", check_fields=False)
    @classmethod
    def validate_dob(cls, v: Optional[date]) -> Optional[date]:
        if v is not None and v > date.today():
            raise ValueError("date of birth cannot be in the future")
        return v

    @field_validator("zip_code", check_fields=False)
    @classmethod
    def validate_zip(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        digits = v.replace("-", "")
        if not digits.isdigit() or len(digits) not in (5, 9):
            raise ValueError("must be a 5-digit or ZIP+4 U.S. zip code")
        return v

    @field_validator("state", check_fields=False)
    @classmethod
    def validate_state(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and (len(v) != 2 or not v.isalpha()):
            raise ValueError("must be a 2-letter U.S. state abbreviation")
        return v.upper() if v else v


class PatientCreate(PatientBase):
    """Fields required to register a new patient (POST /patients)."""

    first_name: str
    last_name: str
    date_of_birth: date
    sex: Sex
    phone_number: str
    address_line_1: str
    city: str
    state: str
    zip_code: str

    # Optional at registration time
    email: Optional[EmailStr] = None
    address_line_2: Optional[str] = None
    insurance_provider: Optional[str] = None
    insurance_member_id: Optional[str] = None
    preferred_language: Optional[str] = "English"
    emergency_contact_name: Optional[str] = None
    emergency_contact_phone: Optional[str] = None


class PatientUpdate(PatientBase):
    """
    All fields optional — PUT /patients/:id allows partial updates.
    Only the fields the caller actually sends get changed.
    """

    first_name: Optional[str] = None
    last_name: Optional[str] = None
    date_of_birth: Optional[date] = None
    sex: Optional[Sex] = None
    phone_number: Optional[str] = None
    address_line_1: Optional[str] = None
    address_line_2: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    zip_code: Optional[str] = None
    email: Optional[EmailStr] = None
    insurance_provider: Optional[str] = None
    insurance_member_id: Optional[str] = None
    preferred_language: Optional[str] = None
    emergency_contact_name: Optional[str] = None
    emergency_contact_phone: Optional[str] = None


class PatientResponse(BaseModel):
    """What we send back to the client — includes server-generated fields."""

    patient_id: UUID
    first_name: str
    last_name: str
    date_of_birth: date
    sex: str
    phone_number: str
    email: Optional[str] = None
    address_line_1: str
    address_line_2: Optional[str] = None
    city: str
    state: str
    zip_code: str
    insurance_provider: Optional[str] = None
    insurance_member_id: Optional[str] = None
    preferred_language: str
    emergency_contact_name: Optional[str] = None
    emergency_contact_phone: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}  # lets us build this directly from a SQLAlchemy Patient object