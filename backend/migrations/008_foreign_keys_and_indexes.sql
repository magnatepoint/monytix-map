-- =========================================================
-- Foreign Keys and Indexes Migration
-- Combines: 008_ensure_foreign_keys.sql, 009_add_optional_relationships.sql, 010_add_remaining_foreign_keys.sql
-- Ensures all foreign key constraints exist + housekeeping fixes
-- =========================================================

-- ============================================================================
-- 1) Normalize created_at defaults (use now() instead of NOW())
-- ============================================================================
ALTER TABLE spendsense.api_request_log
  ALTER COLUMN created_at SET DEFAULT now();

ALTER TABLE spendsense.app_events
  ALTER COLUMN created_at SET DEFAULT now();

ALTER TABLE spendsense.integration_events
  ALTER COLUMN created_at SET DEFAULT now();

-- ============================================================================
-- 2) Auto-update updated_at on parser_rules (if table exists)
-- ============================================================================
CREATE OR REPLACE FUNCTION spendsense.tg_set_updated_at()
RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  NEW.updated_at := now();
  RETURN NEW;
END $$;

DO $$
BEGIN
  -- Check if parser_rules table exists
  IF EXISTS (
    SELECT 1 FROM information_schema.tables
    WHERE table_schema = 'spendsense' AND table_name = 'parser_rules'
  ) THEN
    -- Check if trigger already exists
    IF NOT EXISTS (
      SELECT 1 FROM pg_trigger
      WHERE tgname = 'tr_parser_rules_set_updated_at'
    ) THEN
      CREATE TRIGGER tr_parser_rules_set_updated_at
      BEFORE UPDATE ON spendsense.parser_rules
      FOR EACH ROW EXECUTE FUNCTION spendsense.tg_set_updated_at();
    END IF;
  END IF;
END $$;

