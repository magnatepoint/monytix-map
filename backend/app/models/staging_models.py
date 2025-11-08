"""
Staging Models for ETL/ELT Pipeline
Supports batch tracking and data validation before production
"""
from sqlalchemy import Column, String, Integer, DateTime, Boolean, Text, JSON, Float, ForeignKey, Enum as SQLEnum
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from datetime import datetime
import enum

Base = declarative_base()


class UploadBatch(Base):
    """Tracks file upload batches"""
    __tablename__ = "upload_batches"
    
    id = Column(String, primary_key=True)
    user_id = Column(String, nullable=False, index=True)
    upload_type = Column(String)  # 'manual', 'csv', 'xlsx', 'pdf', 'gmail'
    file_name = Column(String)
    file_size = Column(Integer)
    total_records = Column(Integer, default=0)
    processed_records = Column(Integer, default=0)
    failed_records = Column(Integer, default=0)
    status = Column(String)  # 'uploaded', 'processing', 'completed', 'failed'
    error_summary = Column(Text)
    meta_info = Column(JSON)  # Additional info (renamed from metadata - SQLAlchemy reserved)
    created_at = Column(DateTime, default=datetime.utcnow)
    completed_at = Column(DateTime)


class TransactionStaging(Base):
    """Staging table for raw transaction data before validation"""
    __tablename__ = "txn_staging"
    
    id = Column(String, primary_key=True)
    upload_batch_id = Column(String, ForeignKey("upload_batches.id"), nullable=False, index=True)
    user_id = Column(String, nullable=False, index=True)
    
    # Raw data fields
    raw_amount = Column(String)  # As uploaded
    amount = Column(Float)  # Parsed/converted
    currency = Column(String, default="INR")
    
    raw_date = Column(String)  # As uploaded
    transaction_date = Column(DateTime)
    
    description = Column(Text)
    merchant = Column(String)
    category = Column(String)
    bank = Column(String)
    transaction_type = Column(String)
    
    reference_id = Column(String)
    
    # Status tracking
    validation_status = Column(String, default="pending")  # pending, valid, invalid
    validation_errors = Column(JSON)  # List of error messages
    processing_status = Column(String, default="pending")  # pending, processing, completed, failed
    
    # Processing metadata
    confidence_score = Column(Float, default=0.0)
    data_source = Column(String)  # manual, email, csv, pdf
    row_number = Column(Integer)  # For CSV/XLSX uploads
    
    # Audit fields
    created_at = Column(DateTime, default=datetime.utcnow)
    processed_at = Column(DateTime)
    error_at = Column(DateTime)
    error_message = Column(Text)


class GmailConnection(Base):
    """Gmail integration status and configuration"""
    __tablename__ = "gmail_connections"
    
    id = Column(String, primary_key=True)
    user_id = Column(String, nullable=False, index=True)  # Removed unique constraint
    email = Column(String(255))  # Email address for this account
    display_name = Column(String(255))  # Display name for the email account
    
    # OAuth credentials (encrypted)
    access_token = Column(Text)  # Encrypted
    refresh_token = Column(Text)  # Encrypted
    token_expires_at = Column(DateTime)
    
    # Status
    is_active = Column(Boolean, default=True)
    last_sync_at = Column(DateTime)
    last_email_id = Column(String)  # For incremental sync
    
    # Configuration
    sync_enabled = Column(Boolean, default=True)
    auto_categorize = Column(Boolean, default=True)
    fetch_frequency = Column(String, default="realtime")  # realtime, hourly, daily
    
    # Statistics
    total_emails_fetched = Column(Integer, default=0)
    total_transactions_extracted = Column(Integer, default=0)
    
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class BillReminder(Base):
    """Tracks bills and due dates from emails"""
    __tablename__ = "bill_reminders"
    
    id = Column(String, primary_key=True)
    user_id = Column(String, nullable=False, index=True)
    
    # Bill details
    bill_type = Column(String)  # electricity, water, credit_card, etc.
    merchant = Column(String, nullable=False)
    amount = Column(Float)
    currency = Column(String, default="INR")
    
    # Due date tracking
    due_date = Column(DateTime, nullable=False, index=True)
    is_paid = Column(Boolean, default=False)
    paid_at = Column(DateTime)
    paid_amount = Column(Float)
    
    # Source tracking
    source_email_id = Column(String)  # Link to gmail message
    source_provider = Column(String)  # BSNL, HDFC, etc.
    
    # Notification
    reminder_sent = Column(Boolean, default=False)
    reminder_days_before = Column(Integer)  # Days before due date
    
    # Metadata
    notes = Column(Text)
    category = Column(String)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class EmailTransaction(Base):
    """Extracted transactions from emails"""
    __tablename__ = "email_transactions"
    
    id = Column(String, primary_key=True)
    user_id = Column(String, nullable=False, index=True)
    gmail_message_id = Column(String, unique=True, index=True)
    
    # Email metadata
    email_subject = Column(String)
    email_sender = Column(String)
    email_date = Column(DateTime)
    
    # Transaction data
    amount = Column(Float, nullable=False)
    currency = Column(String, default="INR")
    transaction_date = Column(DateTime)
    description = Column(String)
    merchant = Column(String)
    bank = Column(String)
    
    # Extracted fields
    reference_id = Column(String)
    transaction_type = Column(String)  # debit, credit
    category = Column(String)
    
    # Status
    is_processed = Column(Boolean, default=False)
    processing_status = Column(String)
    
    # Audit
    extracted_at = Column(DateTime, default=datetime.utcnow)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationship to staging
    upload_batch_id = Column(String, ForeignKey("upload_batches.id"))

