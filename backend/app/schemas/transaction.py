from pydantic import BaseModel, Field, field_validator
from decimal import Decimal, ROUND_HALF_UP
from datetime import datetime
from typing import Optional, List
from enum import Enum


class TransactionType(str, Enum):
    DEBIT = "debit"
    CREDIT = "credit"
    CREDIT_CARD = "credit_card"  # Credit card transaction (treated as debit)


class TransactionStatus(str, Enum):
    PENDING = "pending"
    CLEARED = "cleared"
    FAILED = "failed"


class TransactionCreate(BaseModel):
    amount: Decimal = Field(..., ge=Decimal("0.01"), description="Transaction amount")
    currency: str = Field(default="INR", pattern="^[A-Z]{3}$", description="ISO 4217 currency code")
    transaction_date: datetime = Field(..., description="Transaction date and time (UTC preferred)")
    description: str = Field(..., min_length=1, max_length=1000)
    merchant: Optional[str] = Field(None, max_length=255)
    category: Optional[str] = Field(None, max_length=100)  # category_code
    subcategory: Optional[str] = Field(None, max_length=100)  # subcategory_code
    bank: Optional[str] = Field(None, max_length=100)
    account_type: Optional[str] = Field(None, max_length=50)
    transaction_type: TransactionType
    reference_id: Optional[str] = Field(None, max_length=255)
    tags: List[str] = Field(default_factory=list)  # NOTE: Pydantic doesn't enforce list max_length here
    status: TransactionStatus = Field(default=TransactionStatus.CLEARED)
    
    @field_validator('amount')
    @classmethod
    def validate_amount(cls, v: Decimal) -> Decimal:
        # Force 2dp quantization to avoid floaty decimals
        q = v.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        if q <= 0:
            raise ValueError("Amount must be positive")
        if q > Decimal("999999999"):
            raise ValueError("Amount exceeds maximum allowed")
        return q
    
    @field_validator('currency')
    @classmethod
    def validate_currency(cls, v: str) -> str:
        return v.upper()
    
    @field_validator('tags')
    @classmethod
    def validate_tags(cls, v: List[str]) -> List[str]:
        # Enforce at-most 20 tags and trim/normalize
        if len(v) > 20:
            raise ValueError("At most 20 tags allowed")
        norm = []
        for t in v:
            t = (t or "").strip()
            if not t:
                continue
            if len(t) > 40:
                raise ValueError("Each tag must be <= 40 chars")
            norm.append(t)
        return norm
    
    class Config:
        json_schema_extra = {
            "example": {
                "amount": 2450.00,
                "currency": "INR",
                "transaction_date": "2024-01-15T10:30:00Z",
                "description": "Amazon purchase",
                "merchant": "AMAZON",
                "category": "shopping",
                "subcategory": "online_shopping",
                "bank": "HDFC",
                "transaction_type": "debit",
                "reference_id": "TXN123",
                "tags": ["online", "shopping"]
            }
        }


class TransactionResponse(BaseModel):
    id: str
    user_id: str
    amount: Decimal
    currency: str
    transaction_date: datetime
    description: str
    merchant: Optional[str]
    category: Optional[str]
    subcategory: Optional[str]
    bank: Optional[str]
    account_type: Optional[str]
    transaction_type: TransactionType
    reference_id: Optional[str]
    status: TransactionStatus
    tags: List[str]
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True


class TransactionListResponse(BaseModel):
    data: List[TransactionResponse]
    total: int
    skip: int
    limit: int


class TransactionStatsResponse(BaseModel):
    period: str
    total_debit: Decimal
    total_credit: Decimal
    net_amount: Decimal
    transaction_count: int
    average_transaction: Decimal
    top_category: Optional[str]
    top_merchant: Optional[str]

