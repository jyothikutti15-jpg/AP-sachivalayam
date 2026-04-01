import hashlib
import re
from enum import Enum

from fastapi import Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_db


class Role(str, Enum):
    EMPLOYEE = "employee"
    SECRETARIAT_ADMIN = "secretariat_admin"
    DISTRICT_ADMIN = "district_admin"
    SYSTEM_ADMIN = "system_admin"


ROLE_HIERARCHY = {
    Role.EMPLOYEE: 0,
    Role.SECRETARIAT_ADMIN: 1,
    Role.DISTRICT_ADMIN: 2,
    Role.SYSTEM_ADMIN: 3,
}

# Aadhaar pattern: 12 digits
AADHAAR_PATTERN = re.compile(r"\b\d{4}\s?\d{4}\s?\d{4}\b")

# Phone pattern: Indian mobile numbers
PHONE_PATTERN = re.compile(r"\b(?:\+91|91|0)?[6-9]\d{9}\b")


def hash_aadhaar(aadhaar: str) -> str:
    """SHA-256 hash of Aadhaar number. Never store raw Aadhaar."""
    cleaned = re.sub(r"\s", "", aadhaar)
    return hashlib.sha256(cleaned.encode()).hexdigest()


def mask_aadhaar(aadhaar: str) -> str:
    """Show only last 4 digits: XXXX XXXX 1234."""
    cleaned = re.sub(r"\s", "", aadhaar)
    return f"XXXX XXXX {cleaned[-4:]}"


def strip_pii(text: str) -> str:
    """Remove Aadhaar numbers and phone numbers before sending to LLMs."""
    result = AADHAAR_PATTERN.sub("[AADHAAR]", text)
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