-- ============================================================================
-- 3) Add missing foreign keys that help the visualizer
-- (Only if they don't already exist)
-- ============================================================================
DO $$
DECLARE v_exists boolean;
BEGIN
  -- kpi_category_monthly.category_code -> dim_category.category_code
  IF EXISTS (
    SELECT 1 FROM information_schema.tables
    WHERE table_schema = 'spendsense' AND table_name = 'kpi_category_monthly'
  ) THEN
    SELECT EXISTS (
      SELECT 1 FROM information_schema.table_constraints
      WHERE table_schema = 'spendsense' AND table_name = 'kpi_category_monthly'
        AND constraint_name = 'fk_kpi_category_monthly_category'
    ) INTO v_exists;
    
    IF NOT v_exists THEN
      ALTER TABLE spendsense.kpi_category_monthly
        ADD CONSTRAINT fk_kpi_category_monthly_category
        FOREIGN KEY (category_code)
        REFERENCES spendsense.dim_category(category_code)
        ON UPDATE CASCADE;
    END IF;
  END IF;

  -- kpi_spending_leaks_monthly.category_code -> dim_category.category_code
  IF EXISTS (
    SELECT 1 FROM information_schema.tables
    WHERE table_schema = 'spendsense' AND table_name = 'kpi_spending_leaks_monthly'
  ) THEN
    SELECT EXISTS (
      SELECT 1 FROM information_schema.table_constraints
      WHERE table_schema = 'spendsense' AND table_name = 'kpi_spending_leaks_monthly'
        AND constraint_name = 'fk_kpi_leaks_monthly_category'
    ) INTO v_exists;
    
    IF NOT v_exists THEN
      ALTER TABLE spendsense.kpi_spending_leaks_monthly
        ADD CONSTRAINT fk_kpi_leaks_monthly_category
        FOREIGN KEY (category_code)
        REFERENCES spendsense.dim_category(category_code)
        ON UPDATE CASCADE;
    END IF;
  END IF;

  -- kpi_recurring_merchants_monthly.merchant_name_norm -> dim_merchant.normalized_name
  -- (valid because normalized_name is UNIQUE in dim_merchant)
  -- First, ensure missing merchants exist in dim_merchant to avoid FK violations
  IF EXISTS (
    SELECT 1 FROM information_schema.tables
    WHERE table_schema = 'spendsense' AND table_name = 'kpi_recurring_merchants_monthly'
  ) AND EXISTS (
    SELECT 1 FROM information_schema.tables
    WHERE table_schema = 'spendsense' AND table_name = 'dim_merchant'
  ) THEN
    -- Insert missing merchants into dim_merchant
    INSERT INTO spendsense.dim_merchant (merchant_name, normalized_name, active)
    SELECT DISTINCT
      kpi.merchant_name_norm AS merchant_name,
      kpi.merchant_name_norm AS normalized_name,
      TRUE AS active
    FROM spendsense.kpi_recurring_merchants_monthly kpi
    WHERE kpi.merchant_name_norm IS NOT NULL
      AND kpi.merchant_name_norm != ''
      AND NOT EXISTS (
        SELECT 1 FROM spendsense.dim_merchant dm
        WHERE dm.normalized_name = kpi.merchant_name_norm
      )
    ON CONFLICT (normalized_name) DO NOTHING;
    
    -- Now add the FK constraint (should work now that all merchants exist)
    SELECT EXISTS (
      SELECT 1 FROM information_schema.table_constraints
      WHERE table_schema = 'spendsense' AND table_name = 'kpi_recurring_merchants_monthly'
        AND constraint_name = 'fk_kpi_rec_merchants_dim_merchant'
    ) INTO v_exists;
    
    IF NOT v_exists THEN
      -- Verify no orphaned records exist before adding FK
      IF NOT EXISTS (
        SELECT 1 FROM spendsense.kpi_recurring_merchants_monthly kpi
        WHERE kpi.merchant_name_norm IS NOT NULL
          AND kpi.merchant_name_norm != ''
          AND NOT EXISTS (
            SELECT 1 FROM spendsense.dim_merchant dm
            WHERE dm.normalized_name = kpi.merchant_name_norm
          )
      ) THEN
        ALTER TABLE spendsense.kpi_recurring_merchants_monthly
          ADD CONSTRAINT fk_kpi_rec_merchants_dim_merchant
          FOREIGN KEY (merchant_name_norm)
          REFERENCES spendsense.dim_merchant(normalized_name)
          ON UPDATE CASCADE;
      ELSE
        RAISE NOTICE 'Skipping FK for kpi_recurring_merchants_monthly: orphaned records still exist';
      END IF;
    END IF;
  END IF;
END $$;

-- ============================================================================
-- 4) dim_merchant → dim_category, dim_subcategory (default references)
-- ============================================================================
DO $$
DECLARE
  orphaned_count INTEGER;
