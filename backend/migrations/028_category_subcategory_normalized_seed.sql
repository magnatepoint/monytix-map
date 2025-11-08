-- ============================================================================
-- Categories & Subcategories Normalized Seed
-- Creates normalized category/subcategory tables with budget buckets and descriptions
-- Idempotent: safe to run multiple times
-- ============================================================================

BEGIN;

-- ============================================================================
-- 1) Schema: Create normalized category and subcategory tables
-- ============================================================================

CREATE TABLE IF NOT EXISTS spendsense.category (
  id          BIGSERIAL PRIMARY KEY,
  code        TEXT NOT NULL UNIQUE,              -- stable programmatic key: e.g., INCOME, TRANSFER_IN
  name        TEXT NOT NULL,                     -- human readable
  budget_bucket TEXT,                            -- e.g., "Inflows", "Mandatory Payments (Out-Flow-1)"
  created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS spendsense.subcategory (
  id           BIGSERIAL PRIMARY KEY,
  category_id  BIGINT NOT NULL REFERENCES spendsense.category(id) ON DELETE CASCADE,
  code         TEXT NOT NULL,
  name         TEXT NOT NULL,
  description  TEXT,
  created_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (category_id, code)
);

-- Indexes for performance
CREATE INDEX IF NOT EXISTS idx_subcategory_category_id ON spendsense.subcategory(category_id);
CREATE INDEX IF NOT EXISTS idx_subcategory_code ON spendsense.subcategory(code);
CREATE INDEX IF NOT EXISTS idx_category_code ON spendsense.category(code);

-- ============================================================================
-- 2) Triggers: Auto-update updated_at
-- ============================================================================
-- Reuse existing function or create if it doesn't exist
CREATE OR REPLACE FUNCTION spendsense.tg_set_updated_at()
RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  NEW.updated_at := now();
  RETURN NEW;
END $$;

DO $$
BEGIN
  -- Check if trigger already exists (schema-aware check)
  IF NOT EXISTS (
    SELECT 1 FROM pg_trigger t
    JOIN pg_class c ON t.tgrelid = c.oid
    JOIN pg_namespace n ON c.relnamespace = n.oid
    WHERE n.nspname = 'spendsense' 
      AND c.relname = 'category'
      AND t.tgname = 'category_set_updated_at'
  ) THEN
    CREATE TRIGGER category_set_updated_at
      BEFORE UPDATE ON spendsense.category
      FOR EACH ROW EXECUTE FUNCTION spendsense.tg_set_updated_at();
  END IF;

  IF NOT EXISTS (
    SELECT 1 FROM pg_trigger t
    JOIN pg_class c ON t.tgrelid = c.oid
    JOIN pg_namespace n ON c.relnamespace = n.oid
    WHERE n.nspname = 'spendsense' 
      AND c.relname = 'subcategory'
      AND t.tgname = 'subcategory_set_updated_at'
  ) THEN
    CREATE TRIGGER subcategory_set_updated_at
      BEFORE UPDATE ON spendsense.subcategory
      FOR EACH ROW EXECUTE FUNCTION spendsense.tg_set_updated_at();
  END IF;
END$$;

-- ============================================================================
-- 3) Seed Categories (UPSERT)
-- ============================================================================

