-- ============================================================================
-- Monytix — SpendSense (MVP) : Full SQL Package
-- Version: 1.0
-- PostgreSQL 13+
-- ============================================================================
BEGIN;
CREATE EXTENSION IF NOT EXISTS pgcrypto;

-- Create spendsense schema
CREATE SCHEMA IF NOT EXISTS spendsense;

-- ============================================================================
-- 0) ENUMS & CHECKS (simple text + CHECK for portability)
-- ============================================================================
-- Direction: debit (money out), credit (money in)
-- Txn Type: income / needs / wants / assets
-- Source Type: manual / email / file
-- Status: received / parsed / failed / loaded
-- ============================================================================

-- ============================================================================
-- 1) Batches & Staging
-- ============================================================================
CREATE TABLE IF NOT EXISTS spendsense.upload_batch (
  upload_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID NOT NULL,
  source_type VARCHAR(16) NOT NULL CHECK (source_type IN ('manual','email','file')),
  file_name VARCHAR(255),
  received_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  status VARCHAR(16) NOT NULL DEFAULT 'received' CHECK (status IN ('received','parsed','failed','loaded')),
  total_records INTEGER NOT NULL DEFAULT 0,
  parsed_records INTEGER NOT NULL DEFAULT 0,
  error_json JSONB NOT NULL DEFAULT '{}'::jsonb
);

CREATE TABLE IF NOT EXISTS txn_staging (
  staging_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  upload_id UUID NOT NULL REFERENCES upload_batch(upload_id) ON DELETE CASCADE,
  user_id UUID NOT NULL,
  raw_txn_id VARCHAR(128),
  txn_date DATE NOT NULL,
  description_raw TEXT,
  amount NUMERIC(14,2) NOT NULL,
  direction VARCHAR(8) NOT NULL CHECK (direction IN ('debit','credit')),
  currency VARCHAR(3) NOT NULL DEFAULT 'INR',
  merchant_raw VARCHAR(255),
  account_ref VARCHAR(64),
  parsed_ok BOOLEAN NOT NULL DEFAULT TRUE,
  parse_error TEXT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ============================================================================
-- 2) Dimensions & Reference
-- ============================================================================
CREATE TABLE IF NOT EXISTS spendsense.dim_category (
  category_code VARCHAR(32) PRIMARY KEY,
  category_name VARCHAR(64) NOT NULL,
  txn_type VARCHAR(12) NOT NULL CHECK (txn_type IN ('income','needs','wants','assets')),
  display_order SMALLINT NOT NULL DEFAULT 100,
  active BOOLEAN NOT NULL DEFAULT TRUE
);

CREATE TABLE IF NOT EXISTS spendsense.dim_subcategory (
  subcategory_code VARCHAR(48) PRIMARY KEY,
  category_code VARCHAR(32) NOT NULL REFERENCES spendsense.dim_category(category_code) ON UPDATE CASCADE,
  subcategory_name VARCHAR(80) NOT NULL,
  display_order SMALLINT NOT NULL DEFAULT 100,
  active BOOLEAN NOT NULL DEFAULT TRUE
);

CREATE TABLE IF NOT EXISTS spendsense.dim_merchant (
  merchant_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  merchant_name VARCHAR(128) NOT NULL,
  normalized_name VARCHAR(128) NOT NULL,
  default_subcategory_code VARCHAR(48),
  default_category_code VARCHAR(32),
  website VARCHAR(255),
  active BOOLEAN NOT NULL DEFAULT TRUE,
  UNIQUE (normalized_name)
);