BEGIN
  -- Step 1: Clean up orphaned default_category_code references
  SELECT COUNT(*) INTO orphaned_count
  FROM spendsense.dim_merchant dm
  WHERE dm.default_category_code IS NOT NULL
    AND dm.default_category_code NOT IN (
      SELECT category_code FROM spendsense.dim_category
    );
  
  IF orphaned_count > 0 THEN
    UPDATE spendsense.dim_merchant
    SET default_category_code = NULL
    WHERE default_category_code IS NOT NULL
      AND default_category_code NOT IN (
        SELECT category_code FROM spendsense.dim_category
      );
    
    RAISE NOTICE 'NULLed out % orphaned default_category_code references', orphaned_count;
  END IF;

  -- Step 2: Fix orphaned default_subcategory_code references
  SELECT COUNT(*) INTO orphaned_count
  FROM spendsense.dim_merchant dm
  WHERE dm.default_subcategory_code IS NOT NULL
    AND dm.default_subcategory_code NOT IN (
      SELECT subcategory_code FROM spendsense.dim_subcategory
    );
  
  IF orphaned_count > 0 THEN
    -- Fix AJIO: shopping + apparel → apparel + app_ajio
    UPDATE spendsense.dim_merchant
    SET default_category_code = 'apparel',
        default_subcategory_code = 'app_ajio'
    WHERE normalized_name = 'ajio'
      AND default_subcategory_code = 'apparel'
      AND EXISTS (SELECT 1 FROM spendsense.dim_subcategory WHERE subcategory_code = 'app_ajio');
    
    -- Fix Myntra: shopping + apparel → apparel + app_myntra
    UPDATE spendsense.dim_merchant
    SET default_category_code = 'apparel',
        default_subcategory_code = 'app_myntra'
    WHERE normalized_name = 'myntra'
      AND default_subcategory_code = 'apparel'
      AND EXISTS (SELECT 1 FROM spendsense.dim_subcategory WHERE subcategory_code = 'app_myntra');
    
    -- Fix Amazon India: shopping + electronics → electronics + elec_amazon
    UPDATE spendsense.dim_merchant
    SET default_category_code = 'electronics',
        default_subcategory_code = 'elec_amazon'
    WHERE normalized_name = 'amazon'
      AND default_subcategory_code = 'electronics'
      AND EXISTS (SELECT 1 FROM spendsense.dim_subcategory WHERE subcategory_code = 'elec_amazon');
    
    -- Fix Flipkart: shopping + electronics → electronics + elec_flipkart
    UPDATE spendsense.dim_merchant
    SET default_category_code = 'electronics',
        default_subcategory_code = 'elec_flipkart'
    WHERE normalized_name = 'flipkart'
      AND default_subcategory_code = 'electronics'
      AND EXISTS (SELECT 1 FROM spendsense.dim_subcategory WHERE subcategory_code = 'elec_flipkart');
    
    -- For any remaining orphaned references, NULL them out
    UPDATE spendsense.dim_merchant
    SET default_subcategory_code = NULL
    WHERE default_subcategory_code IS NOT NULL
      AND default_subcategory_code NOT IN (
        SELECT subcategory_code FROM spendsense.dim_subcategory
      );
    
    RAISE NOTICE 'Fixed % orphaned default_subcategory_code references', orphaned_count;
  END IF;

  -- Step 3: Add FK for default_category_code
  IF NOT EXISTS (
    SELECT 1 FROM information_schema.table_constraints
    WHERE constraint_schema = 'spendsense'
    AND constraint_name = 'fk_dim_merchant_default_category'
    AND table_name = 'dim_merchant'
  ) THEN
    ALTER TABLE spendsense.dim_merchant
      ADD CONSTRAINT fk_dim_merchant_default_category
      FOREIGN KEY (default_category_code)
      REFERENCES spendsense.dim_category(category_code)
      ON UPDATE CASCADE
      ON DELETE SET NULL;
    
    RAISE NOTICE 'Added FK: dim_merchant.default_category_code → dim_category';
  END IF;

  -- Step 4: Add FK for default_subcategory_code
  IF NOT EXISTS (
    SELECT 1 FROM information_schema.table_constraints
    WHERE constraint_schema = 'spendsense'
    AND constraint_name = 'fk_dim_merchant_default_subcategory'
    AND table_name = 'dim_merchant'
  ) THEN
    ALTER TABLE spendsense.dim_merchant
      ADD CONSTRAINT fk_dim_merchant_default_subcategory
      FOREIGN KEY (default_subcategory_code)
      REFERENCES spendsense.dim_subcategory(subcategory_code)
      ON UPDATE CASCADE
      ON DELETE SET NULL;
    
    RAISE NOTICE 'Added FK: dim_merchant.default_subcategory_code → dim_subcategory';
  END IF;
END $$;

-- ============================================================================
-- 5) Integration Events → Upload Batch (soft relationship)
-- ============================================================================
DO $$
BEGIN
  IF EXISTS (
    SELECT 1 FROM information_schema.tables
    WHERE table_schema = 'spendsense' AND table_name = 'integration_events'
  ) AND EXISTS (
    SELECT 1 FROM information_schema.tables
    WHERE table_schema = 'spendsense' AND table_name = 'upload_batch'
  ) THEN
    -- Add index for ref_id lookups
    PERFORM 1 FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace
     WHERE c.relname = 'ix_integration_events_ref_id' AND n.nspname = 'spendsense';
    IF NOT FOUND THEN
      CREATE INDEX ix_integration_events_ref_id
        ON spendsense.integration_events (ref_id)
        WHERE ref_id IS NOT NULL;
    END IF;
  END IF;
END $$;

