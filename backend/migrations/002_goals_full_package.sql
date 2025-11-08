-- ============================================================================
-- Monytix — Goals Core (MVP) : Full SQL Package (adapted to goal schema)
-- Version: 1.0 (PostgreSQL 13+)
-- ============================================================================
BEGIN;
CREATE EXTENSION IF NOT EXISTS pgcrypto;

-- Ensure schema
CREATE SCHEMA IF NOT EXISTS goal;

-- ============================================================================
-- 1) TABLES
-- ============================================================================
-- 1.1 Master of goal categories/names and default policies
CREATE TABLE IF NOT EXISTS goal.goal_category_master (
  goal_category VARCHAR(50) NOT NULL,
  goal_name VARCHAR(80) NOT NULL,
  default_horizon VARCHAR(16) NOT NULL CHECK (default_horizon IN ('short_term','medium_term','long_term','life_stage','event')),
  policy_linked_txn_type VARCHAR(12) NOT NULL CHECK (policy_linked_txn_type IN ('needs','wants','assets')),
  is_mandatory_flag BOOLEAN NOT NULL DEFAULT FALSE,
  allow_linked_override BOOLEAN NOT NULL DEFAULT FALSE,
  suggested_min_amount_formula TEXT,
  display_order SMALLINT NOT NULL DEFAULT 100,
  active BOOLEAN NOT NULL DEFAULT TRUE,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  PRIMARY KEY (goal_category, goal_name)
);

CREATE INDEX IF NOT EXISTS idx_gcm_category ON goal.goal_category_master(goal_category, display_order);