WITH upsert_cat AS (
  INSERT INTO spendsense.category (code, name, budget_bucket)
  VALUES
    ('INCOME','INCOME','Inflows'),
    ('TRANSFER_IN','TRANSFER_IN','Inflows'),
    ('TRANSFER_OUT','TRANSFER_OUT', 'Outflows'),
    ('LOAN_PAYMENTS','LOAN_PAYMENTS','Mandatory Payments (Out-Flow-1)'),
    ('UTILITIES','UTILITIES','Mandatory Payments (Out-Flow-2)'),
    ('RENT','RENT','Mandatory Payments (Out-Flow-2)'),
    ('BANK_FEES','BANK_FEES','Mandatory Payments (Out-Flow-2)'),
    ('ENTERTAINMENT','ENTERTAINMENT','Luxury Payments (Out-Flow-3)'),
    ('DINING','DINING','Luxury Payments (Out-Flow-4)'),
    ('GROCERIES','Groceries','Necessities'),
    ('HOME_IMPROVEMENT','HOME_IMPROVEMENT','House Maintenance (Out-Flow-5)'),
    ('MEDICAL','MEDICAL','Medical Payments (Out-Flow-6)'),
    ('PERSONAL_CARE','PERSONAL_CARE','Personal Payments (Out-Flow-7)'),
    ('GOVERNMENT_AND_NON_PROFIT','GOVERNMENT_AND_NON_PROFIT','IT savings (Out-Flow-8)'),
    ('TRANSPORTATION','TRANSPORTATION','Local Transport Payments (Out-Flow-9)'),
    ('TRAVEL','TRAVEL','Travel Payments (Out-Flow-10)'),
    ('GENERAL_MERCHANDISE','GENERAL_MERCHANDISE','GENERAL MERCHANDISE (Out-Flow-11)'),
    ('GENERAL_SERVICES','GENERAL_SERVICES','Miscellaneous Payments (Out-Flow-12)'),
    ('SHOPPING','SHOPPING','Shopping Expenses'),
    ('CHILD_CARE','Child Care','Child care expenses'),
    ('MOTOR_MAINTENANCE','Motor Maintaince','Motor Maintaince'),
    ('PETS','Pets','Pet Maintaince'),
    ('ASSETS_LIABILITIES','Assets & Liabilities','Balance Sheet'),
    ('INVESTMENTS','INVESTMENTS','Investments')
  ON CONFLICT (code) DO UPDATE
  SET name = EXCLUDED.name,
      budget_bucket = EXCLUDED.budget_bucket,
      updated_at = now()
  RETURNING 1
)
SELECT 1;

-- ============================================================================
-- 4) Seed Subcategories (UPSERT) - Using CTE for category lookups
-- ============================================================================

-- INCOME
WITH c AS (SELECT id, code FROM spendsense.category WHERE code = 'INCOME')
INSERT INTO spendsense.subcategory (category_id, code, name, description)
SELECT c.id, sc.code, sc.name, sc.description
FROM c
JOIN (VALUES
  ('DIVIDENDS','DIVIDENDS','Dividends from investment accounts'),
  ('INTEREST_EARNED','INTEREST_EARNED','Income from interest on savings accounts'),
  ('RETIREMENT_PENSION','RETIREMENT_PENSION','Income from pension payments'),
  ('TAX_REFUND','TAX_REFUND','Income from tax refunds'),
  ('UNEMPLOYMENT','UNEMPLOYMENT','Unemployment benefits, including insurance and healthcare'),
  ('WAGES','WAGES (Labour/Job work/salary)','Income from salaries, gig-economy work, and tips'),
  ('OTHER_INCOME','OTHER_INCOME','Other miscellaneous income, including alimony, social security, child support, rental'),
  ('BUSINESS_INCOME','Through -Bussiness','Income from business'),
  ('MARKET_REALIZATION','Through -Stocks and Mutual Funds','Income through selling of stocks and mutual funds')
) AS sc(code,name,description) ON TRUE
ON CONFLICT (category_id, code) DO UPDATE
SET name = EXCLUDED.name,
    description = EXCLUDED.description,
    updated_at = now();

-- TRANSFER_IN
WITH c AS (SELECT id, code FROM spendsense.category WHERE code = 'TRANSFER_IN')
INSERT INTO spendsense.subcategory (category_id, code, name, description)
SELECT c.id, sc.code, sc.name, sc.description
FROM c
JOIN (VALUES
  ('CASH_ADVANCES_AND_LOANS','CASH_ADVANCES_AND_LOANS','Loans and cash advances deposited into a bank account'),
  ('DEPOSIT','DEPOSIT','Cash, checks, and ATM deposits into a bank account'),
  ('INVESTMENT_AND_RETIREMENT_FUNDS','INVESTMENT_AND_RETIREMENT_FUNDS','Inbound transfers to an investment or retirement account'),
  ('SAVINGS','SAVINGS','Inbound transfers to a savings account'),
  ('SWEEP_IN','Sweep in',''),
  ('ACCOUNT_TRANSFER','ACCOUNT_TRANSFER','General inbound transfers from another account'),
  ('OTHER_TRANSFER_IN','OTHER_TRANSFER_IN','Other miscellaneous inbound transactions')
) AS sc(code,name,description) ON TRUE
ON CONFLICT (category_id, code) DO UPDATE
SET name = EXCLUDED.name,
    description = EXCLUDED.description,
    updated_at = now();

