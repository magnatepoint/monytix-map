-- =========================================================
-- Merchant Rules Complete Migration
-- Combines: 012_add_merchant_rules_scoping.sql, 015_india_seed_merchant_rules.sql, 022_add_cafe_merchant_rules.sql
-- Adds merchant rules scoping, India-specific seed rules, and cafe rules
-- =========================================================

BEGIN;

-- =============================
-- PART 1: Add user/tenant scoping and pattern hash to merchant_rules
-- =============================

-- Step 1: Add new columns (if not exists)
ALTER TABLE spendsense.merchant_rules
  ADD COLUMN IF NOT EXISTS created_by uuid,
  ADD COLUMN IF NOT EXISTS tenant_id uuid,
  ADD COLUMN IF NOT EXISTS source varchar(16) DEFAULT 'seed', -- 'learned' | 'seed' | 'ops'
  ADD COLUMN IF NOT EXISTS notes text,
  ADD COLUMN IF NOT EXISTS pattern_hash char(40);

-- Step 2: Update existing rules to have source='seed' and pattern_hash
UPDATE spendsense.merchant_rules
SET source = 'seed'
WHERE source IS NULL OR source = '';

-- Step 3: Calculate pattern_hash for existing rows that don't have it
UPDATE spendsense.merchant_rules
SET pattern_hash = encode(digest(pattern_regex, 'sha1'), 'hex')
WHERE pattern_hash IS NULL;

-- Step 4: Handle duplicates - keep the rule with lowest priority (or oldest if same priority)
-- Deactivate duplicate rules (keep only one active per pattern_hash)
WITH duplicates AS (
  SELECT 
    rule_id,
    ROW_NUMBER() OVER (
      PARTITION BY 
        coalesce(tenant_id, '00000000-0000-0000-0000-000000000000'::uuid),
        applies_to,
        pattern_hash
      ORDER BY priority ASC, created_at ASC
    ) as rn
  FROM spendsense.merchant_rules
  WHERE active = true
  AND pattern_hash IS NOT NULL
)
UPDATE spendsense.merchant_rules
SET active = false
FROM duplicates
WHERE merchant_rules.rule_id = duplicates.rule_id
AND duplicates.rn > 1;

-- Step 5: Add index for tenant/applies_to lookups
CREATE INDEX IF NOT EXISTS ix_rules_scope 
ON spendsense.merchant_rules(tenant_id, applies_to, active);

-- Step 6: Add pattern hash unique index for deduplication (per tenant + applies_to + hash)
-- Drop existing index if it exists (in case of previous failed migration)
DROP INDEX IF EXISTS spendsense.ux_rules_hash;

CREATE UNIQUE INDEX ux_rules_hash
ON spendsense.merchant_rules (
  coalesce(tenant_id, '00000000-0000-0000-0000-000000000000'::uuid),
  applies_to,
  pattern_hash
)
WHERE active = true;

COMMENT ON COLUMN spendsense.merchant_rules.created_by IS 'User who created this rule (for learned rules)';
COMMENT ON COLUMN spendsense.merchant_rules.tenant_id IS 'Optional tenant isolation (NULL = global rule)';
COMMENT ON COLUMN spendsense.merchant_rules.source IS 'Rule source: learned (from edits), seed (initial data), ops (manual)';
COMMENT ON COLUMN spendsense.merchant_rules.pattern_hash IS 'SHA1 hash of pattern_regex for efficient deduplication';

-- Helpful index (if not already exists)
CREATE INDEX IF NOT EXISTS ix_rules_active_pri
ON spendsense.merchant_rules (active, priority);

-- =============================
-- PART 2: India Seed Rules (priority: lower number = stronger match)
-- =============================

-- Ensure required categories exist (from migration 029)
DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM spendsense.dim_category WHERE category_code = 'transportation') THEN
    RAISE EXCEPTION 'Required category "transportation" not found. Please run migration 029_migrate_to_dim_category_subcategory.sql first.';
  END IF;
END $$;

-- Clean up any existing rules with invalid category codes first
UPDATE spendsense.merchant_rules
SET active = false
WHERE category_code IS NOT NULL
  AND category_code NOT IN (SELECT category_code FROM spendsense.dim_category);

