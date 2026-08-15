-- 001_create_patients.sql
-- Creates the patients table matching the required demographic data model.
-- Run manually: docker exec -i <db_container> psql -U <user> -d <db> < 001_create_patients.sql

-- pgcrypto gives us gen_random_uuid() for the primary key.
CREATE EXTENSION IF NOT EXISTS pgcrypto;

CREATE TABLE IF NOT EXISTS patients (
    patient_id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Required fields
    first_name              VARCHAR(100) NOT NULL,
    last_name                VARCHAR(100) NOT NULL,
    date_of_birth            DATE NOT NULL,
    sex                       VARCHAR(20) NOT NULL,
    phone_number              VARCHAR(20) NOT NULL,
    address_line_1            TEXT NOT NULL,
    city                      TEXT NOT NULL,
    state                     CHAR(2) NOT NULL,
    zip_code                  VARCHAR(10) NOT NULL,

    -- Optional fields
    email                     VARCHAR(255),
    address_line_2            VARCHAR(255),
    insurance_provider        VARCHAR(255),
    insurance_member_id       VARCHAR(100),
    preferred_language        VARCHAR(50) NOT NULL DEFAULT 'English',
    emergency_contact_name    VARCHAR(100),
    emergency_contact_phone   VARCHAR(10),

    -- Bookkeeping
    created_at                TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at                TIMESTAMPTZ NOT NULL DEFAULT now(),
    deleted_at                TIMESTAMPTZ,  -- NULL = active record; set on soft-delete

    -- Validation rules from the spec, enforced at the DB level (not just the API)
    CONSTRAINT sex_valid CHECK (sex IN ('Male', 'Female', 'Other', 'Decline to Answer')),
    CONSTRAINT phone_number_valid CHECK (phone_number ~ '^[0-9]{10}$'),
    CONSTRAINT emergency_contact_phone_valid CHECK (emergency_contact_phone IS NULL OR emergency_contact_phone ~ '^[0-9]{10}$'),
    CONSTRAINT zip_code_valid CHECK (zip_code ~ '^[0-9]{5}(-[0-9]{4})?$'),
    CONSTRAINT dob_not_future CHECK (date_of_birth <= CURRENT_DATE)
);

-- Supports the ?last_name=, ?date_of_birth=, ?phone_number= query params on GET /patients
CREATE INDEX IF NOT EXISTS idx_patients_last_name ON patients (last_name);
CREATE INDEX IF NOT EXISTS idx_patients_date_of_birth ON patients (date_of_birth);
CREATE INDEX IF NOT EXISTS idx_patients_phone_number ON patients (phone_number);

-- trigger to keep updated_at accurate whenever a row is modified.
CREATE OR REPLACE FUNCTION set_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = now();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_patients_updated_at ON patients;
CREATE TRIGGER trg_patients_updated_at
    BEFORE UPDATE ON patients
    FOR EACH ROW
    EXECUTE FUNCTION set_updated_at();

-- Seed data (optional, per spec) — useful for testing GET/PUT without a live call first.
INSERT INTO patients (first_name, last_name, date_of_birth, sex, phone_number, address_line_1, city, state, zip_code)
VALUES ('Jane', 'Doe', '1990-05-14', 'Female', '5551234567', '123 Main St', 'Austin', 'TX', '73301')
ON CONFLICT DO NOTHING;