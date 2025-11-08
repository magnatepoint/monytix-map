from pydantic import BaseModel, Field, field_validator, model_validator
from decimal import Decimal
from datetime import date, datetime
from typing import Optional
from enum import Enum


class BudgetPeriod(str, Enum):
    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"
    YEARLY = "yearly"


class BudgetStatus(str, Enum):
    ON_TRACK = "on_track"
    WARNING = "warning"
    EXCEEDED = "exceeded"


class BudgetCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    category: Optional[str] = Field(None, max_length=100)
    amount: Decimal = Field(..., gt=0, decimal_places=2)
    period: BudgetPeriod
    start_date: date
    end_date: date
    alert_threshold: float = Field(0.80, ge=0, le=1)
    
    @model_validator(mode='after')
    def validate_dates(self):
        if self.end_date <= self.start_date:
            raise ValueError("end_date must be after start_date")
        return self
    
    class Config:
        json_schema_extra = {
            "example": {
                "name": "Food Budget",
                "category": "Food & Dining",
                "amount": 15000.00,
                "period": "monthly",
                "start_date": "2024-01-01",
                "end_date": "2024-01-31",
                "alert_threshold": 0.80
            }
        }


class BudgetResponse(BaseModel):
    id: str
    user_id: str
    name: str
    category: Optional[str]
    amount: Decimal
    period: str
    start_date: date
    end_date: date
    current_spent: Decimal
    progress: float
    is_active: bool
    alert_threshold: float
    status: BudgetStatus
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True


class BudgetListResponse(BaseModel):
    data: list[BudgetResponse]


class BudgetStats(BaseModel):
    total_budgets: int
    active_budgets: int
    total_allocated: Decimal
    total_spent: Decimal
    avg_utilization: float

