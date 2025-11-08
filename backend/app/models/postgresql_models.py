from sqlalchemy import Column, String, Float, DateTime, Boolean, Text, ForeignKey, Integer, Enum as SQLEnum
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from datetime import datetime
import enum

Base = declarative_base()


class TransactionType(str, enum.Enum):
    DEBIT = "debit"
    CREDIT = "credit"


class TransactionStatus(str, enum.Enum):
    PENDING = "pending"
    CLEARED = "cleared"
    FAILED = "failed"


class Transaction(Base):
    __tablename__ = "transactions"
    
    id = Column(String, primary_key=True)
    user_id = Column(String, nullable=False, index=True)
    amount = Column(Float, nullable=False)
    currency = Column(String, default="INR")
    transaction_date = Column(DateTime, nullable=False, index=True)
    description = Column(Text)
    merchant = Column(String)
    category = Column(String, index=True)
    subcategory = Column(String)
    bank = Column(String)
    account_type = Column(String)
    transaction_type = Column(SQLEnum(TransactionType), nullable=False, index=True)
    reference_id = Column(String, unique=True)
    status = Column(SQLEnum(TransactionStatus), default=TransactionStatus.CLEARED)
    tags = Column(Text)  # JSON array of tags
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    budgets = relationship("Budget", secondary="budget_transactions", back_populates="transactions")
    enrichment = relationship("TransactionEnriched", back_populates="transaction", uselist=False)
    overrides = relationship("TransactionOverride", back_populates="transaction", uselist=False)


class Budget(Base):
    __tablename__ = "budgets"
    
    id = Column(String, primary_key=True)
    user_id = Column(String, nullable=False, index=True)
    name = Column(String, nullable=False)
    category = Column(String)
    amount = Column(Float, nullable=False)
    period = Column(String)  # monthly, weekly, yearly
    start_date = Column(DateTime, nullable=False)
    end_date = Column(DateTime, nullable=False)
    current_spent = Column(Float, default=0.0)
    is_active = Column(Boolean, default=True)
    alert_threshold = Column(Float, default=0.8)  # Alert at 80% of budget
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    transactions = relationship("Transaction", secondary="budget_transactions", back_populates="budgets")


class BudgetTransaction(Base):
    __tablename__ = "budget_transactions"
    
    budget_id = Column(String, ForeignKey("budgets.id"), primary_key=True)
    transaction_id = Column(String, ForeignKey("transactions.id"), primary_key=True)


class Category(Base):
    __tablename__ = "categories"
    
    id = Column(String, primary_key=True)
    user_id = Column(String, nullable=False, index=True)
    name = Column(String, nullable=False)
    parent_category = Column(String)  # For subcategories
    color = Column(String)  # Hex color for UI
    icon = Column(String)  # Icon name
    created_at = Column(DateTime, default=datetime.utcnow)


class Insight(Base):
    __tablename__ = "insights"
    
    id = Column(String, primary_key=True)
    user_id = Column(String, nullable=False, index=True)
    insight_type = Column(String)  # spending_pattern, trend, recommendation
    title = Column(String, nullable=False)
    description = Column(Text)
    data = Column(Text)  # JSON data
    category = Column(String)
    period = Column(String)  # daily, weekly, monthly
    created_at = Column(DateTime, default=datetime.utcnow, index=True)
    is_read = Column(Boolean, default=False)


class Goal(Base):
    __tablename__ = "goals"
    
    id = Column(String, primary_key=True)
    user_id = Column(String, nullable=False, index=True)
    name = Column(String, nullable=False)
    target_amount = Column(Float, nullable=False)
    current_amount = Column(Float, default=0.0)
    deadline = Column(DateTime)
    category = Column(String)
    is_completed = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

