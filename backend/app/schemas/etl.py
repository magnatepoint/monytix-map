"""
ETL Pydantic schemas for validation and normalization
"""
from pydantic import BaseModel, Field, field_validator
from typing import Optional, Literal
from datetime import date, datetime


Direction = Literal["debit", "credit"]


class StagedTxnIn(BaseModel):
    """Schema for staging transaction data before validation"""
    amount: float
    transaction_date: date | datetime
    description: Optional[str] = None
    merchant: Optional[str] = None
    bank: Optional[str] = None
    category: Optional[str] = None
    reference_id: Optional[str] = None
    currency: str = "INR"
    transaction_type: Optional[str] = None  # optional, normalized later
    source: str
    row_number: int

    @field_validator("transaction_date", mode="before")
    @classmethod
    def _parse_date(cls, v):
        """Parse various date formats"""
        if isinstance(v, (date, datetime)):
            return v
        if v is None:
            return None
        try:
            from dateutil import parser
            parsed = parser.parse(str(v))
            return parsed.date() if isinstance(parsed, datetime) else parsed
        except Exception:
            # Return as-is if parsing fails, let validation handle it
            return v

    @field_validator("amount")
    @classmethod
    def _validate_amount(cls, v):
        """Ensure amount is positive"""
        if v is None:
            raise ValueError("Amount is required")
        if v < 0:
            raise ValueError("Amount must be positive")
        return float(v)

    class Config:
        json_encoders = {
            date: lambda v: v.isoformat(),
            datetime: lambda v: v.isoformat()
        }