-- Optional telemetry
CREATE TABLE IF NOT EXISTS app_events (
  event_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID,
  event_name VARCHAR(64) NOT NULL,
  event_props JSONB NOT NULL DEFAULT '{}'::jsonb,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS api_request_log (
  req_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  api_name VARCHAR(64) NOT NULL,
  user_id UUID,
  status_code INTEGER NOT NULL,
  latency_ms INTEGER NOT NULL,
  req_payload JSONB NOT NULL DEFAULT '{}'::jsonb,
  res_payload JSONB NOT NULL DEFAULT '{}'::jsonb,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS integration_events (
  integ_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  from_module VARCHAR(32) NOT NULL,
  to_module VARCHAR(32) NOT NULL,
  ref_id UUID,
  status VARCHAR(16) NOT NULL CHECK (status IN ('pending','success','failed')),
  info JSONB NOT NULL DEFAULT '{}'::jsonb,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ============================================================================
-- 3) Rule Engine Metadata
-- ============================================================================
CREATE TABLE IF NOT EXISTS spendsense.merchant_rules (
  rule_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  priority SMALLINT NOT NULL DEFAULT 100, -- lower = earlier
  applies_to VARCHAR(16) NOT NULL CHECK (applies_to IN ('merchant','description')),
  pattern_regex TEXT NOT NULL, -- POSIX regex
  category_code VARCHAR(32) REFERENCES spendsense.dim_category(category_code),
  subcategory_code VARCHAR(48) REFERENCES spendsense.dim_subcategory(subcategory_code),
  txn_type_override VARCHAR(12) CHECK (txn_type_override IN ('income','needs','wants','assets')),
  active BOOLEAN NOT NULL DEFAULT TRUE,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_rules_active_pri ON spendsense.merchant_rules(active, priority);

-- ============================================================================
-- 4) Canonical Transactions (Fact)
-- ============================================================================
CREATE TABLE IF NOT EXISTS spendsense.txn_fact (
  txn_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID NOT NULL,
  upload_id UUID NOT NULL REFERENCES spendsense.upload_batch(upload_id) ON DELETE SET NULL,
  source_type VARCHAR(16) NOT NULL CHECK (source_type IN ('manual','email','file')),
  account_ref VARCHAR(64),
  txn_external_id VARCHAR(128),
  txn_date DATE NOT NULL,
  description TEXT,
  amount NUMERIC(14,2) NOT NULL,
  direction VARCHAR(8) NOT NULL CHECK (direction IN ('debit','credit')),
  currency VARCHAR(3) NOT NULL DEFAULT 'INR',
  merchant_id UUID REFERENCES spendsense.dim_merchant(merchant_id),
  merchant_name_norm VARCHAR(128),
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_txn_fact_user_date ON spendsense.txn_fact(user_id, txn_date);

-- Add unique index for deduplication (handles NULLs properly)
CREATE UNIQUE INDEX IF NOT EXISTS idx_txn_fact_dedup 
ON spendsense.txn_fact(user_id, txn_date, amount, direction) 
WHERE account_ref IS NOT NULL AND txn_external_id IS NOT NULL;

-- ============================================================================
-- 5) Enrichment (Immutable per load)
-- ============================================================================
CREATE TABLE IF NOT EXISTS spendsense.txn_enriched (
  enrich_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  txn_id UUID NOT NULL REFERENCES spendsense.txn_fact(txn_id) ON DELETE CASCADE,
  matched_rule_id UUID REFERENCES spendsense.merchant_rules(rule_id),
  category_code VARCHAR(32) REFERENCES spendsense.dim_category(category_code),
  subcategory_code VARCHAR(48) REFERENCES spendsense.dim_subcategory(subcategory_code),
  txn_type VARCHAR(12) CHECK (txn_type IN ('income','needs','wants','assets')),
  rule_confidence NUMERIC(4,2) NOT NULL DEFAULT 0.80,
  enriched_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  UNIQUE (txn_id)
);

-- ============================================================================
-- 6) User Overrides (Latest wins)
-- ============================================================================
CREATE TABLE IF NOT EXISTS spendsense.txn_override (
  override_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  txn_id UUID NOT NULL REFERENCES spendsense.txn_fact(txn_id) ON DELETE CASCADE,
  user_id UUID NOT NULL,
  category_code VARCHAR(32) REFERENCES spendsense.dim_category(category_code),
  subcategory_code VARCHAR(48) REFERENCES spendsense.dim_subcategory(subcategory_code),
  txn_type VARCHAR(12) CHECK (txn_type IN ('income','needs','wants','assets')),
  reason TEXT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_override_txn_time ON spendsense.txn_override(txn_id, created_at DESC);

-- ============================================================================
-- 7) Effective Enrichment View
-- ============================================================================
CREATE OR REPLACE VIEW spendsense.vw_txn_effective AS
WITH last_override AS (
  SELECT DISTINCT ON (o.txn_id)
    o.txn_id, o.category_code, o.subcategory_code, o.txn_type, o.created_at
  FROM spendsense.txn_override o
  ORDER BY o.txn_id, o.created_at DESC
)
SELECT
  f.txn_id,
  f.user_id,
  f.txn_date,
  f.amount,
  f.direction,
  f.currency,
  f.description,
  COALESCE(lo.category_code, e.category_code) AS category_code,
  COALESCE(lo.subcategory_code, e.subcategory_code) AS subcategory_code,
  -- Effective txn_type logic:
  CASE
    WHEN lo.txn_type IS NOT NULL THEN lo.txn_type
    WHEN e.txn_type IS NOT NULL THEN e.txn_type
    WHEN f.direction = 'credit' THEN 'income'
    ELSE (SELECT dc.txn_type FROM spendsense.dim_category dc WHERE dc.category_code = COALESCE(lo.category_code, e.category_code))
  END AS txn_type,
  f.merchant_id,
  f.merchant_name_norm
FROM spendsense.txn_fact f
LEFT JOIN spendsense.txn_enriched e ON e.txn_id = f.txn_id
LEFT JOIN last_override lo ON lo.txn_id = f.txn_id;

-- ============================================================================
-- 8) Seed Minimal Reference Data
-- ============================================================================
INSERT INTO spendsense.dim_category(category_code, category_name, txn_type, display_order, active) VALUES
  ('income','Income','income', 5, TRUE),
  ('utilities','Utilities','needs', 10, TRUE),
  ('rent','Rent','needs', 20, TRUE),
  ('groceries','Groceries','needs', 30, TRUE),
  ('dining','Dining','wants', 40, TRUE),
  ('shopping','Shopping','wants', 50, TRUE),
  ('travel','Travel','wants', 60, TRUE),
  ('investments','Investments','assets', 70, TRUE),
  ('savings','Savings','assets', 80, TRUE)
