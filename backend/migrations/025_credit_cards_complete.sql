-- =========================================================
-- Credit Cards Complete Migration
-- Combines: 025_add_credit_cards_category.sql, 026_update_credit_card_rules.sql, 028_add_credit_card_transaction_type.sql
-- Adds credit cards category, subcategories, merchant rules, and payment_method field
-- =========================================================

BEGIN;

-- =============================
-- STEP 1: Insert credit_cards category
-- =============================
INSERT INTO spendsense.dim_category (category_code, category_name, txn_type, display_order, active) VALUES
('credit_cards','Credit Cards','needs',85,true)  -- Between bills (80) and loans (90)
ON CONFLICT (category_code) DO UPDATE SET 
    category_name = EXCLUDED.category_name,
    txn_type = EXCLUDED.txn_type,
    display_order = EXCLUDED.display_order,
    active = true;

-- =============================
-- STEP 2: Insert credit card subcategories
-- =============================
INSERT INTO spendsense.dim_subcategory (subcategory_code, category_code, subcategory_name, display_order, active) VALUES
('cc_bill_payment','credit_cards','Credit Card Bill Payment',10,true),
('cc_interest','credit_cards','Credit Card Interest / Finance Charges',20,true),
('cc_fees','credit_cards','Credit Card Fees (Annual/Late/Overlimit)',30,true),
('cc_cashback','credit_cards','Credit Card Cashback / Rewards (Income)',40,true),
('cc_emi','credit_cards','Credit Card EMI / Installments',50,true),
('cc_balance_transfer','credit_cards','Credit Card Balance Transfer',60,true),
('cc_foreign_transaction','credit_cards','Foreign Transaction Fee',70,true),
('cc_other','credit_cards','Other Credit Card Charges',80,true)
ON CONFLICT (subcategory_code) DO UPDATE SET
    category_code = EXCLUDED.category_code,
    subcategory_name = EXCLUDED.subcategory_name,
    display_order = EXCLUDED.display_order,
    active = true;

-- Note: bills.credit_card_due remains for backward compatibility
-- New credit card transactions should use credit_cards category

-- =============================
-- STEP 3: Update existing credit card merchant rules
-- =============================

-- Update CRED, American Express, and other credit card app rules
-- Change from loans_emi/credit_card_bill to credit_cards/cc_bill_payment
UPDATE spendsense.merchant_rules
SET 
    category_code = 'credit_cards',
    subcategory_code = 'cc_bill_payment'
WHERE 
    active = true
    AND (
        pattern_regex ~* '(?i)\b(CRED|AMERICAN\s*EXPRESS|AMEX|HDFC\s*CARD|ICICI\s*CARD|SBI\s*CARD|AXIS\s*CARD|CREDIT\s*CARD)\b'
        OR category_code = 'loans_emi'
        OR (category_code IS NULL AND pattern_regex ~* '(?i)credit.*card')
    )
    AND subcategory_code IN ('credit_card_bill', 'credit_card_due', NULL);

-- =============================
-- STEP 4: Add specific credit card merchant rules
-- =============================

-- CRED app
INSERT INTO spendsense.merchant_rules (rule_id, priority, applies_to, pattern_regex, category_code, subcategory_code, active, source, created_at)
VALUES 
    (gen_random_uuid(), 15, 'merchant', '(?i)\b(CRED|CRED\s*CLUB|CRED\s*PAY)\b', 'credit_cards', 'cc_bill_payment', true, 'seed', NOW())
ON CONFLICT DO NOTHING;

-- American Express / AMEX
INSERT INTO spendsense.merchant_rules (rule_id, priority, applies_to, pattern_regex, category_code, subcategory_code, active, source, created_at)
VALUES 
    (gen_random_uuid(), 15, 'merchant', '(?i)\b(AMERICAN\s*EXPRESS|AMEX|AMEX\s*CARD)\b', 'credit_cards', 'cc_bill_payment', true, 'seed', NOW())
ON CONFLICT DO NOTHING;

