"""
SpendSense PostgreSQL Models
Matching the SQL schema from 001_spendsense_schema.sql
"""
from sqlalchemy import (
    Column, String, Integer, Numeric, Date, DateTime, Boolean, Text, 
    ForeignKey, SmallInteger, Index, CheckConstraint, UniqueConstraint, PrimaryKeyConstraint, text
)
from sqlalchemy.dialects.postgresql import UUID, JSONB, TIMESTAMP
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from datetime import datetime

Base = declarative_base()


# ============================================================================
# 1) Batches & Staging
# ============================================================================
class UploadBatch(Base):
    """Upload batch tracking"""
    __tablename__ = "upload_batch"
    __table_args__ = (
        CheckConstraint("source_type IN ('manual','email','file')", name='check_source_type'),
        CheckConstraint("status IN ('received','parsed','failed','loaded')", name='check_status'),
        {'schema': 'spendsense'},
    )
    
    upload_id = Column(UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
    user_id = Column(UUID(as_uuid=True), nullable=False)
    source_type = Column(String(16), nullable=False)  # 'manual','email','file'
    file_name = Column(String(255))
    received_at = Column(TIMESTAMP(timezone=True), nullable=False, server_default=text("NOW()"))
    status = Column(String(16), nullable=False, server_default="'received'")  # 'received','parsed','failed','loaded'
    total_records = Column(Integer, nullable=False, server_default="0")
    parsed_records = Column(Integer, nullable=False, server_default="0")
    error_json = Column(JSONB, nullable=False, server_default=text("'{}'::jsonb"))


class TxnStaging(Base):
    """Staging table for raw transaction data"""
    __tablename__ = "txn_staging"
    __table_args__ = (
        CheckConstraint("direction IN ('debit','credit')", name='check_direction'),
        Index('idx_txn_staging_upload_id', 'upload_id'),
        Index('idx_txn_staging_user_id', 'user_id'),
        {'schema': 'spendsense'},
    )
    
    staging_id = Column(UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
    upload_id = Column(UUID(as_uuid=True), ForeignKey("spendsense.upload_batch.upload_id", ondelete="CASCADE"), nullable=False)
    user_id = Column(UUID(as_uuid=True), nullable=False)
    raw_txn_id = Column(String(128))
    txn_date = Column(Date, nullable=False)
    description_raw = Column(Text)
    amount = Column(Numeric(14, 2), nullable=False)
    direction = Column(String(8), nullable=False)  # 'debit','credit'
    currency = Column(String(3), nullable=False, server_default="'INR'")
    merchant_raw = Column(String(255))
    account_ref = Column(String(64))
    parsed_ok = Column(Boolean, nullable=False, server_default="TRUE")
    parse_error = Column(Text)
    parsed_event_oid = Column(String(64))  # MongoDB ObjectId for lineage
    created_at = Column(TIMESTAMP(timezone=True), nullable=False, server_default=text("NOW()"))


# ============================================================================
# 2) Dimensions & Reference
# ============================================================================
class DimCategory(Base):
    """Category dimension table"""
    __tablename__ = "dim_category"
    __table_args__ = (
        CheckConstraint("txn_type IN ('income','needs','wants','assets')", name='check_txn_type'),
        {'schema': 'spendsense'},
    )
    
    category_code = Column(String(32), primary_key=True)
    category_name = Column(String(64), nullable=False)
    txn_type = Column(String(12), nullable=False)  # 'income','needs','wants','assets'
    display_order = Column(SmallInteger, nullable=False, server_default="100")
    active = Column(Boolean, nullable=False, server_default="TRUE")


class DimSubcategory(Base):
    """Subcategory dimension table"""
    __tablename__ = "dim_subcategory"
    __table_args__ = ({'schema': 'spendsense'},)
    
    subcategory_code = Column(String(48), primary_key=True)
    category_code = Column(String(32), ForeignKey("spendsense.dim_category.category_code", onupdate="CASCADE"), nullable=False)
    subcategory_name = Column(String(80), nullable=False)
    display_order = Column(SmallInteger, nullable=False, server_default="100")
    active = Column(Boolean, nullable=False, server_default="TRUE")
    
    # Relationship
    category = relationship("DimCategory")


class DimMerchant(Base):
    """Merchant dimension table"""
    __tablename__ = "dim_merchant"
    __table_args__ = (
        Index('idx_merchant_normalized_name', 'normalized_name'),
        {'schema': 'spendsense'},
    )
    
    merchant_id = Column(UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
    merchant_name = Column(String(128), nullable=False)
    normalized_name = Column(String(128), nullable=False, unique=True)
    website = Column(String(255))
    active = Column(Boolean, nullable=False, server_default="TRUE")


class AppEvent(Base):
    """Application event logging"""
    __tablename__ = "app_events"
    __table_args__ = ({'schema': 'spendsense'},)
    
    event_id = Column(UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
    user_id = Column(UUID(as_uuid=True))
    event_name = Column(String(64), nullable=False)
    event_props = Column(JSONB, nullable=False, server_default=text("'{}'::jsonb"))
    created_at = Column(TIMESTAMP(timezone=True), nullable=False, server_default=text("NOW()"))


class APIRequestLog(Base):
    """API request logging"""
    __tablename__ = "api_request_log"
    __table_args__ = ({'schema': 'spendsense'},)
    
    req_id = Column(UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
    api_name = Column(String(64), nullable=False)
    user_id = Column(UUID(as_uuid=True))
    status_code = Column(Integer, nullable=False)
    latency_ms = Column(Integer, nullable=False)
    req_payload = Column(JSONB, nullable=False, server_default=text("'{}'::jsonb"))
    res_payload = Column(JSONB, nullable=False, server_default=text("'{}'::jsonb"))
    created_at = Column(TIMESTAMP(timezone=True), nullable=False, server_default=text("NOW()"))


class IntegrationEvent(Base):
    """Integration event tracking"""
    __tablename__ = "integration_events"
    __table_args__ = (
        CheckConstraint("status IN ('pending','success','failed')", name='check_integ_status'),
        {'schema': 'spendsense'},
    )
    
    integ_id = Column(UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
    from_module = Column(String(32), nullable=False)
    to_module = Column(String(32), nullable=False)
    ref_id = Column(UUID(as_uuid=True))
    status = Column(String(16), nullable=False)  # 'pending','success','failed'
    info = Column(JSONB, nullable=False, server_default=text("'{}'::jsonb"))
    created_at = Column(TIMESTAMP(timezone=True), nullable=False, server_default=text("NOW()"))


# ============================================================================
# 3) Rule Engine Metadata
# ============================================================================
class MerchantRule(Base):
    """Merchant matching rules"""
    __tablename__ = "merchant_rules"
    __table_args__ = (
        CheckConstraint("applies_to IN ('merchant','description')", name='check_applies_to'),
        CheckConstraint("txn_type_override IS NULL OR txn_type_override IN ('income','needs','wants','assets')", name='check_txn_type_override'),
        CheckConstraint("source IN ('learned','seed','ops')", name='check_source'),
        Index('idx_rules_active_pri', 'active', 'priority'),
        Index('ix_rules_scope', 'tenant_id', 'applies_to', 'active'),
        {'schema': 'spendsense'},
    )
    
    rule_id = Column(UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
    priority = Column(SmallInteger, nullable=False, server_default="100")
    applies_to = Column(String(16), nullable=False)  # 'merchant','description'
    pattern_regex = Column(Text, nullable=False)
    pattern_hash = Column(String(40))  # SHA1 hash of pattern_regex for deduplication
    category_code = Column(String(32), ForeignKey("spendsense.dim_category.category_code"))
    subcategory_code = Column(String(48), ForeignKey("spendsense.dim_subcategory.subcategory_code"))
    txn_type_override = Column(String(12))  # 'income','needs','wants','assets'
    created_by = Column(UUID(as_uuid=True))  # User who created this rule (for learned rules)
    tenant_id = Column(UUID(as_uuid=True))  # Optional tenant isolation (NULL = global rule)
    source = Column(String(16), nullable=False, server_default="'seed'")  # 'learned' | 'seed' | 'ops'
    notes = Column(Text)  # Optional notes
    active = Column(Boolean, nullable=False, server_default="TRUE")
    created_at = Column(TIMESTAMP(timezone=True), nullable=False, server_default=text("NOW()"))


# ============================================================================
# 4) Canonical Transactions (Fact)
# ============================================================================
class TxnFact(Base):
    """Transaction fact table (canonical)"""
    __tablename__ = "txn_fact"
    __table_args__ = (
        CheckConstraint("source_type IN ('manual','email','file')", name='check_source_type'),
        CheckConstraint("direction IN ('debit','credit')", name='check_direction'),
        Index('idx_txn_fact_user_date', 'user_id', 'txn_date'),
        Index('idx_txn_fact_user_id', 'user_id'),
        Index('idx_txn_fact_merchant', 'merchant_id'),
        {'schema': 'spendsense'},
    )
    
    txn_id = Column(UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
    user_id = Column(UUID(as_uuid=True), nullable=False)
    upload_id = Column(UUID(as_uuid=True), ForeignKey("spendsense.upload_batch.upload_id", ondelete="SET NULL"), nullable=False)
    source_type = Column(String(16), nullable=False)  # 'manual','email','file'
    account_ref = Column(String(64))
    txn_external_id = Column(String(128))
    txn_date = Column(Date, nullable=False)
    description = Column(Text)
    amount = Column(Numeric(14, 2), nullable=False)
    direction = Column(String(8), nullable=False)  # 'debit','credit'
    currency = Column(String(3), nullable=False, server_default="'INR'")
    merchant_id = Column(UUID(as_uuid=True), ForeignKey("spendsense.dim_merchant.merchant_id"))
    merchant_name_norm = Column(String(128))
    parsed_event_oid = Column(String(64))  # MongoDB ObjectId for lineage
    created_at = Column(TIMESTAMP(timezone=True), nullable=False, server_default=text("NOW()"))


# ============================================================================
# 5) Enrichment (Immutable per load)
# ============================================================================
class TxnEnriched(Base):
    """Transaction enrichment (immutable)"""
    __tablename__ = "txn_enriched"
    __table_args__ = (
        CheckConstraint("txn_type IS NULL OR txn_type IN ('income','needs','wants','assets')", name='check_txn_type'),
        Index('idx_txn_enriched_txn_id', 'txn_id'),
        {'schema': 'spendsense'},
    )
    
    enrich_id = Column(UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
    txn_id = Column(UUID(as_uuid=True), ForeignKey("spendsense.txn_fact.txn_id", ondelete="CASCADE"), nullable=False, unique=True)
    matched_rule_id = Column(UUID(as_uuid=True), ForeignKey("spendsense.merchant_rules.rule_id"))
    category_code = Column(String(32), ForeignKey("spendsense.dim_category.category_code"))
    subcategory_code = Column(String(48), ForeignKey("spendsense.dim_subcategory.subcategory_code"))
    txn_type = Column(String(12))  # 'income','needs','wants','assets'
    rule_confidence = Column(Numeric(4, 2), nullable=False, server_default="0.80")
    enriched_at = Column(TIMESTAMP(timezone=True), nullable=False, server_default=text("NOW()"))
    
    # Relationships
    txn_fact = relationship("TxnFact", foreign_keys=[txn_id])
    matched_rule = relationship("MerchantRule", foreign_keys=[matched_rule_id])


# ============================================================================
# 6) User Overrides (Latest wins)
# ============================================================================
class TxnOverride(Base):
    """User overrides for transaction classification"""
    __tablename__ = "txn_override"
    __table_args__ = (
        CheckConstraint("txn_type IS NULL OR txn_type IN ('income','needs','wants','assets')", name='check_txn_type'),
        Index('idx_override_txn_time', 'txn_id', 'created_at'),
        Index('idx_override_user_id', 'user_id'),
        {'schema': 'spendsense'},
    )
    
    override_id = Column(UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
    txn_id = Column(UUID(as_uuid=True), ForeignKey("spendsense.txn_fact.txn_id", ondelete="CASCADE"), nullable=False)
    user_id = Column(UUID(as_uuid=True), nullable=False)
    category_code = Column(String(32), ForeignKey("spendsense.dim_category.category_code"))
    subcategory_code = Column(String(48), ForeignKey("spendsense.dim_subcategory.subcategory_code"))
    txn_type = Column(String(12))  # 'income','needs','wants','assets'
    reason = Column(Text)
    created_at = Column(TIMESTAMP(timezone=True), nullable=False, server_default=text("NOW()"))
    
    # Relationships
    txn_fact = relationship("TxnFact", foreign_keys=[txn_id])


# ============================================================================
# 10) KPI Aggregation Tables
# ============================================================================
class KPITypeSplitDaily(Base):
    """Daily type split KPIs"""
    __tablename__ = "kpi_type_split_daily"
    __table_args__ = ({'schema': 'spendsense'},)
    
    user_id = Column(UUID(as_uuid=True), nullable=False, primary_key=True)
    dt = Column(Date, nullable=False, primary_key=True)
    income_amt = Column(Numeric(14, 2), nullable=False, server_default="0")
    needs_amt = Column(Numeric(14, 2), nullable=False, server_default="0")
    wants_amt = Column(Numeric(14, 2), nullable=False, server_default="0")
    assets_amt = Column(Numeric(14, 2), nullable=False, server_default="0")
    created_at = Column(TIMESTAMP(timezone=True), nullable=False, server_default=text("NOW()"))


class KPITypeSplitMonthly(Base):
    """Monthly type split KPIs"""
    __tablename__ = "kpi_type_split_monthly"
    __table_args__ = ({'schema': 'spendsense'},)
    
    user_id = Column(UUID(as_uuid=True), nullable=False, primary_key=True)
    month = Column(Date, nullable=False, primary_key=True)  # first of month
    income_amt = Column(Numeric(14, 2), nullable=False, server_default="0")
    needs_amt = Column(Numeric(14, 2), nullable=False, server_default="0")
    wants_amt = Column(Numeric(14, 2), nullable=False, server_default="0")
    assets_amt = Column(Numeric(14, 2), nullable=False, server_default="0")
    created_at = Column(TIMESTAMP(timezone=True), nullable=False, server_default=text("NOW()"))


class KPICategoryMonthly(Base):
    """Monthly category KPIs"""
    __tablename__ = "kpi_category_monthly"
    __table_args__ = ({'schema': 'spendsense'},)
    
    user_id = Column(UUID(as_uuid=True), nullable=False, primary_key=True)
    month = Column(Date, nullable=False, primary_key=True)
    category_code = Column(String(32), nullable=False, primary_key=True)
    spend_amt = Column(Numeric(14, 2), nullable=False, server_default="0")


class KPISpendingLeaksMonthly(Base):
    """Monthly spending leaks KPI"""
    __tablename__ = "kpi_spending_leaks_monthly"
    __table_args__ = ({'schema': 'spendsense'},)
    
    user_id = Column(UUID(as_uuid=True), nullable=False, primary_key=True)
    month = Column(Date, nullable=False, primary_key=True)
    rank = Column(SmallInteger, nullable=False, primary_key=True)
    category_code = Column(String(32), nullable=False)
    leak_amt = Column(Numeric(14, 2), nullable=False, server_default="0")


class KPIRecurringMerchantsMonthly(Base):
    """Monthly recurring merchants KPI"""
    __tablename__ = "kpi_recurring_merchants_monthly"
    __table_args__ = ({'schema': 'spendsense'},)
    
    user_id = Column(UUID(as_uuid=True), nullable=False, primary_key=True)
    month = Column(Date, nullable=False, primary_key=True)
    merchant_name_norm = Column(String(128), nullable=False, primary_key=True)
    txn_count = Column(Integer, nullable=False)
    total_amt = Column(Numeric(14, 2), nullable=False, server_default="0")