ON CONFLICT (category_code) DO NOTHING;

INSERT INTO spendsense.dim_subcategory(subcategory_code, category_code, subcategory_name, display_order, active) VALUES
  ('electricity','utilities','Electricity Bill',10,TRUE),
  ('water','utilities','Water Bill',20,TRUE),
  ('mobile','utilities','Mobile/Internet',30,TRUE),
  ('supermarket','groceries','Supermarket',10,TRUE),
  ('zomato','dining','Food Delivery',10,TRUE),
  ('restaurant','dining','Restaurant',20,TRUE),
  ('amazon','shopping','Online Shopping',10,TRUE),
  ('uber','travel','Cabs',10,TRUE),
  ('flight','travel','Flights',20,TRUE),
  ('recurring_deposit','savings','Recurring Deposit',10,TRUE)
ON CONFLICT (subcategory_code) DO NOTHING;

-- Some common merchants
INSERT INTO spendsense.dim_merchant(merchant_name, normalized_name, default_subcategory_code, default_category_code, website, active) VALUES
  ('Zomato','zomato','zomato','dining','https://www.zomato.com',TRUE),
  ('Swiggy','swiggy','zomato','dining','https://www.swiggy.com',TRUE),
  ('Amazon','amazon','amazon','shopping','https://www.amazon.in',TRUE),
  ('Uber','uber','uber','travel','https://www.uber.com',TRUE),
  ('Ola','ola','uber','travel','https://www.olacabs.com',TRUE)
ON CONFLICT (normalized_name) DO NOTHING;

-- Example rules (priority order)
INSERT INTO spendsense.merchant_rules(priority, applies_to, pattern_regex, category_code, subcategory_code, txn_type_override, active) VALUES
  (10,'merchant','(?i)zomato|swiggy','dining','zomato',NULL,TRUE),
  (20,'merchant','(?i)uber|ola','travel','uber',NULL,TRUE),
  (30,'description','(?i)electricity|power bill','utilities','electricity',NULL,TRUE),
  (40,'description','(?i)flight|air(?:line)?','travel','flight',NULL,TRUE),
  (50,'merchant','(?i)amazon','shopping','amazon',NULL,TRUE)
ON CONFLICT DO NOTHING;

-- ============================================================================
-- 9) Transformations (Example queries - use with specific parameters)
-- ============================================================================
-- These are example transformation queries to be run separately with parameters
-- For actual execution, replace :p_* variables with actual values

