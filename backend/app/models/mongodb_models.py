from datetime import datetime
from typing import Optional, Dict, Any
from pydantic import BaseModel, Field


class RawEmailData(BaseModel):
    """Raw email data from Gmail"""
    message_id: str
    thread_id: str
    subject: str
    sender: str
    date: datetime
    body: str
    attachments: list[Dict[str, Any]] = Field(default_factory=list)
    user_id: str
    fetched_at: datetime = Field(default_factory=datetime.utcnow)
    processed: bool = False


class RawTransactionData(BaseModel):
    """Raw transaction data from various sources"""
    transaction_id: str
    source: str  # email, sms, upload
    source_type: str  # gmail, bank_api, manual
    raw_data: Dict[str, Any]
    file_type: Optional[str] = None  # pdf, csv, json
    user_id: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    processed: bool = False


class ParsedTransaction(BaseModel):
    """Parsed transaction before cleaning"""
    raw_id: str
    amount: float
    currency: str = "INR"
    transaction_date: datetime
    description: str
    merchant: Optional[str] = None
    category: Optional[str] = None
    bank: Optional[str] = None
    account_type: Optional[str] = None
    transaction_type: str  # debit, credit
    reference_id: Optional[str] = None
    user_id: str
    confidence_score: float = 0.0  # ML confidence


class MLTrainingData(BaseModel):
    """Data for ML training and analysis"""
    transaction_id: str
    amount: float
    category: str
    merchant: str
    date: datetime
    day_of_week: int
    day_of_month: int
    month: int
    user_id: str
    user_category: Optional[str] = None  # User's manual categorization


class AnomalyDetection(BaseModel):
    """Anomaly detection results"""
    transaction_id: str
    anomaly_type: str  # unusual_amount, unusual_category, unusual_time, etc.
    anomaly_score: float
    description: str
    detected_at: datetime = Field(default_factory=datetime.utcnow)

