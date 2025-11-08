"""
Enrichment Models
Immutable enrichment snapshots and user overrides
"""
from sqlalchemy import Column, String, Integer, DateTime, Text, Float, ForeignKey, JSON, Boolean
from sqlalchemy.orm import relationship
from datetime import datetime
from app.models.postgresql_models import Base
import enum


class EnrichmentClassification(str, enum.Enum):
    INCOME = "income"
    NEEDS = "needs"
    WANTS = "wants"
    ASSETS = "assets"
    UNCATEGORIZED = "unlabeled"


class TransactionEnriched(Base):
    """
    Immutable enrichment snapshot (1:1 with transaction)
    Stores rule-based classification results
    """
    __tablename__ = "txn_enriched"
    
    id = Column(String, primary_key=True)
    transaction_id = Column(String, ForeignKey("transactions.id"), unique=True, nullable=False, index=True)
    user_id = Column(String, nullable=False, index=True)
    
    # Classification results
    merchant = Column(String)
    subcategory = Column(String)
    category = Column(String)
    
    # Transaction type classification
    classification = Column(String)  # 'income', 'needs', 'wants', 'assets'
    transaction_type_detected = Column(String)  # 'debit' or 'credit'
    
    # Raw data for reference
    original_description = Column(Text)
    original_amount = Column(Float)
    
    # Enrichment metadata
    enrichment_confidence = Column(Float, default=0.0)  # 0-1
    enrichment_rules_applied = Column(JSON)  # List of rule IDs that matched
    enrichment_timestamp = Column(DateTime, default=datetime.utcnow)
    enrichment_version = Column(String, default="1.0")  # For future rule updates
    
    # Audit
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationship to transaction (would need to be defined in postgresql_models.py)
    transaction = relationship("Transaction", foreign_keys=[transaction_id])


class TransactionOverride(Base):
    """
    User edits to enrichment classifications
    Allows users to correct/change automatic classifications
    """
    __tablename__ = "txn_override"
    
    id = Column(String, primary_key=True)
    transaction_id = Column(String, ForeignKey("transactions.id"), unique=True, nullable=False, index=True)
    user_id = Column(String, nullable=False, index=True)
    
    # Override fields (any field can be overridden)
    merchant_override = Column(String)
    subcategory_override = Column(String)
    category_override = Column(String)
    classification_override = Column(String)  # 'income', 'needs', 'wants', 'assets'
    
    # Reason for override
    override_reason = Column(Text)
    override_confidence = Column(Float, default=1.0)
    
    # Audit
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationship to transaction
    transaction = relationship("Transaction", foreign_keys=[transaction_id])


class EnrichmentRule(Base):
    """
    User-defined enrichment rules
    Supports priority-based matching
    """
    __tablename__ = "enrichment_rules"
    
    id = Column(String, primary_key=True)
    user_id = Column(String, nullable=False, index=True)
    
    # Rule configuration
    name = Column(String, nullable=False)
    priority = Column(Integer, default=100, index=True)  # Lower = higher priority
    is_active = Column(Boolean, default=True)
    
    # Matching criteria
    merchant_regex = Column(String)
    description_regex = Column(String)
    amount_min = Column(Float)
    amount_max = Column(Float)
    
    # Classification result
    category = Column(String, nullable=False)
    subcategory = Column(String)
    classification = Column(String)  # 'income', 'needs', 'wants', 'assets'
    
    # Metadata
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    class Config:
        indexes = [('user_id', 'priority')]


class EnrichmentTag(Base):
    """
    Tags for transactions (user-defined labels)
    """
    __tablename__ = "enrichment_tags"
    
    id = Column(String, primary_key=True)
    transaction_id = Column(String, ForeignKey("transactions.id"), index=True)
    user_id = Column(String, nullable=False, index=True)
    
    tag_name = Column(String, nullable=False)
    tag_color = Column(String)  # Hex color for UI
    
    created_at = Column(DateTime, default=datetime.utcnow)