-- ============================================================================
-- 9.1 STAGING → FACT (Normalization & Dedupe)
-- Usage: Replace :p_upload_id with actual UUID
-- ============================================================================
/*
WITH s AS (
  SELECT *
  FROM spendsense.txn_staging
  WHERE upload_id = 'actual-upload-id-here'::uuid
),
norm AS (
  SELECT
    s.*,
    LOWER(COALESCE(TRIM(s.merchant_raw), '')) AS m_norm
  FROM s
),
m_match AS (
  SELECT n.*, dm.merchant_id, dm.normalized_name
  FROM norm n
  LEFT JOIN spendsense.dim_merchant dm
    ON dm.normalized_name = NULLIF(n.m_norm,'')
),
ins AS (
  INSERT INTO spendsense.txn_fact (
    user_id, upload_id, source_type, account_ref, txn_external_id, txn_date,
    description, amount, direction, currency, merchant_id, merchant_name_norm
  )
  SELECT
    m.user_id, m.upload_id, (SELECT source_type FROM spendsense.upload_batch ub WHERE ub.upload_id=m.upload_id),
    m.account_ref, m.raw_txn_id, m.txn_date,
    m.description_raw, m.amount, m.direction, m.currency, m.merchant_id, m.normalized_name
  FROM m_match m
  ON CONFLICT (user_id, COALESCE(account_ref,''), COALESCE(txn_external_id,''), txn_date, amount, direction) DO NOTHING
  RETURNING txn_id
)
UPDATE spendsense.upload_batch ub
SET status = 'loaded'
WHERE ub.upload_id = 'actual-upload-id-here'::uuid;
*/

-- ============================================================================
-- 9.2 FACT → ENRICHMENT (Rule Matching Order)
-- Usage: Replace :p_user_id, :p_date_from, :p_date_to with actual values
-- ============================================================================
/*
WITH candidates AS (
  SELECT f.*
  FROM spendsense.txn_fact f
  WHERE f.user_id = 'actual-user-id-here'::uuid
    AND f.txn_date >= '2025-01-01'::date
    AND f.txn_date <= '2025-12-31'::date
    AND NOT EXISTS (SELECT 1 FROM spendsense.txn_enriched e WHERE e.txn_id=f.txn_id)
),
rule_try AS (
  SELECT
    c.txn_id,
    r.rule_id,
    r.category_code,
    r.subcategory_code,
    r.txn_type_override,
    r.priority,
    CASE r.applies_to
      WHEN 'merchant' THEN (c.merchant_name_norm ~ r.pattern_regex)
      WHEN 'description' THEN (COALESCE(c.description,'') ~ r.pattern_regex)
    END AS is_match
  FROM candidates c
  JOIN spendsense.merchant_rules r ON r.active = TRUE
),
rule_rank AS (
  SELECT *
  FROM (
    SELECT
      rt.*,
      ROW_NUMBER() OVER (PARTITION BY rt.txn_id ORDER BY CASE WHEN rt.is_match THEN 0 ELSE 1 END, rt.priority ASC) AS rn
    FROM rule_try rt
  ) z
  WHERE z.rn = 1 -- best rule (matched earliest by priority; if none matched, this is the first non-match)
),
resolved AS (
  SELECT
    c.txn_id,
    CASE WHEN rr.is_match AND rr.category_code IS NOT NULL
      THEN rr.category_code
      ELSE COALESCE(dm.default_category_code, 'shopping') -- fallback
    END AS category_code,
    CASE WHEN rr.is_match AND rr.subcategory_code IS NOT NULL
      THEN rr.subcategory_code
      ELSE dm.default_subcategory_code
    END AS subcategory_code,
    CASE
      WHEN rr.is_match AND rr.txn_type_override IS NOT NULL THEN rr.txn_type_override
      WHEN c.direction = 'credit' THEN 'income'
      ELSE (SELECT dc.txn_type FROM spendsense.dim_category dc WHERE dc.category_code = (CASE WHEN rr.is_match AND rr.category_code IS NOT NULL
        THEN rr.category_code
        ELSE COALESCE(dm.default_category_code, 'shopping') END))
    END AS txn_type,
    CASE WHEN rr.is_match THEN rr.rule_id ELSE NULL END AS matched_rule_id
  FROM candidates c
  LEFT JOIN rule_rank rr ON rr.txn_id=c.txn_id
  LEFT JOIN spendsense.dim_merchant dm ON dm.merchant_id=c.merchant_id
)
INSERT INTO spendsense.txn_enriched (txn_id, matched_rule_id, category_code, subcategory_code, txn_type, rule_confidence, enriched_at)
SELECT
  r.txn_id, r.matched_rule_id, r.category_code, r.subcategory_code, r.txn_type, 0.90, NOW()
FROM resolved r
ON CONFLICT (txn_id) DO NOTHING;
*/