-- Clean up any existing rules with invalid subcategory codes
UPDATE spendsense.merchant_rules
SET active = false
WHERE subcategory_code IS NOT NULL
  AND subcategory_code NOT IN (SELECT subcategory_code FROM spendsense.dim_subcategory);

-- ---------- TRANSPORT / MOBILITY ----------

-- Auto/Taxi
INSERT INTO spendsense.merchant_rules (rule_id, priority, applies_to, pattern_regex, category_code, subcategory_code, active, source, tenant_id, created_by)
VALUES
(gen_random_uuid(), 25, 'merchant', '(?i)\b(OLA|UBER|MERU|RAPIDO)\b', 'transportation', 'taxis_and_ride_shares', true, 'seed', NULL, NULL)
ON CONFLICT DO NOTHING;

-- Metro / Local
INSERT INTO spendsense.merchant_rules (rule_id, priority, applies_to, pattern_regex, category_code, subcategory_code, active, source, tenant_id, created_by)
VALUES
(gen_random_uuid(), 40, 'description', '(?i)\b(METRO|MMTS|LOCAL TRAIN|TSRTC|BMTC|BEST)\b', 'transportation', 'public_transit', true, 'seed', NULL, NULL)
ON CONFLICT DO NOTHING;

-- FASTag / Tolls
INSERT INTO spendsense.merchant_rules (rule_id, priority, applies_to, pattern_regex, category_code, subcategory_code, active, source, tenant_id, created_by)
VALUES
(gen_random_uuid(), 30, 'description', '(?i)\b(FASTAG|NHAI|TOLL)\b', 'transportation', 'tolls', true, 'seed', NULL, NULL)
ON CONFLICT DO NOTHING;

-- Fuel Brands (under transportation or motor_maintenance)
INSERT INTO spendsense.merchant_rules (rule_id, priority, applies_to, pattern_regex, category_code, subcategory_code, active, source, tenant_id, created_by)
VALUES
(gen_random_uuid(), 25, 'merchant', '(?i)\b(HPCL|BPCL|IOCL|INDIAN\s*OIL|SHELL|RELIANCE)\b', 'motor_maintenance', 'automotive_services', true, 'seed', NULL, NULL)
ON CONFLICT DO NOTHING;

-- ---------- EATING OUT & NIGHTLIFE ----------

-- Food delivery
INSERT INTO spendsense.merchant_rules (rule_id, priority, applies_to, pattern_regex, category_code, subcategory_code, active, source, tenant_id, created_by)
VALUES
(gen_random_uuid(), 20, 'merchant', '(?i)\b(SWIGGY|ZOMATO|EATSURE)\b', 'dining', 'online_delivery', true, 'seed', NULL, NULL)
ON CONFLICT DO NOTHING;

-- Cafés/Bakeries
INSERT INTO spendsense.merchant_rules (rule_id, priority, applies_to, pattern_regex, category_code, subcategory_code, active, source, tenant_id, created_by)
VALUES
(gen_random_uuid(), 35, 'merchant', '(?i)\b(STARBUCKS|CCD|CHAITALI|BAKERY|CAFE|COFFEE)\b', 'dining', 'cafes_bistros', true, 'seed', NULL, NULL)
ON CONFLICT DO NOTHING;

-- Bars/Pubs/Nightlife (incl. Wine Shops)
INSERT INTO spendsense.merchant_rules (rule_id, priority, applies_to, pattern_regex, category_code, subcategory_code, active, source, tenant_id, created_by)
VALUES
(gen_random_uuid(), 28, 'merchant', '(?i)\b(BAR|PUB|BREWERY|LOUNGE|WINE\s*SHOP|LIQUOR)\b', 'dining', 'pubs_bars', true, 'seed', NULL, NULL)
ON CONFLICT DO NOTHING;

-- Street food / Pan shop cues (description often has PAN/BEEDA/PAAN)
INSERT INTO spendsense.merchant_rules (rule_id, priority, applies_to, pattern_regex, category_code, subcategory_code, active, source, tenant_id, created_by)
VALUES
(gen_random_uuid(), 45, 'description', '(?i)\b(PA[AN]N?|BEEDA|PAN\s*SHOP|BIRIYANI\s*CART|TEA\s*STALL|DOS[A|E]\s*CART|BANDI)\b', 'dining', 'street_food', true, 'seed', NULL, NULL)
ON CONFLICT DO NOTHING;