-- TRANSFER_OUT
WITH c AS (SELECT id, code FROM spendsense.category WHERE code = 'TRANSFER_OUT')
INSERT INTO spendsense.subcategory (category_id, code, name, description)
SELECT c.id, sc.code, sc.name, sc.description
FROM c
JOIN (VALUES
  ('INVESTMENT_AND_RETIREMENT_FUNDS','INVESTMENT_AND_RETIREMENT_FUNDS','Transfers to an investment or retirement account'),
  ('SAVINGS','SAVINGS','Outbound transfers to savings accounts'),
  ('WITHDRAWAL','WITHDRAWAL','Withdrawals from a bank account'),
  ('ACCOUNT_TRANSFER','ACCOUNT_TRANSFER','General outbound transfers to another account'),
  ('SWEEP_OUT','Sweep out',''),
  ('OTHER_TRANSFER_OUT','OTHER_TRANSFER_OUT','Other miscellaneous outbound transactions')
) AS sc(code,name,description) ON TRUE
ON CONFLICT (category_id, code) DO UPDATE
SET name = EXCLUDED.name,
    description = EXCLUDED.description,
    updated_at = now();

-- LOAN_PAYMENTS
WITH c AS (SELECT id, code FROM spendsense.category WHERE code = 'LOAN_PAYMENTS')
INSERT INTO spendsense.subcategory (category_id, code, name, description)
SELECT c.id, sc.code, sc.name, sc.description
FROM c
JOIN (VALUES
  ('CAR_PAYMENT','LOAN_PAYMENTS_CAR_PAYMENT','Car loans and leases'),
  ('CREDIT_CARD_PAYMENT','LOAN_PAYMENTS_CREDIT_CARD_PAYMENT','Payments to a credit card (positive for credit card subtypes, negative for depository)'),
  ('PERSONAL_LOAN_PAYMENT','LOAN_PAYMENTS_PERSONAL_LOAN_PAYMENT','Personal loans, including cash advances and BNPL repayments'),
  ('MORTGAGE_PAYMENT','LOAN_PAYMENTS_MORTGAGE_PAYMENT','Payments on mortgages'),
  ('STUDENT_LOAN_PAYMENT','LOAN_PAYMENTS_STUDENT_LOAN_PAYMENT','Payments on student loans'),
  ('OTHER_PAYMENT','LOAN_PAYMENTS_OTHER_PAYMENT','Other miscellaneous debt payments')
) AS sc(code,name,description) ON TRUE
ON CONFLICT (category_id, code) DO UPDATE
SET name = EXCLUDED.name,
    description = EXCLUDED.description,
    updated_at = now();

-- UTILITIES
WITH c AS (SELECT id, code FROM spendsense.category WHERE code = 'UTILITIES')
INSERT INTO spendsense.subcategory (category_id, code, name, description)
SELECT c.id, sc.code, sc.name, sc.description
FROM c
JOIN (VALUES
  ('ELECTRICITY','ELECTRICITY','electricity bills'),
  ('GAS','Gas','Gas bill'),
  ('INTERNET_AND_CABLE','INTERNET_AND_CABLE','Internet and cable bills'),
  ('SEWAGE_AND_WASTE_MANAGEMENT','SEWAGE_AND_WASTE_MANAGEMENT','Sewage and garbage disposal bills'),
  ('MOBILE_TELEPHONE','Mobile/TELEPHONE','Cell phone bills'),
  ('WATER','WATER','Water bills'),
  ('OTHER_UTILITIES','OTHER_UTILITIES','Other miscellaneous utility bills')
) AS sc(code,name,description) ON TRUE
ON CONFLICT (category_id, code) DO UPDATE
SET name = EXCLUDED.name,
    description = EXCLUDED.description,
    updated_at = now();

-- RENT
WITH c AS (SELECT id, code FROM spendsense.category WHERE code = 'RENT')
INSERT INTO spendsense.subcategory (category_id, code, name, description)
SELECT c.id, 'RENT', 'RENT', 'Rent payment'
FROM c
ON CONFLICT (category_id, code) DO UPDATE
SET name = EXCLUDED.name, description = EXCLUDED.description, updated_at = now();