-- ============================================================================
-- 10) KPI Aggregation Tables
-- ============================================================================
-- 10.1 Daily/Monthly Type Split per User
CREATE TABLE IF NOT EXISTS spendsense.kpi_type_split_daily (
  user_id UUID NOT NULL,
  dt DATE NOT NULL,
  income_amt NUMERIC(14,2) NOT NULL DEFAULT 0,
  needs_amt NUMERIC(14,2) NOT NULL DEFAULT 0,
  wants_amt NUMERIC(14,2) NOT NULL DEFAULT 0,
  assets_amt NUMERIC(14,2) NOT NULL DEFAULT 0,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  PRIMARY KEY (user_id, dt)
);

CREATE TABLE IF NOT EXISTS spendsense.kpi_type_split_monthly (
  user_id UUID NOT NULL,
  month DATE NOT NULL, -- first of month
  income_amt NUMERIC(14,2) NOT NULL DEFAULT 0,
  needs_amt NUMERIC(14,2) NOT NULL DEFAULT 0,
  wants_amt NUMERIC(14,2) NOT NULL DEFAULT 0,
  assets_amt NUMERIC(14,2) NOT NULL DEFAULT 0,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  PRIMARY KEY (user_id, month)
);

-- 10.2 Monthly Categories per User
CREATE TABLE IF NOT EXISTS spendsense.kpi_category_monthly (
  user_id UUID NOT NULL,
  month DATE NOT NULL,
  category_code VARCHAR(32) NOT NULL,
  spend_amt NUMERIC(14,2) NOT NULL DEFAULT 0,
  PRIMARY KEY (user_id, month, category_code)
);

-- 10.3 Spending Leaks (Top Wants Categories) per User/Month
CREATE TABLE IF NOT EXISTS spendsense.kpi_spending_leaks_monthly (
  user_id UUID NOT NULL,
  month DATE NOT NULL,
  rank SMALLINT NOT NULL,
  category_code VARCHAR(32) NOT NULL,
  leak_amt NUMERIC(14,2) NOT NULL DEFAULT 0,
  PRIMARY KEY (user_id, month, rank)
);

-- 10.4 Recurring Merchants (Monthly)
CREATE TABLE IF NOT EXISTS spendsense.kpi_recurring_merchants_monthly (
  user_id UUID NOT NULL,
  month DATE NOT NULL,
  merchant_name_norm VARCHAR(128) NOT NULL,
  txn_count INTEGER NOT NULL,
  total_amt NUMERIC(14,2) NOT NULL DEFAULT 0,
  PRIMARY KEY (user_id, month, merchant_name_norm)
);

