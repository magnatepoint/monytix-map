-- =========================================================
-- Add Dedupe Fingerprint and Performance Indexes
-- 1. Add dedupe_fp column and function
-- 2. Create unique index for duplicate prevention
-- 3. Add performance indexes for hot paths
-- =========================================================

BEGIN;

-- ---------- DEDUPE FINGERPRINT ----------

-- Add dedupe_fp column if not exists
ALTER TABLE spendsense.txn_fact
ADD COLUMN IF NOT EXISTS dedupe_fp text;

-- Create fingerprint function
CREATE OR REPLACE FUNCTION spendsense.fn_txn_fact_fp(
    p_user uuid, 
    p_date date, 
    p_amt numeric, 
    p_dir text, 
    p_desc text, 
    p_merch text, 
    p_acct text
) RETURNS text LANGUAGE sql IMMUTABLE AS $$
SELECT encode(
  digest(
    coalesce(p_user::text,'') || '|' ||
    coalesce(p_date::text,'') || '|' ||
    coalesce(trim(to_char(p_amt, 'FM9999999990.00')),'') || '|' ||
    coalesce(lower(p_dir),'') || '|' ||
    coalesce(lower(regexp_replace(p_desc,'\s+',' ','g')),'') || '|' ||
    coalesce(lower(p_merch),'') || '|' ||
    coalesce(lower(p_acct),'')
  , 'sha1'), 'hex');
$$;

COMMENT ON FUNCTION spendsense.fn_txn_fact_fp IS 'Generate dedupe fingerprint for transactions';

-- Create unique index on dedupe_fp
CREATE UNIQUE INDEX IF NOT EXISTS ux_txn_fact_dedupe_fp
ON spendsense.txn_fact(dedupe_fp)
WHERE dedupe_fp IS NOT NULL;

-- Backfill existing rows (optional, but recommended)
UPDATE spendsense.txn_fact
SET dedupe_fp = spendsense.fn_txn_fact_fp(
    user_id,
    txn_date,
    amount,
    direction,
    COALESCE(description, ''),
    COALESCE(merchant_name_norm, ''),
    COALESCE(account_ref::text, '')
)
WHERE dedupe_fp IS NULL;

-- ---------- PERFORMANCE INDEXES ----------

-- Staging hot paths
CREATE INDEX IF NOT EXISTS ix_txn_staging_user 
ON spendsense.txn_staging(user_id);

CREATE INDEX IF NOT EXISTS ix_txn_staging_user_date 
ON spendsense.txn_staging(user_id, txn_date);

CREATE INDEX IF NOT EXISTS ix_txn_staging_upload 
ON spendsense.txn_staging(upload_id);

CREATE INDEX IF NOT EXISTS ix_txn_staging_parsed 
ON spendsense.txn_staging(parsed_ok) 
WHERE parsed_ok = true;

-- Enriched lookups
CREATE INDEX IF NOT EXISTS ix_txn_enriched_txn 
ON spendsense.txn_enriched(txn_id);

CREATE INDEX IF NOT EXISTS ix_txn_enriched_cat 
ON spendsense.txn_enriched(category_code, subcategory_code)
WHERE category_code IS NOT NULL;

-- Fact queries (lists / dashboards)
CREATE INDEX IF NOT EXISTS ix_txn_fact_user_date 
ON spendsense.txn_fact(user_id, txn_date DESC);

CREATE INDEX IF NOT EXISTS ix_txn_fact_user_amt_dir 
ON spendsense.txn_fact(user_id, amount, direction);

CREATE INDEX IF NOT EXISTS ix_txn_fact_user_dir 
ON spendsense.txn_fact(user_id, direction)
WHERE direction IN ('debit', 'credit');

COMMIT;

