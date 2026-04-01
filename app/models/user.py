from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin


class Secretariat(Base, TimestampMixin):
    __tablename__ = "secretariats"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    gsws_code: Mapped[str] = mapped_column(String(10), unique=True, nullable=False)
    name_te: Mapped[str] = mapped_column(Text, nullable=False)
    name_en: Mapped[str] = mapped_column(Text, nullable=False)
    mandal: Mapped[str | None] = mapped_column(String(100))
    district: Mapped[str | None] = mapped_column(String(100))
    pin_code: Mapped[str | None] = mapped_column(String(6))
    connectivity_tier: Mapped[str] = mapped_column(String(10), default="normal")

    employees: Mapped[list["Employee"]] = relationship(back_populates="secretariat")


class Employee(Base, TimestampMixin):
    __tablename__ = "employees"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    phone_number: Mapped[str] = mapped_column(String(15), unique=True, nullable=False)
    gsws_employee_id: Mapped[str | None] = mapped_column(String(20), unique=True)
    name_te: Mapped[str] = mapped_column(Text, nullable=False)
    name_en: Mapped[str | None] = mapped_column(Text)
    designation: Mapped[str] = mapped_column(String(100), nullable=False)
    department: Mapped[str] = mapped_column(String(100), nullable=False)
    secretariat_id: Mapped[int | None] = mapped_column(ForeignKey("secretariats.id"))
    preferred_language: Mapped[str] = mapped_column(String(5), default="te")
    role: Mapped[str] = mapped_column(String(20), default="employee")
    onboarded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    secretariat: Mapped[Secretariat | None] = relationship(back_populates="employees")
