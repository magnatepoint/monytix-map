-- =========================================================
-- Update Materialized Views to Exclude Transfers
-- Ensure KPI calculations exclude transfers category
-- =========================================================

BEGIN;

-- Check if materialized views exist and update them
-- Note: We need to DROP and recreate since we can't ALTER materialized views

-- Drop existing views if they exist
DROP MATERIALIZED VIEW IF EXISTS spendsense.mv_spendsense_dashboard_user_month;
DROP MATERIALIZED VIEW IF EXISTS spendsense.mv_spendsense_insights_user_month;

-- Recreate dashboard view with transfers exclusion
CREATE MATERIALIZED VIEW spendsense.mv_spendsense_dashboard_user_month AS
SELECT
    tf.user_id,
    date_trunc('month', tf.txn_date)::date AS month,
    SUM(CASE WHEN tf.direction = 'credit' THEN tf.amount ELSE 0 END) AS income_amt,
    SUM(CASE WHEN tf.direction = 'debit' 
             AND COALESCE(dc.txn_type,'wants') = 'needs' 
             AND COALESCE(te.category_code,'') <> 'transfers'
             THEN tf.amount ELSE 0 END) AS needs_amt,
    SUM(CASE WHEN tf.direction = 'debit' 
             AND COALESCE(dc.txn_type,'wants') = 'wants' 
             AND COALESCE(te.category_code,'') <> 'transfers'
             THEN tf.amount ELSE 0 END) AS wants_amt,
    SUM(CASE WHEN tf.direction = 'debit' 
             AND COALESCE(dc.txn_type,'wants') = 'assets' 
             AND COALESCE(te.category_code,'') <> 'transfers'
             THEN tf.amount ELSE 0 END) AS assets_amt,
    NOW() AS created_at
FROM spendsense.txn_fact tf
LEFT JOIN spendsense.txn_enriched te ON te.txn_id = tf.txn_id
LEFT JOIN spendsense.dim_category dc ON dc.category_code = te.category_code
WHERE COALESCE(te.category_code,'') <> 'transfers'
GROUP BY tf.user_id, date_trunc('month', tf.txn_date);

CREATE UNIQUE INDEX IF NOT EXISTS idx_mv_dash_user_month 
ON spendsense.mv_spendsense_dashboard_user_month(user_id, month);

-- Recreate insights view with transfers exclusion
CREATE MATERIALIZED VIEW spendsense.mv_spendsense_insights_user_month AS
SELECT
    tf.user_id,
    date_trunc('month', tf.txn_date)::date AS month,
    COALESCE(te.category_code,'others') AS category_code,
    COUNT(*) AS txn_count,
    SUM(CASE WHEN tf.direction = 'debit' THEN tf.amount ELSE 0 END) AS spend_amt,
    SUM(CASE WHEN tf.direction = 'credit' THEN tf.amount ELSE 0 END) AS income_amt
FROM spendsense.txn_fact tf
LEFT JOIN spendsense.txn_enriched te ON te.txn_id = tf.txn_id
WHERE COALESCE(te.category_code,'') <> 'transfers'
GROUP BY tf.user_id, date_trunc('month', tf.txn_date), COALESCE(te.category_code,'others');

CREATE UNIQUE INDEX IF NOT EXISTS idx_mv_insights_user_month 
ON spendsense.mv_spendsense_insights_user_month(user_id, month, category_code);

COMMENT ON MATERIALIZED VIEW spendsense.mv_spendsense_dashboard_user_month IS 'Dashboard KPIs excluding transfers';
COMMENT ON MATERIALIZED VIEW spendsense.mv_spendsense_insights_user_month IS 'Insights by category excluding transfers';

COMMIT;