-- Restaurants (generic)
INSERT INTO spendsense.merchant_rules (rule_id, priority, applies_to, pattern_regex, category_code, subcategory_code, active, source, tenant_id, created_by)
VALUES
(gen_random_uuid(), 38, 'description', '(?i)\b(RESTAURANT|HOTEL|DINING|BIRYANI|TANDOORI|BAKESHOP|MESS)\b', 'dining', 'casual_dining', true, 'seed', NULL, NULL)
ON CONFLICT DO NOTHING;

-- ---------- GROCERIES / KIRANA ----------

INSERT INTO spendsense.merchant_rules (rule_id, priority, applies_to, pattern_regex, category_code, subcategory_code, active, source, tenant_id, created_by)
VALUES
(gen_random_uuid(), 22, 'merchant', '(?i)\b(DMART|MORE\s*SUPERMARKET|SPENCERS|RELIANCE\s*SMART)\b', 'groceries', 'supermarkets', true, 'seed', NULL, NULL)
ON CONFLICT DO NOTHING;

-- Quick commerce
INSERT INTO spendsense.merchant_rules (rule_id, priority, applies_to, pattern_regex, category_code, subcategory_code, active, source, tenant_id, created_by)
VALUES
(gen_random_uuid(), 22, 'merchant', '(?i)\b(ZEPTO|BLINKIT|BIGBASKET|BBNOW)\b', 'groceries', 'online_groceries', true, 'seed', NULL, NULL)
ON CONFLICT DO NOTHING;

-- Kirana / generic store words
INSERT INTO spendsense.merchant_rules (rule_id, priority, applies_to, pattern_regex, category_code, subcategory_code, active, source, tenant_id, created_by)
VALUES
(gen_random_uuid(), 47, 'merchant', '(?i)\b(KIRANA|PROVISION|GENERAL\s*STORE|SUPER\s*MART|BAZAR|DEPARTMENTAL)\b', 'groceries', 'mom_and_pop', true, 'seed', NULL, NULL)
ON CONFLICT DO NOTHING;

-- ---------- SHOPPING / APPAREL / ELECTRONICS ----------

INSERT INTO spendsense.merchant_rules (rule_id, priority, applies_to, pattern_regex, category_code, subcategory_code, active, source, tenant_id, created_by)
VALUES
(gen_random_uuid(), 24, 'merchant', '(?i)\b(AMAZON|FLIPKART|AJIO|MYNTRA|NYKAA|MEESHO)\b', 'shopping', 'online_shopping', true, 'seed', NULL, NULL)
ON CONFLICT DO NOTHING;

INSERT INTO spendsense.merchant_rules (rule_id, priority, applies_to, pattern_regex, category_code, subcategory_code, active, source, tenant_id, created_by)
VALUES
(gen_random_uuid(), 26, 'merchant', '(?i)\b(CROMA|RELIANCE\s*DIGITAL|VIJAY\s*SALES)\b', 'shopping', 'electronics', true, 'seed', NULL, NULL)
ON CONFLICT DO NOTHING;

-- Small businesses (fallback)
INSERT INTO spendsense.merchant_rules (rule_id, priority, applies_to, pattern_regex, category_code, subcategory_code, active, source, tenant_id, created_by)
VALUES
(gen_random_uuid(), 60, 'merchant', '(?i)(ENTERPRISES?|TRAD(?:ER|ING)S?|STORES?|MART|BAZAR|BOUTIQUE)$', 'shopping', 'clothing_and_accessories', true, 'seed', NULL, NULL)
ON CONFLICT DO NOTHING;

-- ---------- MOBILE / INTERNET / DTH ----------

INSERT INTO spendsense.merchant_rules (rule_id, priority, applies_to, pattern_regex, category_code, subcategory_code, active, source, tenant_id, created_by)
VALUES
(gen_random_uuid(), 23, 'merchant', '(?i)\b(AIRTEL|JIO|VI\b|VODAFONE|IDEA)\b', 'utilities', 'mobile_telephone', true, 'seed', NULL, NULL)
ON CONFLICT DO NOTHING;

