-- =========================================================
-- Add Investments Category and Expand Loans
-- Add mutual funds, stocks, SIP, bonds, etc.
-- =========================================================

BEGIN;

-- =============================
-- STEP 1: Add investments category
-- =============================
INSERT INTO spendsense.dim_category (category_code, category_name, txn_type, display_order, active) VALUES
('investments','Investments','assets',115,true)  -- Between banks (110) and ott (120)
ON CONFLICT (category_code) DO UPDATE SET 
    category_name = EXCLUDED.category_name,
    txn_type = EXCLUDED.txn_type,
    display_order = EXCLUDED.display_order,
    active = true;

-- =============================
-- STEP 2: Add investment subcategories
-- =============================
INSERT INTO spendsense.dim_subcategory (subcategory_code, category_code, subcategory_name, display_order, active) VALUES
-- Mutual Funds
('mf_sip','investments','Mutual Fund SIP',10,true),
('mf_lumpsum','investments','Mutual Fund Lump Sum',15,true),
('mf_equity','investments','Equity Mutual Funds',20,true),
('mf_debt','investments','Debt Mutual Funds',25,true),
('mf_hybrid','investments','Hybrid Mutual Funds',30,true),
('mf_elss','investments','ELSS (Tax Saving)',35,true),
('mf_index','investments','Index Funds / ETFs',40,true),

-- Stocks & Equity
('stocks_direct','investments','Stocks (Direct)',50,true),
('stocks_etf','investments','ETFs / Index Funds',55,true),
('stocks_ipo','investments','IPO / FPO',60,true),
('stocks_futures','investments','Futures & Options',65,true),

-- Bonds & Fixed Income
('bonds_government','investments','Government Bonds',70,true),
('bonds_corporate','investments','Corporate Bonds',75,true),
('sgb_gold','investments','Sovereign Gold Bonds (SGB)',80,true),

-- Other Investments
('commodities','investments','Commodities (Gold/Silver)',85,true),
('reits','investments','REITs / InvITs',90,true),
('crypto','investments','Cryptocurrency',95,true),
('other_investments','investments','Other Investments',100,true)

ON CONFLICT (subcategory_code) DO UPDATE SET
    category_code = EXCLUDED.category_code,
    subcategory_name = EXCLUDED.subcategory_name,
    display_order = EXCLUDED.display_order,
    active = true;

-- =============================
-- STEP 3: Expand loans subcategories
-- =============================
INSERT INTO spendsense.dim_subcategory (subcategory_code, category_code, subcategory_name, display_order, active) VALUES
-- Additional loan types
('loan_gold','loans','Gold Loan EMI',70,true),
('loan_property','loans','Property Loan EMI',75,true),
('loan_credit_card','loans','Credit Card Loan EMI',80,true),
('loan_overdraft','loans','Overdraft / Cash Credit',85,true),
('loan_other','loans','Other Loans',90,true)

ON CONFLICT (subcategory_code) DO UPDATE SET
    category_code = EXCLUDED.category_code,
    subcategory_name = EXCLUDED.subcategory_name,
    display_order = EXCLUDED.display_order,
    active = true;

-- =============================
-- STEP 4: Add merchant rules for investment platforms
-- =============================

-- Zerodha (stocks & MF)
INSERT INTO spendsense.merchant_rules (rule_id, priority, applies_to, pattern_regex, category_code, subcategory_code, active, source, created_at)
VALUES 
    (gen_random_uuid(), 25, 'merchant', '(?i)\b(ZERODHA|ZERODHA\s*KITE|KITE)\b', 'investments', 'stocks_direct', true, 'seed', NOW()),
    (gen_random_uuid(), 25, 'merchant', '(?i)\b(COIN\.ZERODHA|ZERODHA\s*COIN)\b', 'investments', 'mf_sip', true, 'seed', NOW())
ON CONFLICT DO NOTHING;

-- Groww (stocks & MF)
INSERT INTO spendsense.merchant_rules (rule_id, priority, applies_to, pattern_regex, category_code, subcategory_code, active, source, created_at)
VALUES 
    (gen_random_uuid(), 25, 'merchant', '(?i)\b(GROWW)\b', 'investments', 'stocks_direct', true, 'seed', NOW()),
    (gen_random_uuid(), 25, 'merchant', '(?i)\b(GROWW\s*MF|GROWW\s*MUTUAL)\b', 'investments', 'mf_sip', true, 'seed', NOW())
ON CONFLICT DO NOTHING;

-- Upstox (stocks & MF)
INSERT INTO spendsense.merchant_rules (rule_id, priority, applies_to, pattern_regex, category_code, subcategory_code, active, source, created_at)
VALUES 
    (gen_random_uuid(), 25, 'merchant', '(?i)\b(UPSTOX)\b', 'investments', 'stocks_direct', true, 'seed', NOW())
ON CONFLICT DO NOTHING;

-- Paytm Money, Angel One, etc.
INSERT INTO spendsense.merchant_rules (rule_id, priority, applies_to, pattern_regex, category_code, subcategory_code, active, source, created_at)
VALUES 
    (gen_random_uuid(), 25, 'merchant', '(?i)\b(PAYTM\s*MONEY|PAYTM\s*MF)\b', 'investments', 'mf_sip', true, 'seed', NOW()),
    (gen_random_uuid(), 25, 'merchant', '(?i)\b(ANGEL\s*ONE|ANGEL\s*BROKING)\b', 'investments', 'stocks_direct', true, 'seed', NOW()),
    (gen_random_uuid(), 25, 'merchant', '(?i)\b(ICICI\s*DIRECT|HDFC\s*SECURITIES|KOTAK\s*SECURITIES)\b', 'investments', 'stocks_direct', true, 'seed', NOW())
ON CONFLICT DO NOTHING;

-- SIP descriptions
INSERT INTO spendsense.merchant_rules (rule_id, priority, applies_to, pattern_regex, category_code, subcategory_code, active, source, created_at)
VALUES 
    (gen_random_uuid(), 30, 'description', '(?i)\b(SIP|SYSTEMATIC\s*INVESTMENT|MUTUAL\s*FUND\s*SIP)\b', 'investments', 'mf_sip', true, 'seed', NOW()),
    (gen_random_uuid(), 30, 'description', '(?i)\b(MUTUAL\s*FUND|MF|AMC)\b', 'investments', 'mf_lumpsum', true, 'seed', NOW()),
    (gen_random_uuid(), 30, 'description', '(?i)\b(IPO|FPO|INITIAL\s*PUBLIC|OFFER)\b', 'investments', 'stocks_ipo', true, 'seed', NOW())
ON CONFLICT DO NOTHING;

COMMIT;