-- BANK_FEES
WITH c AS (SELECT id, code FROM spendsense.category WHERE code = 'BANK_FEES')
INSERT INTO spendsense.subcategory (category_id, code, name, description)
SELECT c.id, sc.code, sc.name, sc.description
FROM c
JOIN (VALUES
  ('ATM_FEES','BANK_FEES_ATM_FEES','Fees incurred for out-of-network ATMs'),
  ('FOREIGN_TRANSACTION_FEES','BANK_FEES_FOREIGN_TRANSACTION_FEES','Fees incurred on non-domestic transactions'),
  ('INSUFFICIENT_FUNDS','BANK_FEES_INSUFFICIENT_FUNDS','Fees relating to insufficient funds'),
  ('INTEREST_CHARGE','BANK_FEES_INTEREST_CHARGE','Interest on purchases or cash advances'),
  ('OVERDRAFT_FEES','BANK_FEES_OVERDRAFT_FEES','Fees incurred when an account is in overdraft'),
  ('OTHER_BANK_FEES','BANK_FEES_OTHER_BANK_FEES','Other miscellaneous bank fees')
) AS sc(code,name,description) ON TRUE
ON CONFLICT (category_id, code) DO UPDATE
SET name = EXCLUDED.name, description = EXCLUDED.description, updated_at = now();

-- ENTERTAINMENT
WITH c AS (SELECT id, code FROM spendsense.category WHERE code = 'ENTERTAINMENT')
INSERT INTO spendsense.subcategory (category_id, code, name, description)
SELECT c.id, sc.code, sc.name, sc.description
FROM c
JOIN (VALUES
  ('CASINOS_AND_GAMBLING','CASINOS_AND_GAMBLING','Gambling, casinos, and sports betting'),
  ('MUSIC_AND_AUDIO','MUSIC_AND_AUDIO','Music purchases and streaming'),
  ('SPORTING_EVENTS','SPORTING_EVENTS','Purchases at sporting events, venues, concerts'),
  ('AMUSEMENT_PARKS','AMUSEMENT_PARKS/ CIRCUS/MAGIC SHOW','Amusement parks, circus, magic shows'),
  ('MUSEUMS','MUSEUMS/ART EXHIBITIONS/','Museums and art exhibitions'),
  ('TV_AND_MOVIES','ENTERTAINMENT_TV_AND_MOVIES','Streaming services and theaters'),
  ('VIDEO_GAMES','ENTERTAINMENT_VIDEO_GAMES','Video games and VR'),
  ('OTHER_ENTERTAINMENT','ENTERTAINMENT_OTHER_ENTERTAINMENT','Night life and other entertainment'),
  ('ADVENTURE_SPORTS','Adventure sports','Skydiving, rock climbing, etc.')
) AS sc(code,name,description) ON TRUE
ON CONFLICT (category_id, code) DO UPDATE
SET name = EXCLUDED.name, description = EXCLUDED.description, updated_at = now();

-- DINING
WITH c AS (SELECT id, code FROM spendsense.category WHERE code = 'DINING')
INSERT INTO spendsense.subcategory (category_id, code, name, description)
SELECT c.id, sc.code, sc.name, sc.description
FROM c
JOIN (VALUES
  ('FAST_FOOD','FastFood Restaurants','Pick-and-go outlets: McDonald''s, KFC'),
  ('FINE_DINING','Fine Dining','Fine dining restaurants'),
  ('CASUAL_DINING','Casual Dining','Ala-carte restaurants'),
  ('BUFFET','Buffet Restaurants','Buffet Restaurants'),
  ('CAFES_BISTROS','Cafes and Bistros','Café lounges'),
  ('PUBS_BARS','Pubs and Bars','Pubs and Bars'),
  ('STREET_FOOD','Street Food','Street Food'),
  ('ONLINE_DELIVERY','Online Delivery','Food delivery like Swiggy, Zomato')
) AS sc(code,name,description) ON TRUE
ON CONFLICT (category_id, code) DO UPDATE
SET name = EXCLUDED.name, description = EXCLUDED.description, updated_at = now();

