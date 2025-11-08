-- Migration: Add parsed_event_oid columns for MongoDB lineage tracking
-- This allows tracing PostgreSQL transactions back to MongoDB parsed_events

-- Add parsed_event_oid to txn_staging
ALTER TABLE spendsense.txn_staging
  ADD COLUMN IF NOT EXISTS parsed_event_oid text;

-- Add parsed_event_oid to txn_fact
ALTER TABLE spendsense.txn_fact
  ADD COLUMN IF NOT EXISTS parsed_event_oid text;

-- Create indexes for lineage queries
CREATE INDEX IF NOT EXISTS idx_txn_staging_parsed_event_oid 
  ON spendsense.txn_staging(parsed_event_oid);

CREATE INDEX IF NOT EXISTS idx_txn_fact_parsed_event_oid 
  ON spendsense.txn_fact(parsed_event_oid);

-- Add unique soft constraint (optional, for additional safety)
-- This prevents duplicates at PostgreSQL level even if dedupe_key fails
-- Note: txn_fact uses txn_external_id (not raw_txn_id)
CREATE UNIQUE INDEX IF NOT EXISTS idx_txn_fact_soft_dedup
  ON spendsense.txn_fact(
    user_id,
    txn_date,
    amount,
    direction,
    COALESCE(txn_external_id, ''),
    COALESCE(merchant_name_norm, '')
  )
  WHERE txn_external_id IS NOT NULL OR merchant_name_norm IS NOT NULL;

