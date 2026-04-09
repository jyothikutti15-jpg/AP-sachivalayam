import re
from enum import Enum

from fastapi import Depends, HTTPException, status
from passlib.context import CryptContext
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_db

# bcrypt context for Aadhaar hashing (rounds=12 ≈ 250ms on modern hardware —
# slow enough to resist brute-force, fast enough for interactive use).
_aadhaar_ctx = CryptContext(schemes=["bcrypt"], deprecated="auto", bcrypt__rounds=12)


class Role(str, Enum):
    EMPLOYEE = "employee"
    SECRETARIAT_ADMIN = "secretariat_admin"
    MANDAL_OFFICER = "mandal_officer"
    DISTRICT_ADMIN = "district_admin"
    SYSTEM_ADMIN = "system_admin"


ROLE_HIERARCHY = {
    Role.EMPLOYEE: 0,
    Role.SECRETARIAT_ADMIN: 1,
    Role.MANDAL_OFFICER: 2,
    Role.DISTRICT_ADMIN: 3,
    Role.SYSTEM_ADMIN: 4,
}

# Aadhaar pattern: 12 digits (Arabic numerals)
AADHAAR_PATTERN = re.compile(r"\b\d{4}\s?\d{4}\s?\d{4}\b")

# Aadhaar pattern: 12 digits (Telugu numerals ౦-౯)
AADHAAR_PATTERN_TELUGU = re.compile(r"[౦-౯]{4}\s?[౦-౯]{4}\s?[౦-౯]{4}")

# Phone pattern: Indian mobile numbers
PHONE_PATTERN = re.compile(r"\b(?:\+91|91|0)?[6-9]\d{9}\b")


def hash_aadhaar(aadhaar: str) -> str:
    """Bcrypt hash of Aadhaar with a random salt. Never store raw Aadhaar.

    Each call produces a different hash string — use verify_aadhaar() to
    check a candidate value against a stored hash, never plain ==.
    """
    cleaned = re.sub(r"\s", "", aadhaar)
    return _aadhaar_ctx.hash(cleaned)


def verify_aadhaar(aadhaar: str, stored_hash: str) -> bool:
    """Return True if aadhaar matches the stored bcrypt hash."""
    cleaned = re.sub(r"\s", "", aadhaar)
    return _aadhaar_ctx.verify(cleaned, stored_hash)


def mask_aadhaar(aadhaar: str) -> str:
    """Show only last 4 digits: XXXX XXXX 1234."""
    cleaned = re.sub(r"\s", "", aadhaar)
    return f"XXXX XXXX {cleaned[-4:]}"


def strip_pii(text: str) -> str:
    """Remove Aadhaar numbers and phone numbers before sending to LLMs.

    Handles both Arabic (0-9) and Telugu (౦-౯) digit formats.
    """
    result = AADHAAR_PATTERN.sub("[AADHAAR]", text)
    result = AADHAAR_PATTERN_TELUGU.sub("[AADHAAR]", result)
    result = PHONE_PATTERN.sub("[PHONE]", result)
    return result


def restore_pii(text: str, aadhaar: str | None = None, phone: str | None = None) -> str:
    """Reinsert PII placeholders with masked values."""
    if aadhaar:
        text = text.replace("[AADHAAR]", mask_aadhaar(aadhaar))
    if phone:
        text = text.replace("[PHONE]", phone)
    return text


async def get_employee_by_phone(phone_number: str, db: AsyncSession):
    """Look up employee by WhatsApp phone number."""
    from app.models.user import Employee
    result = await db.execute(
        select(Employee).where(Employee.phone_number == phone_number)
    )
    return result.scalar_one_or_none()


async def get_citizen_by_phone(phone_number: str, db: AsyncSession):
    """Look up citizen by WhatsApp phone number."""
    from app.models.citizen import Citizen
    result = await db.execute(
        select(Citizen).where(Citizen.phone_number == phone_number)
    )
    return result.scalar_one_or_none()


async def get_user_by_phone(phone_number: str, db: AsyncSession) -> tuple:
    """Look up user (employee or citizen) by phone. Employee takes priority."""
    employee = await get_employee_by_phone(phone_number, db)
    if employee:
        return employee, "employee"
    citizen = await get_citizen_by_phone(phone_number, db)
    if citizen:
        return citizen, "citizen"
    return None, None


def require_role(minimum_role: Role):
    """Dependency that checks if the user has at least the required role."""
    async def check_role(employee=None):
        if employee is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Authentication required",
            )
        user_role = Role(employee.role)
        if ROLE_HIERARCHY[user_role] < ROLE_HIERARCHY[minimum_role]:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Requires {minimum_role.value} role or higher",
            )
        return employee
    return check_role