-- GROCERIES
WITH c AS (SELECT id, code FROM spendsense.category WHERE code = 'GROCERIES')
INSERT INTO spendsense.subcategory (category_id, code, name, description)
SELECT c.id, sc.code, sc.name, sc.description
FROM c
JOIN (VALUES
  ('HYPERMARKETS','HyperMarkets_','Chains like Spar, Lulu, D-Mart'),
  ('SUPERMARKETS','supermarkets_Department stores','Ratnadeep, Vijetha, Spencers'),
  ('MOM_AND_POP','Mom and pop Stores','Neighborhood kirana stores'),
  ('ONLINE_GROCERIES','Online Groceries','Grofers, BigBasket, Swiggy Instamart, Zepto, Blinkit'),
  ('VEG_FRUIT_STORES','Vegetable and fruits Stores','Pure-O-Natural and local fruit/veg vendors')
) AS sc(code,name,description) ON TRUE
ON CONFLICT (category_id, code) DO UPDATE
SET name = EXCLUDED.name, description = EXCLUDED.description, updated_at = now();

-- HOME_IMPROVEMENT
WITH c AS (SELECT id, code FROM spendsense.category WHERE code = 'HOME_IMPROVEMENT')
INSERT INTO spendsense.subcategory (category_id, code, name, description)
SELECT c.id, sc.code, sc.name, sc.description
FROM c
JOIN (VALUES
  ('FURNITURE','FURNITURE','Furniture, bedding, and home accessories'),
  ('HARDWARE','HARDWARE','Building materials, paint, wallpaper'),
  ('REPAIR_AND_MAINTENANCE','REPAIR_AND_MAINTENANCE','Plumbing, lighting, gardening, roofing'),
  ('SECURITY','SECURITY','Home security systems'),
  ('OTHER_HOME_IMPROVEMENT','OTHER_HOME_IMPROVEMENT','Pool installation, pest control, etc.')
) AS sc(code,name,description) ON TRUE
ON CONFLICT (category_id, code) DO UPDATE
SET name = EXCLUDED.name, description = EXCLUDED.description, updated_at = now();

-- MEDICAL
WITH c AS (SELECT id, code FROM spendsense.category WHERE code = 'MEDICAL')
INSERT INTO spendsense.subcategory (category_id, code, name, description)
SELECT c.id, sc.code, sc.name, sc.description
FROM c
JOIN (VALUES
  ('DENTAL_CARE','DENTAL_CARE','Dentists and dental care'),
  ('EYE_CARE','EYE_CARE','Optometrists, contacts, glasses'),
  ('NURSING_CARE','NURSING_CARE','Nursing care and facilities'),
  ('PHARMACIES_AND_SUPPLEMENTS','PHARMACIES_AND_SUPPLEMENTS','Pharmacies and nutrition shops'),
  ('PRIMARY_CARE','PRIMARY_CARE','Doctors and physicians'),
  ('MEDICAL_APPS','Medical APPs','Medical app payments'),
  ('OTHER_MEDICAL','OTHER_MEDICAL','Hospitals, blood work, ambulances')
) AS sc(code,name,description) ON TRUE
ON CONFLICT (category_id, code) DO UPDATE
SET name = EXCLUDED.name, description = EXCLUDED.description, updated_at = now();

-- PERSONAL_CARE
WITH c AS (SELECT id, code FROM spendsense.category WHERE code = 'PERSONAL_CARE')
INSERT INTO spendsense.subcategory (category_id, code, name, description)
SELECT c.id, sc.code, sc.name, sc.description
FROM c
JOIN (VALUES
  ('GYMS_AND_FITNESS_CENTERS','GYMS_AND_FITNESS_CENTERS','Gyms, fitness centers, workout classes'),
  ('HAIR_AND_SKIN_SERVICES','HAIR_AND_SKin SERVICES','Salon, spa/massage, grooming'),
  ('BEAUTY_PRODUCTS','Hair,skin, beauty and personal  Products','Bath, beauty & personal products'),
  ('LAUNDRY_AND_DRY_CLEANING','LAUNDRY_AND_DRY_CLEANING','Wash & fold, dry cleaning'),
  ('OTHER_PERSONAL_CARE','OTHER_PERSONAL_CARE','Other personal care, mental health apps/services')
) AS sc(code,name,description) ON TRUE
ON CONFLICT (category_id, code) DO UPDATE
SET name = EXCLUDED.name, description = EXCLUDED.description, updated_at = now();