INSERT INTO spendsense.merchant_rules (rule_id, priority, applies_to, pattern_regex, category_code, subcategory_code, active, source, tenant_id, created_by)
VALUES
(gen_random_uuid(), 23, 'merchant', '(?i)\b(JIOFIBER|ACT\s*FIBERNET|HATHWAY|BSNL\s*(FTTH|BB)|TIKONA)\b', 'utilities', 'internet_and_cable', true, 'seed', NULL, NULL)
ON CONFLICT DO NOTHING;

INSERT INTO spendsense.merchant_rules (rule_id, priority, applies_to, pattern_regex, category_code, subcategory_code, active, source, tenant_id, created_by)
VALUES
(gen_random_uuid(), 33, 'merchant', '(?i)\b(TATA\s*PLAY|AIRTEL\s*DTH|SUN\s*DIRECT|DISHTV)\b', 'utilities', 'internet_and_cable', true, 'seed', NULL, NULL)
ON CONFLICT DO NOTHING;

-- ---------- UTILITIES ----------

INSERT INTO spendsense.merchant_rules (rule_id, priority, applies_to, pattern_regex, category_code, subcategory_code, active, source, tenant_id, created_by)
VALUES
(gen_random_uuid(), 30, 'merchant', '(?i)\b(BSES\s*(RAJDHANI|YAMUNA)|TPDDL|TSSPDCL|MSEDCL|BESCOM|TANGEDCO|APDCL)\b', 'utilities', 'electricity', true, 'seed', NULL, NULL)
ON CONFLICT DO NOTHING;

INSERT INTO spendsense.merchant_rules (rule_id, priority, applies_to, pattern_regex, category_code, subcategory_code, active, source, tenant_id, created_by)
VALUES
(gen_random_uuid(), 32, 'merchant', '(?i)\b(IGL|MGL|ADANI\s*GAS|PNG)\b', 'utilities', 'gas', true, 'seed', NULL, NULL)
ON CONFLICT DO NOTHING;

-- ---------- HEALTHCARE ----------

INSERT INTO spendsense.merchant_rules (rule_id, priority, applies_to, pattern_regex, category_code, subcategory_code, active, source, tenant_id, created_by)
VALUES
(gen_random_uuid(), 35, 'merchant', '(?i)\b(APOLLO\s*(PHARMACY|HOSPITALS)|FORTIS|MANIPAL|STAR\s*HEALTH|MEDPLUS)\b', 'medical', 'primary_care', true, 'seed', NULL, NULL)
ON CONFLICT DO NOTHING;

INSERT INTO spendsense.merchant_rules (rule_id, priority, applies_to, pattern_regex, category_code, subcategory_code, active, source, tenant_id, created_by)
VALUES
(gen_random_uuid(), 35, 'merchant', '(?i)\b(MEDPLUS|PHARMACY|APOLLO\s*PHARMACY)\b', 'medical', 'pharmacies_and_supplements', true, 'seed', NULL, NULL)
ON CONFLICT DO NOTHING;

INSERT INTO spendsense.merchant_rules (rule_id, priority, applies_to, pattern_regex, category_code, subcategory_code, active, source, tenant_id, created_by)
VALUES
(gen_random_uuid(), 35, 'merchant', '(?i)\b(THYROCARE|LAL\s*PATH|DR\.?\s*LAL)\b', 'medical', 'other_medical', true, 'seed', NULL, NULL)
ON CONFLICT DO NOTHING;

-- ---------- EDUCATION ----------

INSERT INTO spendsense.merchant_rules (rule_id, priority, applies_to, pattern_regex, category_code, subcategory_code, active, source, tenant_id, created_by)
VALUES
(gen_random_uuid(), 42, 'description', '(?i)\b(SCHOOL\s*FEE|TUTION|TUITION|COACHING)\b', 'child_care', 'education', true, 'seed', NULL, NULL)
ON CONFLICT DO NOTHING;

-- ---------- INSURANCE ----------

INSERT INTO spendsense.merchant_rules (rule_id, priority, applies_to, pattern_regex, category_code, subcategory_code, active, source, tenant_id, created_by)
VALUES
(gen_random_uuid(), 30, 'merchant', '(?i)\b(LIC|HDFC\s*LIFE|SBI\s*LIFE|ICICI\s*LOMBARD|ACKO|STAR\s*HEALTH|HDFC\s*ERGO)\b', 'general_services', 'accounting_and_financial_planning', true, 'seed', NULL, NULL)
ON CONFLICT DO NOTHING;

