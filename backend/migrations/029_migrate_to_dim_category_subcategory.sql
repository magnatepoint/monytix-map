-- ============================================================================
-- Migrate category/subcategory data to dim_category/dim_subcategory
-- Drops duplicate tables and migrates all data to existing schema
-- ============================================================================

BEGIN;

-- ============================================================================
-- 1) Add budget_bucket and description columns if they don't exist
-- ============================================================================
ALTER TABLE spendsense.dim_category 
  ADD COLUMN IF NOT EXISTS budget_bucket TEXT;

ALTER TABLE spendsense.dim_subcategory 
  ADD COLUMN IF NOT EXISTS description TEXT;

-- ============================================================================
-- 2) Map budget_bucket to txn_type for categories
-- ============================================================================
-- Helper function to determine txn_type from budget_bucket
CREATE OR REPLACE FUNCTION spendsense.map_budget_bucket_to_txn_type(bucket TEXT)
RETURNS VARCHAR(12) AS $$
BEGIN
  RETURN CASE
    WHEN bucket ILIKE '%Inflow%' THEN 'income'
    WHEN bucket ILIKE '%Mandatory%' OR bucket ILIKE '%Necessities%' THEN 'needs'
    WHEN bucket ILIKE '%Luxury%' OR bucket ILIKE '%Shopping%' OR bucket ILIKE '%Entertainment%' THEN 'wants'
    WHEN bucket ILIKE '%Balance Sheet%' OR bucket ILIKE '%Asset%' OR bucket ILIKE '%Investment%' THEN 'assets'
    ELSE 'wants' -- default
  END;
END;
$$ LANGUAGE plpgsql IMMUTABLE;

-- ============================================================================
-- 3) Migrate categories to dim_category
-- ============================================================================
-- Deduplicate categories first (in case of duplicates)
INSERT INTO spendsense.dim_category (category_code, category_name, txn_type, display_order, active, budget_bucket)
SELECT DISTINCT ON (LOWER(code))
  LOWER(code) AS category_code,
  name AS category_name,
  spendsense.map_budget_bucket_to_txn_type(budget_bucket) AS txn_type,
  -- Assign display_order based on category type
  CASE 
    WHEN code = 'INCOME' THEN 5
    WHEN code = 'TRANSFER_IN' THEN 6
    WHEN code = 'TRANSFER_OUT' THEN 7
    WHEN code = 'LOAN_PAYMENTS' THEN 90
    WHEN code = 'UTILITIES' THEN 10
    WHEN code = 'RENT' THEN 20
    WHEN code = 'BANK_FEES' THEN 15
    WHEN code = 'GROCERIES' THEN 30
    WHEN code = 'DINING' THEN 40
    WHEN code = 'ENTERTAINMENT' THEN 50
    WHEN code = 'SHOPPING' THEN 60
    WHEN code = 'TRANSPORTATION' THEN 70
    WHEN code = 'TRAVEL' THEN 75
    WHEN code = 'MEDICAL' THEN 25
    WHEN code = 'PERSONAL_CARE' THEN 45
    WHEN code = 'HOME_IMPROVEMENT' THEN 35
    WHEN code = 'GOVERNMENT_AND_NON_PROFIT' THEN 80
    WHEN code = 'GENERAL_MERCHANDISE' THEN 65
    WHEN code = 'GENERAL_SERVICES' THEN 85
    WHEN code = 'CHILD_CARE' THEN 28
    WHEN code = 'MOTOR_MAINTENANCE' THEN 72
    WHEN code = 'PETS' THEN 55
    WHEN code = 'ASSETS_LIABILITIES' THEN 100
    WHEN code = 'INVESTMENTS' THEN 95
    ELSE 100
  END AS display_order,
  TRUE AS active,
  budget_bucket
FROM spendsense.category
ORDER BY LOWER(code), id
ON CONFLICT (category_code) DO UPDATE SET
  category_name = EXCLUDED.category_name,
  txn_type = EXCLUDED.txn_type,
  display_order = EXCLUDED.display_order,
  active = TRUE,
  budget_bucket = EXCLUDED.budget_bucket;

-- ============================================================================
-- 4) Migrate subcategories to dim_subcategory
-- ============================================================================
-- Deduplicate subcategories first, then insert with proper display_order
INSERT INTO spendsense.dim_subcategory (subcategory_code, category_code, subcategory_name, display_order, active, description)
WITH deduped_subcats AS (
  SELECT DISTINCT ON (LOWER(s.code))
    LOWER(s.code) AS subcategory_code,
    LOWER(c.code) AS category_code,
    s.name AS subcategory_name,
    s.description,
    s.id
  FROM spendsense.subcategory s
  JOIN spendsense.category c ON s.category_id = c.id
  ORDER BY LOWER(s.code), s.id
)
SELECT 
  subcategory_code,
  category_code,
  subcategory_name,
  -- Assign display_order sequentially within each category
  ROW_NUMBER() OVER (PARTITION BY category_code ORDER BY subcategory_code) * 10 AS display_order,
  TRUE AS active,
  description
FROM deduped_subcats
ON CONFLICT (subcategory_code) DO UPDATE SET
  category_code = EXCLUDED.category_code,
  subcategory_name = EXCLUDED.subcategory_name,
  display_order = EXCLUDED.display_order,
  active = TRUE,
  description = EXCLUDED.description;

-- ============================================================================
-- 5) Update view to use dim_category/dim_subcategory
-- ============================================================================
-- Drop existing view first (in case column names differ)
DROP VIEW IF EXISTS spendsense.v_categories;

CREATE VIEW spendsense.v_categories AS
SELECT
  dc.category_code,
  dc.category_name,
  dc.txn_type,
  dc.budget_bucket,
  dc.display_order AS category_display_order,
  dc.active AS category_active,
  ds.subcategory_code,
  ds.subcategory_name,
  ds.description,
  ds.display_order AS subcategory_display_order,
  ds.active AS subcategory_active
FROM spendsense.dim_category dc
LEFT JOIN spendsense.dim_subcategory ds ON ds.category_code = dc.category_code
ORDER BY dc.display_order, ds.display_order;

COMMENT ON VIEW spendsense.v_categories IS 'Convenient view joining dim_category and dim_subcategory with all fields';

-- ============================================================================
-- 6) Drop duplicate tables (if they exist)
-- ============================================================================
-- Drop triggers first
DROP TRIGGER IF EXISTS category_set_updated_at ON spendsense.category;
DROP TRIGGER IF EXISTS subcategory_set_updated_at ON spendsense.subcategory;

-- Drop tables
DROP TABLE IF EXISTS spendsense.subcategory CASCADE;
DROP TABLE IF EXISTS spendsense.category CASCADE;

-- Drop helper function
DROP FUNCTION IF EXISTS spendsense.map_budget_bucket_to_txn_type(TEXT);

COMMIT;

-- ============================================================================
-- Migration complete
-- ============================================================================
-- All category/subcategory data has been migrated to dim_category/dim_subcategory
-- Duplicate tables have been removed
-- View updated to use the standard schema
-- ============================================================================