-- GOVERNMENT_AND_NON_PROFIT
WITH c AS (SELECT id, code FROM spendsense.category WHERE code = 'GOVERNMENT_AND_NON_PROFIT')
INSERT INTO spendsense.subcategory (category_id, code, name, description)
SELECT c.id, sc.code, sc.name, sc.description
FROM c
JOIN (VALUES
  ('DONATIONS','DONATIONS','Charitable, political, and religious donations'),
  ('DEPARTMENTS_AND_AGENCIES','GOVERNMENT_DEPARTMENTS_AND_AGENCIES','Licenses, passport renewal'),
  ('TAX_PAYMENT','TAX_PAYMENT','Income and property taxes'),
  ('OTHER_GOV_NONPROFIT','OTHER_GOVERNMENT_AND_NON_PROFIT','Other government & non-profit payments')
) AS sc(code,name,description) ON TRUE
ON CONFLICT (category_id, code) DO UPDATE
SET name = EXCLUDED.name, description = EXCLUDED.description, updated_at = now();

-- TRANSPORTATION
WITH c AS (SELECT id, code FROM spendsense.category WHERE code = 'TRANSPORTATION')
INSERT INTO spendsense.subcategory (category_id, code, name, description)
SELECT c.id, sc.code, sc.name, sc.description
FROM c
JOIN (VALUES
  ('BIKES_AND_SCOOTERS','BIKES_AND_SCOOTERS','Bike and scooter rentals'),
  ('DIGITAL_APPS','TRANSPORATION_ DIGITAL_APPS','Ride apps: Uber, Ola'),
  ('PARKING','PARKING','Parking fees'),
  ('PUBLIC_TRANSIT','PUBLIC_TRANSIT','Rail, metro, bus'),
  ('TAXIS_AND_RIDE_SHARES','TAXIS_AND_RIDE_SHARES','Taxi and ride share'),
  ('TOLLS','TOLLS','Toll expenses'),
  ('OTHER_TRANSPORTATION','OTHER_TRANSPORTATION','Other transportation expenses')
) AS sc(code,name,description) ON TRUE
ON CONFLICT (category_id, code) DO UPDATE
SET name = EXCLUDED.name, description = EXCLUDED.description, updated_at = now();

-- TRAVEL
WITH c AS (SELECT id, code FROM spendsense.category WHERE code = 'TRAVEL')
INSERT INTO spendsense.subcategory (category_id, code, name, description)
SELECT c.id, sc.code, sc.name, sc.description
FROM c
JOIN (VALUES
  ('TRAVEL_FLIGHTS','TRAVEL_FLIGHTS','Airline expenses'),
  ('TRAVEL_LODGING','TRAVEL_LODGING','Hotels, motels, Airbnb'),
  ('TRAVEL_RENTAL_CARS','TRAVEL_RENTAL_CARS','Rental cars, charter buses, trucks'),
  ('TRAVEL_OTHER','TRAVEL_OTHER_TRAVEL','Other travel expenses')
) AS sc(code,name,description) ON TRUE
ON CONFLICT (category_id, code) DO UPDATE
SET name = EXCLUDED.name, description = EXCLUDED.description, updated_at = now();

-- GENERAL_MERCHANDISE
WITH c AS (SELECT id, code FROM spendsense.category WHERE code = 'GENERAL_MERCHANDISE')
INSERT INTO spendsense.subcategory (category_id, code, name, description)
SELECT c.id, sc.code, sc.name, sc.description
FROM c
JOIN (VALUES
  ('BOOKSTORES_AND_NEWSSTANDS','BOOKSTORES_AND_NEWSSTANDS','Books, magazines, news'),
  ('GIFTS_AND_NOVELTIES','GIFTS_AND_NOVELTIES','Photo, gifts, cards, florists'),
  ('OFFICE_SUPPLIES','OFFICE_SUPPLIES','Office goods'),
  ('ONLINE_MARKETPLACES','ONLINE_MARKETPLACES','Etsy, Ebay, Amazon'),
  ('SPORTING_GOODS','SPORTING_GOODS','Sporting goods, camping, outdoor'),
  ('SUPERSTORES','SUPERSTORES','Target, Walmart (groceries + general)'),
  ('TOBACCO_AND_VAPE','TOBACCO_AND_VAPE','Tobacco & vaping'),
  ('OTHER_GENERAL_MERCHANDISE','OTHER_GENERAL_MERCHANDISE','Toys, hobbies, arts & crafts')
) AS sc(code,name,description) ON TRUE
ON CONFLICT (category_id, code) DO UPDATE
SET name = EXCLUDED.name, description = EXCLUDED.description, updated_at = now();

