"""Beneficiary model — Stores citizen demographics for outreach matching."""
from sqlalchemy import Boolean, Float, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


class Beneficiary(Base, TimestampMixin):
    __tablename__ = "beneficiaries"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    aadhaar_hash: Mapped[str | None] = mapped_column(String(64), unique=True, index=True)
    phone_number: Mapped[str | None] = mapped_column(String(15), index=True)
    name_te: Mapped[str] = mapped_column(Text, nullable=False)
    name_en: Mapped[str | None] = mapped_column(Text)
    age: Mapped[int | None] = mapped_column(Integer)
    gender: Mapped[str | None] = mapped_column(String(10))  # male/female/other
    caste_category: Mapped[str | None] = mapped_column(String(10))  # SC/ST/BC/OC/Minority
    annual_income: Mapped[int | None] = mapped_column(Integer)
    ration_card_type: Mapped[str | None] = mapped_column(String(15))  # white/rice/antyodaya/none
    district: Mapped[str | None] = mapped_column(String(50))
    mandal: Mapped[str | None] = mapped_column(String(50))
    secretariat_id: Mapped[int | None] = mapped_column(ForeignKey("secretariats.id"))
    is_disabled: Mapped[bool] = mapped_column(Boolean, default=False)
    disability_percentage: Mapped[int | None] = mapped_column(Integer)
    occupation: Mapped[str | None] = mapped_column(String(50))
    land_acres_wet: Mapped[float | None] = mapped_column(Float)
    land_acres_dry: Mapped[float | None] = mapped_column(Float)
    num_children: Mapped[int | None] = mapped_column(Integer)
    is_govt_employee: Mapped[bool] = mapped_column(Boolean, default=False)
    is_income_tax_payer: Mapped[bool] = mapped_column(Boolean, default=False)
    owns_four_wheeler: Mapped[bool] = mapped_column(Boolean, default=False)
    electricity_units: Mapped[int | None] = mapped_column(Integer)
    schemes_enrolled: Mapped[dict | None] = mapped_column(JSONB)  # ["SCHEME-CODE", ...]
    opt_out: Mapped[bool] = mapped_column(Boolean, default=False)
    metadata_extra: Mapped[dict | None] = mapped_column(JSONB)