-- 1.2 User goals catalog
CREATE TABLE IF NOT EXISTS goal.user_goals_master (
  goal_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID NOT NULL,
  goal_category VARCHAR(50) NOT NULL,
  goal_name VARCHAR(80) NOT NULL,
  goal_type VARCHAR(16) NOT NULL CHECK (goal_type IN ('short_term','medium_term','long_term')),
  linked_txn_type VARCHAR(12) CHECK (linked_txn_type IN ('needs','wants','assets')),
  estimated_cost NUMERIC(14,2) NOT NULL CHECK (estimated_cost >= 0),
  target_date DATE,
  current_savings NUMERIC(14,2) NOT NULL DEFAULT 0 CHECK (current_savings >= 0),
  importance SMALLINT CHECK (importance BETWEEN 1 AND 5),
  priority_rank SMALLINT CHECK (priority_rank BETWEEN 1 AND 5),
  allow_autolink_to_savings BOOLEAN NOT NULL DEFAULT TRUE,
  status VARCHAR(16) NOT NULL DEFAULT 'active' CHECK (status IN ('active','paused','completed','cancelled')),
  notes TEXT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  CONSTRAINT fk_gcm FOREIGN KEY(goal_category, goal_name)
    REFERENCES goal.goal_category_master(goal_category, goal_name) ON UPDATE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_ugm_user ON goal.user_goals_master(user_id);
CREATE INDEX IF NOT EXISTS idx_ugm_user_status ON goal.user_goals_master(user_id, status);
CREATE INDEX IF NOT EXISTS idx_ugm_target ON goal.user_goals_master(user_id, target_date);
CREATE INDEX IF NOT EXISTS idx_ugm_user_priority ON goal.user_goals_master(user_id, priority_rank);

-- Ensure columns exist when table was created earlier without them (idempotent safety)
ALTER TABLE goal.user_goals_master
  ADD COLUMN IF NOT EXISTS importance SMALLINT CHECK (importance BETWEEN 1 AND 5);
ALTER TABLE goal.user_goals_master
  ADD COLUMN IF NOT EXISTS allow_autolink_to_savings BOOLEAN NOT NULL DEFAULT TRUE;
ALTER TABLE goal.goal_category_master
  ADD COLUMN IF NOT EXISTS allow_linked_override BOOLEAN NOT NULL DEFAULT FALSE;

-- 1.3 Life Context (used by questionnaire for gating/recommendations)
CREATE TABLE IF NOT EXISTS goal.user_life_context (
  user_id UUID PRIMARY KEY,
  age_band VARCHAR(16) NOT NULL CHECK (age_band IN ('18-24','25-34','35-44','45-54','55+')),
  dependents_spouse BOOLEAN NOT NULL DEFAULT FALSE,
  dependents_children_count SMALLINT NOT NULL DEFAULT 0 CHECK (dependents_children_count >= 0),
  dependents_parents_care BOOLEAN NOT NULL DEFAULT FALSE,
  housing VARCHAR(24) NOT NULL CHECK (housing IN ('rent','own_mortgage','own_nomortgage')),
  employment VARCHAR(24) NOT NULL CHECK (employment IN ('salaried','self_employed','student','homemaker','retired')),
  income_regularity VARCHAR(16) NOT NULL CHECK (income_regularity IN ('very_stable','stable','variable')),
  region_code VARCHAR(16) NOT NULL,
  emergency_opt_out BOOLEAN NOT NULL DEFAULT FALSE,
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE OR REPLACE FUNCTION goal.touch_user_life_context_updated_at()
RETURNS TRIGGER AS $$
BEGIN
  NEW.updated_at = NOW();
  RETURN NEW;
END; $$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_ulc_updated ON goal.user_life_context;
CREATE TRIGGER trg_ulc_updated
BEFORE UPDATE ON goal.user_life_context
FOR EACH ROW EXECUTE FUNCTION goal.touch_user_life_context_updated_at();

-- ============================================================================
-- 2) SEED MASTER CATALOG (excerpt adapted; extend as needed)
-- ============================================================================
INSERT INTO goal.goal_category_master(goal_category, goal_name, default_horizon, policy_linked_txn_type, is_mandatory_flag, suggested_min_amount_formula, display_order)
VALUES
('Emergency','Emergency Fund','short_term','assets', TRUE, '3-6 months expenses', 10),
('Insurance','Term Insurance','long_term','needs', TRUE, 'Annual premium * 1', 20),
('Insurance','Health Insurance','long_term','needs', TRUE, 'Annual premium * 1', 21),
('Debt','Credit Card Paydown','short_term','needs', TRUE, 'High APR first (avalanche)', 30),
('Housing','Home Down Payment','medium_term','assets', FALSE, '20% of property value', 40),
('Education','Children Education','long_term','assets', TRUE, 'Corpus target', 50),
('Retirement','Retirement Corpus','long_term','assets', TRUE, 'Corpus target', 60),
('Travel','Vacation / Travel','short_term','wants', FALSE, 'Trip budget', 90),
('Lifestyle','New Smartphone','short_term','wants', FALSE, 'Device price', 100)
ON CONFLICT (goal_category, goal_name) DO UPDATE SET
  default_horizon = EXCLUDED.default_horizon,
  policy_linked_txn_type = EXCLUDED.policy_linked_txn_type,
  is_mandatory_flag = EXCLUDED.is_mandatory_flag,
  suggested_min_amount_formula = EXCLUDED.suggested_min_amount_formula,
  display_order = EXCLUDED.display_order,
  active = EXCLUDED.active,
  updated_at = NOW();

-- Custom goal placeholders to facilitate free-text custom entries
INSERT INTO goal.goal_category_master(goal_category, goal_name, default_horizon, policy_linked_txn_type, is_mandatory_flag, display_order, active)
VALUES
('Custom','Custom Goal (Short)','short_term','wants', FALSE, 900, TRUE),
('Custom','Custom Goal (Medium)','medium_term','wants', FALSE, 901, TRUE),
('Custom','Custom Goal (Long)','long_term','wants', FALSE, 902, TRUE)
ON CONFLICT (goal_category, goal_name) DO NOTHING;

-- ============================================================================
-- 3) DERIVATION FUNCTIONS & TRIGGERS
-- ============================================================================
-- 3.1 Derive linked_txn_type from policy when NULL or when category/name changes
CREATE OR REPLACE FUNCTION goal.fn_derive_linked_txn_type(p_category TEXT, p_name TEXT)
RETURNS VARCHAR AS $$
DECLARE v_type VARCHAR(12);
BEGIN
  SELECT policy_linked_txn_type INTO v_type
  FROM goal.goal_category_master
  WHERE goal_category = p_category AND goal_name = p_name;
  RETURN COALESCE(v_type, 'assets');
END;
$$ LANGUAGE plpgsql IMMUTABLE;

-- 3.2 Compute priority rank (1=highest..5=lowest) based on policy & goal_type
CREATE OR REPLACE FUNCTION goal.fn_compute_priority_rank(
  p_category TEXT,
  p_name TEXT,
  p_goal_type TEXT,
  p_linked_txn_type TEXT DEFAULT NULL
) RETURNS SMALLINT AS $$
DECLARE
  v_mandatory BOOLEAN;
  v_policy_type VARCHAR(12);
  v_score INT := 50;
  v_type VARCHAR(12);