-- GENERAL_SERVICES
WITH c AS (SELECT id, code FROM spendsense.category WHERE code = 'GENERAL_SERVICES')
INSERT INTO spendsense.subcategory (category_id, code, name, description)
SELECT c.id, sc.code, sc.name, sc.description
FROM c
JOIN (VALUES
  ('ACCOUNTING_AND_FINANCIAL_PLANNING','ACCOUNTING_AND_FINANCIAL_PLANNING','Financial planning, tax & accounting'),
  ('CONSULTING_AND_LEGAL','CONSULTING_AND_LEGAL','Consulting and legal services'),
  ('POSTAGE_AND_SHIPPING','POSTAGE_AND_SHIPPING','Mail, packaging, shipping'),
  ('STORAGE','STORAGE','Storage services & facilities'),
  ('OTHER_GENERAL_SERVICES','OTHER_GENERAL_SERVICES','Advertising, cloud storage, misc.')
) AS sc(code,name,description) ON TRUE
ON CONFLICT (category_id, code) DO UPDATE
SET name = EXCLUDED.name, description = EXCLUDED.description, updated_at = now();

-- SHOPPING
WITH c AS (SELECT id, code FROM spendsense.category WHERE code = 'SHOPPING')
INSERT INTO spendsense.subcategory (category_id, code, name, description)
SELECT c.id, sc.code, sc.name, sc.description
FROM c
JOIN (VALUES
  ('CLOTHING_AND_ACCESSORIES','CLOTHING_AND_ACCESSORIES','Apparel, shoes, jewelry (Investment)'),
  ('CONVENIENCE_STORES','CONVENIENCE_STORES','Purchases at convenience stores'),
  ('DEPARTMENT_STORES','DEPARTMENT_STORES','Retail—clothing & home goods'),
  ('DISCOUNT_STORES','DISCOUNT_STORES','Discount retailers'),
  ('ELECTRONICS','ELECTRONICS','Electronics stores & sites'),
  ('ONLINE_SHOPPING','Online shopping','Personal, household, toys, auto, books, media, home, kitchen; Amazon/Flipkart etc.')
) AS sc(code,name,description) ON TRUE
ON CONFLICT (category_id, code) DO UPDATE
SET name = EXCLUDED.name, description = EXCLUDED.description, updated_at = now();

-- CHILD_CARE
WITH c AS (SELECT id, code FROM spendsense.category WHERE code = 'CHILD_CARE')
INSERT INTO spendsense.subcategory (category_id, code, name, description)
SELECT c.id, sc.code, sc.name, sc.description
FROM c
JOIN (VALUES
  ('EDUCATION','Education','School/tuition fee for children'),
  ('CHILD_CARE_EXPENSES','Child care expenses','Day care and child care needs')
) AS sc(code,name,description) ON TRUE
ON CONFLICT (category_id, code) DO UPDATE
SET name = EXCLUDED.name, description = EXCLUDED.description, updated_at = now();

-- MOTOR_MAINTENANCE
WITH c AS (SELECT id, code FROM spendsense.category WHERE code = 'MOTOR_MAINTENANCE')
INSERT INTO spendsense.subcategory (category_id, code, name, description)
SELECT c.id, sc.code, sc.name, sc.description
FROM c
JOIN (VALUES
  ('AUTOMOTIVE_SERVICES','GENERAL_SERVICES_AUTOMOTIVE','Oil changes, washes, repairs, towing'),
  ('INSURANCE','GENERAL_SERVICES_INSURANCE','Auto insurance')
) AS sc(code,name,description) ON TRUE
ON CONFLICT (category_id, code) DO UPDATE
SET name = EXCLUDED.name, description = EXCLUDED.description, updated_at = now();