-- ============================================================================
-- 11) KPI Derivations (Daily/Monthly) - Example queries
-- These queries use psql variables and should be run with specific parameters
-- ============================================================================
/*
-- Usage example for KPI queries:
-- 1. Set variables: \set p_user_id 'user-uuid-here'
--                   \set p_month '2025-10-01'
--                   \set p_date_from '2025-10-01'
--                   \set p_date_to '2025-10-31'
-- 2. Then run the queries below

-- 11.1 Daily type split
WITH d AS (
  SELECT v.user_id,
    v.txn_date::date AS dt,
    SUM(CASE WHEN v.txn_type='income' AND v.direction='credit' THEN v.amount ELSE 0 END) AS income_amt,
    SUM(CASE WHEN v.txn_type='needs' AND v.direction='debit' THEN v.amount ELSE 0 END) AS needs_amt,
    SUM(CASE WHEN v.txn_type='wants' AND v.direction='debit' THEN v.amount ELSE 0 END) AS wants_amt,
    SUM(CASE WHEN v.txn_type='assets' AND v.direction='debit' THEN v.amount ELSE 0 END) AS assets_amt
  FROM spendsense.vw_txn_effective v
  WHERE v.user_id = '00000000-0000-0000-0000-000000000000'::uuid
    AND v.txn_date >= '2025-10-01'::date
    AND v.txn_date <= '2025-10-31'::date
  GROUP BY v.user_id, v.txn_date::date
)
INSERT INTO spendsense.kpi_type_split_daily(user_id, dt, income_amt, needs_amt, wants_amt, assets_amt)
SELECT user_id, dt, income_amt, needs_amt, wants_amt, assets_amt FROM d
ON CONFLICT (user_id, dt) DO UPDATE
SET income_amt = EXCLUDED.income_amt,
    needs_amt = EXCLUDED.needs_amt,
    wants_amt = EXCLUDED.wants_amt,
    assets_amt = EXCLUDED.assets_amt,
    created_at = NOW();

-- 11.2 Monthly type split
WITH m AS (
  SELECT v.user_id,
    date_trunc('month', v.txn_date)::date AS month,
    SUM(CASE WHEN v.txn_type='income' AND v.direction='credit' THEN v.amount ELSE 0 END) AS income_amt,
    SUM(CASE WHEN v.txn_type='needs' AND v.direction='debit' THEN v.amount ELSE 0 END) AS needs_amt,
    SUM(CASE WHEN v.txn_type='wants' AND v.direction='debit' THEN v.amount ELSE 0 END) AS wants_amt,
    SUM(CASE WHEN v.txn_type='assets' AND v.direction='debit' THEN v.amount ELSE 0 END) AS assets_amt
  FROM spendsense.vw_txn_effective v
  WHERE v.user_id = '00000000-0000-0000-0000-000000000000'::uuid
    AND date_trunc('month', v.txn_date)::date = date_trunc('month', '2025-10-01'::date)
  GROUP BY v.user_id, date_trunc('month', v.txn_date)
)
INSERT INTO spendsense.kpi_type_split_monthly(user_id, month, income_amt, needs_amt, wants_amt, assets_amt)
SELECT user_id, month, income_amt, needs_amt, wants_amt, assets_amt FROM m
ON CONFLICT (user_id, month) DO UPDATE
SET income_amt = EXCLUDED.income_amt,
    needs_amt = EXCLUDED.needs_amt,
    wants_amt = EXCLUDED.wants_amt,
    assets_amt = EXCLUDED.assets_amt,
    created_at = NOW();

-- 11.3 Monthly categories (debits only)
WITH c AS (
  SELECT v.user_id,
    date_trunc('month', v.txn_date)::date AS month,
    v.category_code,
    SUM(CASE WHEN v.direction='debit' THEN v.amount ELSE 0 END) AS spend_amt
  FROM spendsense.vw_txn_effective v
  WHERE v.user_id = '00000000-0000-0000-0000-000000000000'::uuid
    AND date_trunc('month', v.txn_date)::date = date_trunc('month', '2025-10-01'::date)
  GROUP BY v.user_id, date_trunc('month', v.txn_date), v.category_code
)
INSERT INTO spendsense.kpi_category_monthly(user_id, month, category_code, spend_amt)
SELECT user_id, month, category_code, spend_amt FROM c
ON CONFLICT (user_id, month, category_code) DO UPDATE
SET spend_amt = EXCLUDED.spend_amt;

-- 11.4 Spending leaks (Top wants categories per month)
WITH wants AS (
  SELECT k.user_id, k.month, k.category_code, k.spend_amt
  FROM spendsense.kpi_category_monthly k
  JOIN spendsense.dim_category dc ON dc.category_code=k.category_code AND dc.txn_type='wants'
  WHERE k.user_id = '00000000-0000-0000-0000-000000000000'::uuid
    AND k.month = date_trunc('month', '2025-10-01'::date)
),
rnk AS (
  SELECT w.*,
    ROW_NUMBER() OVER (PARTITION BY w.user_id, w.month ORDER BY w.spend_amt DESC) AS rn
  FROM wants w
)
INSERT INTO spendsense.kpi_spending_leaks_monthly(user_id, month, rank, category_code, leak_amt)
SELECT user_id, month, rn AS rank, category_code, spend_amt FROM rnk WHERE rn <= 3
ON CONFLICT (user_id, month, rank) DO UPDATE
SET category_code = EXCLUDED.category_code,
    leak_amt = EXCLUDED.leak_amt;

-- 11.5 Recurring merchants (same merchant 2+ times in month)
WITH rm AS (
  SELECT v.user_id,
    date_trunc('month', v.txn_date)::date AS month,
    COALESCE(v.merchant_name_norm, 'unknown') AS merchant_name_norm,
    COUNT(*) AS txn_count,
    SUM(CASE WHEN v.direction='debit' THEN v.amount ELSE 0 END) AS total_amt
  FROM spendsense.vw_txn_effective v
  WHERE v.user_id = '00000000-0000-0000-0000-000000000000'::uuid
    AND date_trunc('month', v.txn_date)::date = date_trunc('month', '2025-10-01'::date)
  GROUP BY v.user_id, date_trunc('month', v.txn_date), COALESCE(v.merchant_name_norm, 'unknown')
  HAVING COUNT(*) >= 2
)
INSERT INTO spendsense.kpi_recurring_merchants_monthly(user_id, month, merchant_name_norm, txn_count, total_amt)
SELECT user_id, month, merchant_name_norm, txn_count, total_amt FROM rm
ON CONFLICT (user_id, month, merchant_name_norm) DO UPDATE
SET txn_count = EXCLUDED.txn_count,
    total_amt = EXCLUDED.total_amt;
*/