BEGIN
  SELECT is_mandatory_flag, policy_linked_txn_type
  INTO v_mandatory, v_policy_type
  FROM goal.goal_category_master
  WHERE goal_category = p_category AND goal_name = p_name;

  v_type := COALESCE(p_linked_txn_type, v_policy_type, 'assets');
  IF v_mandatory THEN v_score := v_score + 40; END IF;
  IF p_goal_type = 'short_term' THEN v_score := v_score + 20;
  ELSIF p_goal_type = 'medium_term' THEN v_score := v_score + 10; END IF;
  IF v_type = 'needs' THEN v_score := v_score + 10;
  ELSIF v_type = 'wants' THEN v_score := v_score - 10; END IF;
  IF p_category IN ('Emergency','Contingency','Taxes','Insurance','Health','Debt','Utilities') THEN
    v_score := v_score + 10;
  ELSIF p_category IN ('Retirement','Education','Housing','Parents Care') THEN
    v_score := v_score + 5;
  END IF;
  IF v_score >= 80 THEN RETURN 1;
  ELSIF v_score >= 65 THEN RETURN 2;
  ELSIF v_score >= 50 THEN RETURN 3;
  ELSIF v_score >= 35 THEN RETURN 4;
  ELSE RETURN 5; END IF;
END;
$$ LANGUAGE plpgsql STABLE;

-- 3.3 Trigger: before insert/update on user_goals_master
CREATE OR REPLACE FUNCTION goal.trg_user_goals_master_biu()
RETURNS TRIGGER AS $$
BEGIN
  IF NEW.linked_txn_type IS NULL
     OR (TG_OP = 'UPDATE' AND (NEW.goal_category IS DISTINCT FROM OLD.goal_category OR NEW.goal_name IS DISTINCT FROM OLD.goal_name)) THEN
    NEW.linked_txn_type := goal.fn_derive_linked_txn_type(NEW.goal_category, NEW.goal_name);
  END IF;
  IF NEW.priority_rank IS NULL
     OR (TG_OP = 'UPDATE' AND (NEW.goal_category IS DISTINCT FROM OLD.goal_category OR NEW.goal_name IS DISTINCT FROM OLD.goal_name OR NEW.goal_type IS DISTINCT FROM OLD.goal_type OR NEW.linked_txn_type IS DISTINCT FROM OLD.linked_txn_type)) THEN
    NEW.priority_rank := goal.fn_compute_priority_rank(NEW.goal_category, NEW.goal_name, NEW.goal_type, NEW.linked_txn_type);
  END IF;
  NEW.updated_at := NOW();
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS biu_user_goals_master ON goal.user_goals_master;
CREATE TRIGGER biu_user_goals_master
BEFORE INSERT OR UPDATE ON goal.user_goals_master
FOR EACH ROW EXECUTE FUNCTION goal.trg_user_goals_master_biu();

-- ============================================================================
-- 4) VALIDATION & HELPERS
-- ============================================================================
DROP VIEW IF EXISTS goal.vw_goal_priority_explain;
DROP VIEW IF EXISTS goal.vw_user_goals_with_policy;
CREATE OR REPLACE VIEW goal.vw_user_goals_with_policy AS
SELECT
  u.user_id, u.goal_id, u.goal_category, u.goal_name, u.goal_type,
  u.linked_txn_type, u.priority_rank, u.importance, u.estimated_cost, u.target_date,
  u.current_savings, u.allow_autolink_to_savings, u.status,
  gcm.policy_linked_txn_type AS master_policy_type,
  gcm.is_mandatory_flag AS master_mandatory,
  gcm.default_horizon AS master_default_horizon
FROM goal.user_goals_master u
JOIN goal.goal_category_master gcm
  ON gcm.goal_category = u.goal_category AND gcm.goal_name = u.goal_name;

-- Explainability view (labels only; scoring can be computed app-side)
CREATE OR REPLACE VIEW goal.vw_goal_priority_explain AS
SELECT
  u.user_id,
  u.goal_id,
  u.goal_category,
  u.goal_name,
  u.goal_type,
  u.priority_rank,
  gcm.is_mandatory_flag AS safety_flag,
  (CASE WHEN u.goal_category = 'Debt' OR u.goal_name ILIKE '%Debt%' OR u.goal_name ILIKE '%Loan%'
        THEN TRUE ELSE FALSE END) AS liability_flag,
  u.target_date,
  u.importance,
  (u.allow_autolink_to_savings) AS autolink_enabled
FROM goal.user_goals_master u
JOIN goal.goal_category_master gcm
  ON gcm.goal_category = u.goal_category AND gcm.goal_name = u.goal_name;

CREATE INDEX IF NOT EXISTS idx_ugm_priority ON goal.user_goals_master(user_id, priority_rank, goal_type);

COMMIT;

