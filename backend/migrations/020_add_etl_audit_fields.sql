-- =========================================================
-- Add ETL Audit Fields
-- Track how transactions were ingested for debugging
-- =========================================================

BEGIN;

-- Add audit fields to txn_fact
ALTER TABLE spendsense.txn_fact
  ADD COLUMN IF NOT EXISTS ingested_via text,
  ADD COLUMN IF NOT EXISTS raw_source_id uuid;

-- Add index on ingested_via for filtering
CREATE INDEX IF NOT EXISTS ix_txn_fact_ingested_via
ON spendsense.txn_fact(ingested_via)
WHERE ingested_via IS NOT NULL;

-- Add index on raw_source_id for tracking
CREATE INDEX IF NOT EXISTS ix_txn_fact_raw_source_id
ON spendsense.txn_fact(raw_source_id)
WHERE raw_source_id IS NOT NULL;

COMMENT ON COLUMN spendsense.txn_fact.ingested_via IS 'Source of ingestion: file, manual, etc.';
COMMENT ON COLUMN spendsense.txn_fact.raw_source_id IS 'Reference to upload_batch.upload_id';

COMMIT;