-- ============================================================================
-- 12) Dashboard Views (Materialized)
-- ============================================================================
CREATE MATERIALIZED VIEW IF NOT EXISTS spendsense.mv_spendsense_dashboard_user_month AS
SELECT
  u.user_id,
  u.month,
  u.income_amt,
  u.needs_amt,
  u.wants_amt,
  u.assets_amt,
  -- ratios
  CASE WHEN u.income_amt>0 THEN ROUND(u.needs_amt/u.income_amt,2) ELSE NULL END AS needs_share,
  CASE WHEN u.income_amt>0 THEN ROUND(u.wants_amt/u.income_amt,2) ELSE NULL END AS wants_share,
  CASE WHEN u.income_amt>0 THEN ROUND(u.assets_amt/u.income_amt,2) ELSE NULL END AS assets_share
FROM spendsense.kpi_type_split_monthly u;
CREATE UNIQUE INDEX IF NOT EXISTS idx_mv_dash_user_month ON spendsense.mv_spendsense_dashboard_user_month(user_id, month);

CREATE MATERIALIZED VIEW IF NOT EXISTS spendsense.mv_spendsense_insights_user_month AS
SELECT
  l.user_id,
  l.month,
  jsonb_agg(jsonb_build_object('rank', l.rank, 'category_code', l.category_code, 'leak_amt', l.leak_amt)
    ORDER BY l.rank) AS top_leaks,
  (SELECT jsonb_agg(jsonb_build_object('merchant', r.merchant_name_norm, 'count', r.txn_count, 'amount', r.total_amt)
    ORDER BY r.txn_count DESC, r.total_amt DESC)
    FROM spendsense.kpi_recurring_merchants_monthly r
    WHERE r.user_id=l.user_id AND r.month=l.month) AS recurring_merchants
FROM spendsense.kpi_spending_leaks_monthly l
GROUP BY l.user_id, l.month;
CREATE UNIQUE INDEX IF NOT EXISTS idx_mv_insights_user_month ON spendsense.mv_spendsense_insights_user_month(user_id, month);

-- ============================================================================
-- 13) Refresh Helpers (run after daily ETL)
-- ============================================================================
-- REFRESH MATERIALIZED VIEW CONCURRENTLY spendsense.mv_spendsense_dashboard_user_month;
-- REFRESH MATERIALIZED VIEW CONCURRENTLY spendsense.mv_spendsense_insights_user_month;

COMMIT;

-- ============================================================================
-- HOW TO RUN (psql):
-- 1) Load staging rows and create an upload batch:
--    INSERT INTO spendsense.upload_batch(user_id, source_type, file_name, total_records) VALUES
--      ('aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa','file','oct.csv',100);
--    \set p_upload_id '<returned-upload_id>'
-- 2) Insert rows into spendsense.txn_staging with that upload_id.
-- 3) Normalize & load to fact: (Section 9.1 uses :p_upload_id)
-- 4) Enrich:
--    \set p_user_id 'aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa'
--    \set p_date_from '2025-10-01'
--    \set p_date_to '2025-10-31'
-- 5) KPIs:
--    \set p_month '2025-10-01'
--    \set p_date_from '2025-10-01'
--    \set p_date_to '2025-10-31'
-- 6) Refresh materialized views (12).
-- ============================================================================