-- PETS
WITH c AS (SELECT id, code FROM spendsense.category WHERE code = 'PETS')
INSERT INTO spendsense.subcategory (category_id, code, name, description)
SELECT c.id, sc.code, sc.name, sc.description
FROM c
JOIN (VALUES
  ('GROOMING','Grooming','Grooming, boarding, bathing'),
  ('PET_FOOD','Pet Food Expenses','Pet Food Expenses'),
  ('VACCINATION','Vaccination','Pet vaccination expenses'),
  ('INSURANCE','Insurance','Pet insurance')
) AS sc(code,name,description) ON TRUE
ON CONFLICT (category_id, code) DO UPDATE
SET name = EXCLUDED.name, description = EXCLUDED.description, updated_at = now();

-- ASSETS & LIABILITIES (Balance Sheet style)
WITH c AS (SELECT id, code FROM spendsense.category WHERE code = 'ASSETS_LIABILITIES')
INSERT INTO spendsense.subcategory (category_id, code, name, description)
SELECT c.id, sc.code, sc.name, sc.description
FROM c
JOIN (VALUES
  ('CASH_IN_HAND_FD','Cash in Hand-FD','Cash / Fixed deposits'),
  ('INVESTMENTS_IN_FM','Investments in FM','Financial market investments'),
  ('HOUSE','House','Residential property (asset)'),
  ('GOLD','Gold','Gold holdings (asset)'),
  ('REAL_ESTATE','Real Estate','Real estate assets'),
  ('CAR','Car','Vehicle (asset)'),
  ('PERSONAL_LOAN','Personal Loan','Outstanding personal loan (liability)'),
  ('HOME_LOAN','Home Loan','Outstanding home loan (liability)'),
  ('CAR_LOAN','Car Loan','Outstanding car loan (liability)'),
  ('CREDIT_CARD_DEBT','Credit card debt','Credit card outstanding (liability)'),
  ('OTHER_LIABILITIES','other Liabilities','Other liabilities')
) AS sc(code,name,description) ON TRUE
ON CONFLICT (category_id, code) DO UPDATE
SET name = EXCLUDED.name, description = EXCLUDED.description, updated_at = now();

-- INVESTMENTS
WITH c AS (SELECT id, code FROM spendsense.category WHERE code = 'INVESTMENTS')
INSERT INTO spendsense.subcategory (category_id, code, name, description)
SELECT c.id, sc.code, sc.name, sc.description
FROM c
JOIN (VALUES
  ('MUTUAL_FUNDS','Mutual Funds','Mutual fund investments and transactions'),
  ('STOCKS','Stocks','Stock investments and transactions'),
  ('BONDS','Bonds','Bond investments and transactions'),
  ('ETFs','ETFs','Exchange-traded fund investments and transactions'),
  ('CRYPTOCURRENCY','Cryptocurrency','Cryptocurrency investments and transactions'),
  ('REITs','REITs','Real Estate Investment Trust investments and transactions'),
  ('RETIREMENT_ACCOUNTS','Retirement Accounts','401(k), IRA, and other retirement account investments'),
  ('INDEX_FUNDS','Index Funds','Index fund investments and transactions'),
  ('COMMODITIES','Commodities','Commodity investments (gold, silver, oil, etc.)'),
  ('OTHER_INVESTMENTS','Other Investments','Other miscellaneous investment types')
) AS sc(code,name,description) ON TRUE
ON CONFLICT (category_id, code) DO UPDATE
SET name = EXCLUDED.name, description = EXCLUDED.description, updated_at = now();

-- ============================================================================
-- 5) Helper View: Convenient view for admin UIs and queries
-- ============================================================================

DROP VIEW IF EXISTS spendsense.v_categories;

CREATE VIEW spendsense.v_categories AS
SELECT
  c.id              AS category_id,
  c.code            AS category_code,
  c.name            AS category_name,
  c.budget_bucket,
  s.id              AS subcategory_id,
  s.code            AS subcategory_code,
  s.name            AS subcategory_name,
  s.description
FROM spendsense.category c
LEFT JOIN spendsense.subcategory s ON s.category_id = c.id
ORDER BY c.name, s.name;

COMMENT ON VIEW spendsense.v_categories IS 'Convenient view joining categories and subcategories with all fields';

COMMIT;

-- ============================================================================
-- Migration complete
-- ============================================================================
-- This migration creates normalized category/subcategory tables with:
-- - Stable codes (UPPER_SNAKE_CASE) for programmatic access
-- - Human-readable names
-- - Budget buckets for grouping
-- - Descriptions for subcategories
-- - Idempotent UPSERT logic (safe to rerun)
-- ============================================================================