-- ---------- LOANS / EMI / CREDIT CARD BILLS ----------

INSERT INTO spendsense.merchant_rules (rule_id, priority, applies_to, pattern_regex, category_code, subcategory_code, active, source, tenant_id, created_by)
VALUES
(gen_random_uuid(), 22, 'description', '(?i)\b(CREDIT\s*CARD\s*BILL|CARD\s*PAYMENT|CC\s*PAYMENT)\b', 'loan_payments', 'credit_card_payment', true, 'seed', NULL, NULL)
ON CONFLICT DO NOTHING;

INSERT INTO spendsense.merchant_rules (rule_id, priority, applies_to, pattern_regex, category_code, subcategory_code, active, source, tenant_id, created_by)
VALUES
(gen_random_uuid(), 28, 'description', '(?i)\b(EMI\s*DEBIT|LOAN\s*EMI|AUTO\s*DEBIT)\b', 'loan_payments', 'personal_loan_payment', true, 'seed', NULL, NULL)
ON CONFLICT DO NOTHING;

-- ---------- FEES / TAX ----------

INSERT INTO spendsense.merchant_rules (rule_id, priority, applies_to, pattern_regex, category_code, subcategory_code, active, source, tenant_id, created_by)
VALUES
(gen_random_uuid(), 38, 'description', '(?i)\b(BANK\s*CHARGE|CONVENIENCE\s*FEE|IMPS\s*CHARGES|UPI\s*CHARGE)\b', 'bank_fees', 'other_bank_fees', true, 'seed', NULL, NULL)
ON CONFLICT DO NOTHING;

INSERT INTO spendsense.merchant_rules (rule_id, priority, applies_to, pattern_regex, category_code, subcategory_code, active, source, tenant_id, created_by)
VALUES
(gen_random_uuid(), 38, 'description', '(?i)\b(INCOME\s*TAX|TDS|GST\s*PAYMENT|EPFO)\b', 'government_and_non_profit', 'tax_payment', true, 'seed', NULL, NULL)
ON CONFLICT DO NOTHING;

-- ---------- INCOME ----------

INSERT INTO spendsense.merchant_rules (rule_id, priority, applies_to, pattern_regex, category_code, subcategory_code, active, source, tenant_id, created_by)
VALUES
(gen_random_uuid(), 18, 'description', '(?i)\b(SALARY\s*(CREDIT|PAY)|PAYROLL|NEFT\s*CREDIT.*SALARY)\b', 'income', 'wages', true, 'seed', NULL, NULL)
ON CONFLICT DO NOTHING;

INSERT INTO spendsense.merchant_rules (rule_id, priority, applies_to, pattern_regex, category_code, subcategory_code, active, source, tenant_id, created_by)
VALUES
(gen_random_uuid(), 30, 'description', '(?i)\b(REFUND|CASHBACK|REVERSAL)\b', 'income', 'other_income', true, 'seed', NULL, NULL)
ON CONFLICT DO NOTHING;

-- =============================
-- PART 3: Add Cafe/Restaurant Merchant Rules
-- =============================

-- Add cafe/coffee shop keywords
INSERT INTO spendsense.merchant_rules (rule_id, priority, applies_to, pattern_regex, category_code, subcategory_code, active, source, tenant_id, created_by, created_at)
VALUES 
    (gen_random_uuid(), 35, 'merchant', '(?i)\b(CUP|COFFEE|THEORY|CAFE|COFFEE SHOP|BARISTA)\b', 'dining', 'cafes_bistros', true, 'seed', NULL, NULL, now())
ON CONFLICT DO NOTHING;

-- Add more cafe keywords
INSERT INTO spendsense.merchant_rules (rule_id, priority, applies_to, pattern_regex, category_code, subcategory_code, active, source, tenant_id, created_by, created_at)
VALUES 
    (gen_random_uuid(), 36, 'merchant', '(?i)\b(BIG CUP|CUP THEORY|COFFEE.*THEORY)\b', 'dining', 'cafes_bistros', true, 'seed', NULL, NULL, now())
ON CONFLICT DO NOTHING;

COMMIT;