-- ============================================================================
-- 6) Helpful indexes for FK columns & JSON logs
-- ============================================================================
DO $$
BEGIN
  -- Index for kpi_category_monthly.category_code
  IF EXISTS (
    SELECT 1 FROM information_schema.tables
    WHERE table_schema = 'spendsense' AND table_name = 'kpi_category_monthly'
  ) THEN
    PERFORM 1 FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace
     WHERE c.relname = 'ix_kpi_category_monthly_category' AND n.nspname = 'spendsense';
    IF NOT FOUND THEN
      CREATE INDEX ix_kpi_category_monthly_category
        ON spendsense.kpi_category_monthly (category_code);
    END IF;
  END IF;

  -- Index for kpi_spending_leaks_monthly.category_code
  IF EXISTS (
    SELECT 1 FROM information_schema.tables
    WHERE table_schema = 'spendsense' AND table_name = 'kpi_spending_leaks_monthly'
  ) THEN
    PERFORM 1 FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace
     WHERE c.relname = 'ix_kpi_leaks_monthly_category' AND n.nspname = 'spendsense';
    IF NOT FOUND THEN
      CREATE INDEX ix_kpi_leaks_monthly_category
        ON spendsense.kpi_spending_leaks_monthly (category_code);
    END IF;
  END IF;

  -- Index for kpi_recurring_merchants_monthly.merchant_name_norm
  IF EXISTS (
    SELECT 1 FROM information_schema.tables
    WHERE table_schema = 'spendsense' AND table_name = 'kpi_recurring_merchants_monthly'
  ) THEN
    PERFORM 1 FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace
     WHERE c.relname = 'ix_kpi_rec_merchants_norm' AND n.nspname = 'spendsense';
    IF NOT FOUND THEN
      CREATE INDEX ix_kpi_rec_merchants_norm
        ON spendsense.kpi_recurring_merchants_monthly (merchant_name_norm);
    END IF;
  END IF;

  -- JSONB logs: fast querying with GIN indexes
  IF EXISTS (
    SELECT 1 FROM information_schema.tables
    WHERE table_schema = 'spendsense' AND table_name = 'api_request_log'
  ) THEN
    PERFORM 1 FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace
     WHERE c.relname = 'ix_api_request_log_req_payload' AND n.nspname = 'spendsense';
    IF NOT FOUND THEN
      CREATE INDEX ix_api_request_log_req_payload ON spendsense.api_request_log
        USING gin (req_payload);
    END IF;

    PERFORM 1 FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace
     WHERE c.relname = 'ix_api_request_log_res_payload' AND n.nspname = 'spendsense';
    IF NOT FOUND THEN
      CREATE INDEX ix_api_request_log_res_payload ON spendsense.api_request_log
        USING gin (res_payload);
    END IF;
  END IF;

  IF EXISTS (
    SELECT 1 FROM information_schema.tables
    WHERE table_schema = 'spendsense' AND table_name = 'app_events'
  ) THEN
    PERFORM 1 FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace
     WHERE c.relname = 'ix_app_events_event_props' AND n.nspname = 'spendsense';
    IF NOT FOUND THEN
      CREATE INDEX ix_app_events_event_props ON spendsense.app_events
        USING gin (event_props);
    END IF;
  END IF;

  -- KPI Tables → TxnFact (soft relationship via user_id + date)
  IF EXISTS (
    SELECT 1 FROM information_schema.tables
    WHERE table_schema = 'spendsense' AND table_name = 'kpi_type_split_daily'
  ) THEN
    PERFORM 1 FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace
     WHERE c.relname = 'ix_kpi_type_split_daily_user_date' AND n.nspname = 'spendsense';
    IF NOT FOUND THEN
      CREATE INDEX ix_kpi_type_split_daily_user_date
        ON spendsense.kpi_type_split_daily (user_id, dt);
    END IF;
  END IF;

  IF EXISTS (
    SELECT 1 FROM information_schema.tables
    WHERE table_schema = 'spendsense' AND table_name = 'kpi_type_split_monthly'
  ) THEN
    PERFORM 1 FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace
     WHERE c.relname = 'ix_kpi_type_split_monthly_user_month' AND n.nspname = 'spendsense';
    IF NOT FOUND THEN
      CREATE INDEX ix_kpi_type_split_monthly_user_month
        ON spendsense.kpi_type_split_monthly (user_id, month);
    END IF;
  END IF;

  IF EXISTS (
    SELECT 1 FROM information_schema.tables
    WHERE table_schema = 'spendsense' AND table_name = 'kpi_category_monthly'
  ) THEN
    PERFORM 1 FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace
     WHERE c.relname = 'ix_kpi_category_monthly_user_month' AND n.nspname = 'spendsense';
    IF NOT FOUND THEN
      CREATE INDEX ix_kpi_category_monthly_user_month
        ON spendsense.kpi_category_monthly (user_id, month);
    END IF;
  END IF;

  IF EXISTS (
    SELECT 1 FROM information_schema.tables
    WHERE table_schema = 'spendsense' AND table_name = 'kpi_spending_leaks_monthly'
  ) THEN
    PERFORM 1 FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace
     WHERE c.relname = 'ix_kpi_leaks_monthly_user_month' AND n.nspname = 'spendsense';
    IF NOT FOUND THEN
      CREATE INDEX ix_kpi_leaks_monthly_user_month
        ON spendsense.kpi_spending_leaks_monthly (user_id, month);
    END IF;
  END IF;

  IF EXISTS (
    SELECT 1 FROM information_schema.tables
    WHERE table_schema = 'spendsense' AND table_name = 'kpi_recurring_merchants_monthly'
  ) THEN
    PERFORM 1 FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace
     WHERE c.relname = 'ix_kpi_rec_merchants_user_month' AND n.nspname = 'spendsense';
    IF NOT FOUND THEN
      CREATE INDEX ix_kpi_rec_merchants_user_month
        ON spendsense.kpi_recurring_merchants_monthly (user_id, month);
    END IF;
  END IF;

  -- Logging Tables (app_events, api_request_log) → user_id indexes
  IF EXISTS (
    SELECT 1 FROM information_schema.tables
    WHERE table_schema = 'spendsense' AND table_name = 'app_events'
  ) THEN
    PERFORM 1 FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace
     WHERE c.relname = 'ix_app_events_user_id' AND n.nspname = 'spendsense';
    IF NOT FOUND THEN
      CREATE INDEX ix_app_events_user_id
        ON spendsense.app_events (user_id)
        WHERE user_id IS NOT NULL;
    END IF;
  END IF;

  IF EXISTS (
    SELECT 1 FROM information_schema.tables
    WHERE table_schema = 'spendsense' AND table_name = 'api_request_log'
  ) THEN
    PERFORM 1 FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace
     WHERE c.relname = 'ix_api_request_log_user_id' AND n.nspname = 'spendsense';
    IF NOT FOUND THEN
      CREATE INDEX ix_api_request_log_user_id
        ON spendsense.api_request_log (user_id)
        WHERE user_id IS NOT NULL;
    END IF;

    PERFORM 1 FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace
     WHERE c.relname = 'ix_api_request_log_api_name' AND n.nspname = 'spendsense';
    IF NOT FOUND THEN
      CREATE INDEX ix_api_request_log_api_name
        ON spendsense.api_request_log (api_name);
    END IF;
  END IF;

  -- Parser Rules (standalone, but add useful indexes)
  IF EXISTS (
    SELECT 1 FROM information_schema.tables
    WHERE table_schema = 'spendsense' AND table_name = 'parser_rules'
  ) THEN
    PERFORM 1 FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace
     WHERE c.relname = 'ix_parser_rules_bank_channel' AND n.nspname = 'spendsense';
    IF NOT FOUND THEN
      CREATE INDEX ix_parser_rules_bank_channel
        ON spendsense.parser_rules (bank, channel, active)
        WHERE active = TRUE;
    END IF;

    PERFORM 1 FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace
     WHERE c.relname = 'ix_parser_rules_priority' AND n.nspname = 'spendsense';
    IF NOT FOUND THEN
      CREATE INDEX ix_parser_rules_priority
        ON spendsense.parser_rules (priority DESC, active)
        WHERE active = TRUE;
    END IF;
  END IF;
END $$;