-- Bank credit cards (HDFC, ICICI, SBI, Axis, etc.)
INSERT INTO spendsense.merchant_rules (rule_id, priority, applies_to, pattern_regex, category_code, subcategory_code, active, source, created_at)
VALUES 
    (gen_random_uuid(), 20, 'merchant', '(?i)\b(HDFC\s*CARD|HDFC\s*CREDIT|HDFC\s*CREDIT\s*CARD)\b', 'credit_cards', 'cc_bill_payment', true, 'seed', NOW()),
    (gen_random_uuid(), 20, 'merchant', '(?i)\b(ICICI\s*CARD|ICICI\s*CREDIT|ICICI\s*CREDIT\s*CARD)\b', 'credit_cards', 'cc_bill_payment', true, 'seed', NOW()),
    (gen_random_uuid(), 20, 'merchant', '(?i)\b(SBI\s*CARD|SBI\s*CREDIT|SBI\s*CREDIT\s*CARD)\b', 'credit_cards', 'cc_bill_payment', true, 'seed', NOW()),
    (gen_random_uuid(), 20, 'merchant', '(?i)\b(AXIS\s*CARD|AXIS\s*CREDIT|AXIS\s*CREDIT\s*CARD)\b', 'credit_cards', 'cc_bill_payment', true, 'seed', NOW()),
    (gen_random_uuid(), 20, 'merchant', '(?i)\b(KOTAK\s*CARD|KOTAK\s*CREDIT|KOTAK\s*CREDIT\s*CARD)\b', 'credit_cards', 'cc_bill_payment', true, 'seed', NOW()),
    (gen_random_uuid(), 20, 'merchant', '(?i)\b(HSBC\s*CARD|HSBC\s*CREDIT|HSBC\s*CREDIT\s*CARD)\b', 'credit_cards', 'cc_bill_payment', true, 'seed', NOW())
ON CONFLICT DO NOTHING;

-- Credit card payment descriptions
INSERT INTO spendsense.merchant_rules (rule_id, priority, applies_to, pattern_regex, category_code, subcategory_code, active, source, created_at)
VALUES 
    (gen_random_uuid(), 25, 'description', '(?i)\b(CREDIT\s*CARD\s*BILL|CARD\s*PAYMENT|CC\s*PAYMENT|CREDIT\s*CARD\s*PAYMENT)\b', 'credit_cards', 'cc_bill_payment', true, 'seed', NOW()),
    (gen_random_uuid(), 25, 'description', '(?i)\b(CREDIT\s*CARD\s*DUE|CC\s*DUE|CARD\s*DUE)\b', 'credit_cards', 'cc_bill_payment', true, 'seed', NOW())
ON CONFLICT DO NOTHING;

-- Credit card interest and fees
INSERT INTO spendsense.merchant_rules (rule_id, priority, applies_to, pattern_regex, category_code, subcategory_code, active, source, created_at)
VALUES 
    (gen_random_uuid(), 30, 'description', '(?i)\b(CREDIT\s*CARD\s*INTEREST|CC\s*INTEREST|FINANCE\s*CHARGE|CREDIT\s*CARD\s*FINANCE)\b', 'credit_cards', 'cc_interest', true, 'seed', NOW()),
    (gen_random_uuid(), 30, 'description', '(?i)\b(CREDIT\s*CARD\s*FEE|CC\s*FEE|ANNUAL\s*FEE|LATE\s*FEE|OVERLIMIT\s*FEE)\b', 'credit_cards', 'cc_fees', true, 'seed', NOW()),
    (gen_random_uuid(), 30, 'description', '(?i)\b(CREDIT\s*CARD\s*CASHBACK|CC\s*CASHBACK|CREDIT\s*CARD\s*REWARD)\b', 'credit_cards', 'cc_cashback', true, 'seed', NOW()),
    (gen_random_uuid(), 30, 'description', '(?i)\b(CREDIT\s*CARD\s*EMI|CC\s*EMI|CARD\s*EMI|INSTALLMENT)\b', 'credit_cards', 'cc_emi', true, 'seed', NOW())
ON CONFLICT DO NOTHING;

-- =============================
-- STEP 5: Add payment_method column to track credit card transactions
-- =============================
ALTER TABLE spendsense.txn_fact
  ADD COLUMN IF NOT EXISTS payment_method VARCHAR(32);

-- Add payment_method to txn_staging as well
ALTER TABLE spendsense.txn_staging
  ADD COLUMN IF NOT EXISTS payment_method VARCHAR(32);

-- Add index for payment_method queries
CREATE INDEX IF NOT EXISTS ix_txn_fact_payment_method 
  ON spendsense.txn_fact(payment_method) 
  WHERE payment_method IS NOT NULL;

COMMENT ON COLUMN spendsense.txn_fact.payment_method IS 'Payment method: credit_card, debit_card, upi, neft, imps, cash, etc.';
COMMENT ON COLUMN spendsense.txn_staging.payment_method IS 'Payment method: credit_card, debit_card, upi, neft, imps, cash, etc.';

COMMIT;

