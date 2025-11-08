-- =============================================================================
-- Monytix — BudgetPilot (MVP) : Full SQL Package
-- Version: 1.0
-- =============================================================================
BEGIN;
CREATE EXTENSION IF NOT EXISTS pgcrypto;
-- Ensure target schema for BudgetPilot objects
CREATE SCHEMA IF NOT EXISTS budgetpilot;
-- Resolve unqualified objects from these schemas in order (prefer budgetpilot)
SET search_path = budgetpilot, goal, spendsense, enrichment, core, public;

-- Optional: relocate previously created tables from spendsense to budgetpilot
DO $$
BEGIN
  IF to_regclass('spendsense.budget_plan_master') IS NOT NULL AND to_regclass('budgetpilot.budget_plan_master') IS NULL THEN
    EXECUTE 'ALTER TABLE spendsense.budget_plan_master SET SCHEMA budgetpilot';
  END IF;
  IF to_regclass('spendsense.user_budget_recommendation') IS NOT NULL AND to_regclass('budgetpilot.user_budget_recommendation') IS NULL THEN
    EXECUTE 'ALTER TABLE spendsense.user_budget_recommendation SET SCHEMA budgetpilot';
  END IF;
  IF to_regclass('spendsense.user_budget_commit') IS NOT NULL AND to_regclass('budgetpilot.user_budget_commit') IS NULL THEN
    EXECUTE 'ALTER TABLE spendsense.user_budget_commit SET SCHEMA budgetpilot';
  END IF;
  IF to_regclass('spendsense.user_budget_commit_goal_alloc') IS NOT NULL AND to_regclass('budgetpilot.user_budget_commit_goal_alloc') IS NULL THEN
    EXECUTE 'ALTER TABLE spendsense.user_budget_commit_goal_alloc SET SCHEMA budgetpilot';
  END IF;
  IF to_regclass('spendsense.user_goal_attributes') IS NOT NULL AND to_regclass('budgetpilot.user_goal_attributes') IS NULL THEN
    EXECUTE 'ALTER TABLE spendsense.user_goal_attributes SET SCHEMA budgetpilot';
  END IF;
  IF to_regclass('spendsense.budget_user_month_aggregate') IS NOT NULL AND to_regclass('budgetpilot.budget_user_month_aggregate') IS NULL THEN
    EXECUTE 'ALTER TABLE spendsense.budget_user_month_aggregate SET SCHEMA budgetpilot';
  END IF;
END$$;

-- ============================================================================
-- 0) SAFETY: Required upstream objects (references only, not created here)
-- - vw_txn_effective(user_id, txn_date, amount, direction, txn_type, major_category, merchant_id?)
-- - user_goals_master(user_id, goal_id, goal_category, goal_name, goal_type, linked_txn_type,
--   estimated_cost, target_date, current_savings, priority_rank, status)
-- - goal_category_master(goal_category, goal_name, default_horizon, policy_linked_txn_type,
--   is_mandatory_flag, suggested_min_amount_formula, display_order)
-- ============================================================================

-- ============================================================================
-- 1) TABLES
-- ============================================================================

-- 1.1 Plan templates (registry)
CREATE TABLE IF NOT EXISTS budget_plan_master (
  plan_code VARCHAR(40) PRIMARY KEY,
  name VARCHAR(100) NOT NULL,
  description TEXT,
  base_needs_pct NUMERIC(5,3) NOT NULL CHECK (base_needs_pct >= 0 AND base_needs_pct <= 1),
  base_wants_pct NUMERIC(5,3) NOT NULL CHECK (base_wants_pct >= 0 AND base_wants_pct <= 1),
  base_assets_pct NUMERIC(5,3) NOT NULL CHECK (base_assets_pct >= 0 AND base_assets_pct <= 1),
  eligibility_json JSONB NOT NULL DEFAULT '{}'::jsonb, -- rule hints (min_income, debt_flags, etc.)
  is_active BOOLEAN NOT NULL DEFAULT TRUE,
  display_order SMALLINT NOT NULL DEFAULT 100,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  CHECK (ROUND((base_needs_pct + base_wants_pct + base_assets_pct)::numeric, 3) = 1.000)
);

-- 1.2 Engine output (recommendations)
CREATE TABLE IF NOT EXISTS user_budget_recommendation (
  reco_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID NOT NULL,
  month DATE NOT NULL,
  plan_code VARCHAR(40) NOT NULL REFERENCES budget_plan_master(plan_code) ON UPDATE CASCADE,
  needs_budget_pct NUMERIC(5,3) NOT NULL CHECK (needs_budget_pct >= 0 AND needs_budget_pct <= 1),
  wants_budget_pct NUMERIC(5,3) NOT NULL CHECK (wants_budget_pct >= 0 AND wants_budget_pct <= 1),
  savings_budget_pct NUMERIC(5,3) NOT NULL CHECK (savings_budget_pct>= 0 AND savings_budget_pct<= 1),
  score NUMERIC(8,3) NOT NULL DEFAULT 0,
  recommendation_reason TEXT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  UNIQUE (user_id, month, plan_code)
);

-- 1.3 User commitment (chosen plan for a month)
CREATE TABLE IF NOT EXISTS user_budget_commit (
  user_id UUID NOT NULL,
  month DATE NOT NULL,
  plan_code VARCHAR(40) NOT NULL REFERENCES budget_plan_master(plan_code) ON UPDATE CASCADE,
  alloc_needs_pct NUMERIC(5,3) NOT NULL CHECK (alloc_needs_pct >= 0 AND alloc_needs_pct <= 1),
  alloc_wants_pct NUMERIC(5,3) NOT NULL CHECK (alloc_wants_pct >= 0 AND alloc_wants_pct <= 1),
  alloc_assets_pct NUMERIC(5,3) NOT NULL CHECK (alloc_assets_pct >= 0 AND alloc_assets_pct <= 1),
  notes TEXT,
  committed_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  PRIMARY KEY (user_id, month),
  CHECK (ROUND((alloc_needs_pct + alloc_wants_pct + alloc_assets_pct)::numeric, 3) = 1.000)
);

-- 1.4 Goal-level allocation (expanded from commit)
CREATE TABLE IF NOT EXISTS user_budget_commit_goal_alloc (
  ubcga_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID NOT NULL,
  month DATE NOT NULL,
  goal_id UUID NOT NULL,
  weight_pct NUMERIC(6,4) NOT NULL CHECK (weight_pct >= 0 AND weight_pct <= 1),
  planned_amount NUMERIC(14,2) NOT NULL DEFAULT 0,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  UNIQUE (user_id, month, goal_id)
);

-- 1.5 Derived attributes per goal (to help ranking & weighting)
CREATE TABLE IF NOT EXISTS user_goal_attributes (
  user_id UUID NOT NULL,
  goal_id UUID NOT NULL,
  essentiality_score SMALLINT NOT NULL CHECK (essentiality_score BETWEEN 0 AND 100),
  urgency_score SMALLINT NOT NULL CHECK (urgency_score BETWEEN 0 AND 100),
  dependency_score SMALLINT NOT NULL CHECK (dependency_score BETWEEN 0 AND 100),
  affordability_score SMALLINT NOT NULL CHECK (affordability_score BETWEEN 0 AND 100),
  suggested_monthly_amount NUMERIC(14,2) NOT NULL DEFAULT 0,
  computed_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  PRIMARY KEY (user_id, goal_id)
);

-- 1.6 Monthly aggregate (actuals vs plan)
CREATE TABLE IF NOT EXISTS budget_user_month_aggregate (
  user_id UUID NOT NULL,
  month DATE NOT NULL,
  income_amt NUMERIC(14,2) NOT NULL DEFAULT 0,
  needs_amt NUMERIC(14,2) NOT NULL DEFAULT 0,
  planned_needs_amt NUMERIC(14,2) NOT NULL DEFAULT 0,
  variance_needs_amt NUMERIC(14,2) NOT NULL DEFAULT 0,
  wants_amt NUMERIC(14,2) NOT NULL DEFAULT 0,
  planned_wants_amt NUMERIC(14,2) NOT NULL DEFAULT 0,
  variance_wants_amt NUMERIC(14,2) NOT NULL DEFAULT 0,
  assets_amt NUMERIC(14,2) NOT NULL DEFAULT 0,
  planned_assets_amt NUMERIC(14,2) NOT NULL DEFAULT 0,
  variance_assets_amt NUMERIC(14,2) NOT NULL DEFAULT 0,
  computed_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  PRIMARY KEY (user_id, month)
);

CREATE INDEX IF NOT EXISTS idx_ubcga_user_month ON user_budget_commit_goal_alloc(user_id, month);
CREATE INDEX IF NOT EXISTS idx_ubc_user_month ON user_budget_commit(user_id, month);
CREATE INDEX IF NOT EXISTS idx_ubmagg_user_month ON budget_user_month_aggregate(user_id, month);

-- ============================================================================
-- 2) SEED PLAN TEMPLATES
-- (You can tune weights later; sum must be 1.000)
-- ============================================================================
INSERT INTO budget_plan_master (plan_code, name, description, base_needs_pct, base_wants_pct, base_assets_pct, eligibility_json, is_active, display_order)
VALUES
  ('BAL_50_30_20','Balanced 50/30/20','Default balanced plan', 0.500, 0.300, 0.200, '{}', TRUE, 10),
  ('EMERGENCY_FIRST','Emergency Priority','Boost savings until emergency funded', 0.500, 0.200, 0.300, '{"require_emergency_goal":true}', TRUE, 20),
  ('DEBT_FIRST','Debt First','Aggressive needs to repay debt, shrink wants', 0.600, 0.150, 0.250, '{"debt_flag":true}', TRUE, 30),
  ('GOAL_PRIORITY','Top 3 Goals Priority','Assets tilt to top-3 goals', 0.450, 0.250, 0.300, '{"min_active_goals":1}', TRUE, 40),
  ('LEAN_BASICS','Lean Basics','Tighten wants, preserve savings', 0.550, 0.200, 0.250, '{}', TRUE, 50)
ON CONFLICT (plan_code) DO UPDATE
SET name = EXCLUDED.name,
    description = EXCLUDED.description,
    base_needs_pct = EXCLUDED.base_needs_pct,
    base_wants_pct = EXCLUDED.base_wants_pct,
    base_assets_pct = EXCLUDED.base_assets_pct,
    eligibility_json = EXCLUDED.eligibility_json,
    is_active = EXCLUDED.is_active,
    display_order = EXCLUDED.display_order,
    updated_at = NOW();

-- ============================================================================
-- 3) USER GOAL ATTRIBUTES (DERIVATION)
-- Parameters:
-- \set p_user_id 'aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa' -- UUID or NULL for all users
-- \set as_of_date '2025-10-01'
-- ============================================================================
-- Guards (psql): if not set, you can set defaults here
-- \set p_user_id NULL
-- \set as_of_date '2025-10-01'
WITH params AS (
  SELECT
    DATE '2025-10-01' AS as_of_date,
    NULL::uuid       AS p_user_id
),
goals AS (
  SELECT g.*,
         COALESCE(
           g.target_date,
           CASE g.goal_type
            WHEN 'short_term' THEN (date_trunc('month', (SELECT as_of_date FROM params)) + INTERVAL '18 months')::date
            WHEN 'medium_term' THEN (date_trunc('month', (SELECT as_of_date FROM params)) + INTERVAL '42 months')::date
            WHEN 'long_term' THEN (date_trunc('month', (SELECT as_of_date FROM params)) + INTERVAL '96 months')::date
           END
         ) AS effective_target_date
  FROM goal.user_goals_master g
  WHERE ((SELECT p_user_id FROM params) IS NULL OR g.user_id = (SELECT p_user_id FROM params))
    AND g.status = 'active'
),
cat AS (
  SELECT goal_category, goal_name, is_mandatory_flag, policy_linked_txn_type
  FROM goal.goal_category_master
),
income AS (
  -- avg monthly income over last 3 full months before as_of_date
  SELECT v.user_id, AVG(m_income) AS avg_income_mo
  FROM (
    SELECT user_id,
           date_trunc('month', txn_date) AS m,
           SUM(CASE WHEN txn_type='income' THEN amount ELSE 0 END) AS m_income
    FROM spendsense.vw_txn_effective
    WHERE txn_date >= date_trunc('month', (SELECT as_of_date FROM params)) - INTERVAL '3 months'
      AND txn_date <  date_trunc('month', (SELECT as_of_date FROM params))
    GROUP BY user_id, date_trunc('month', txn_date)
  ) v
  GROUP BY v.user_id
),
scored AS (
  SELECT g.user_id, g.goal_id, g.goal_category, g.goal_name, g.goal_type,
         g.estimated_cost, g.current_savings,
         GREATEST(1, CEIL(EXTRACT(EPOCH FROM (g.effective_target_date::timestamp - (SELECT as_of_date FROM params)::timestamp)) / (30*24*3600)))::int AS months_remaining,
         COALESCE(i.avg_income_mo, 0) AS avg_income_mo,
         COALESCE(c.is_mandatory_flag, false) AS is_mandatory_flag,
         COALESCE(g.linked_txn_type, c.policy_linked_txn_type) AS eff_linked_txn_type
  FROM goals g
  LEFT JOIN cat c ON c.goal_category=g.goal_category AND c.goal_name=g.goal_name
  LEFT JOIN income i ON i.user_id=g.user_id
),
calc AS (
  SELECT s.*,
         CASE WHEN s.is_mandatory_flag THEN 100
              WHEN s.eff_linked_txn_type = 'needs' THEN 60
              WHEN s.eff_linked_txn_type = 'assets' THEN 30
              ELSE 15 END AS essentiality_score,
         CASE WHEN s.months_remaining <= 6 THEN 100
              WHEN s.months_remaining <= 12 THEN 80
              WHEN s.months_remaining <= 24 THEN 60
              WHEN s.months_remaining <= 36 THEN 40
              ELSE 20 END AS urgency_score,
         CASE WHEN LOWER(s.goal_category) IN ('education','parents_care','term_insurance','health_insurance') THEN 80
              ELSE 30 END AS dependency_score,
         CASE WHEN s.avg_income_mo > 0 THEN LEAST(100, GREATEST(0, 100 - 100 * ((GREATEST(0, s.estimated_cost - s.current_savings) / s.months_remaining) / NULLIF(s.avg_income_mo,0))))
              ELSE 50 END AS affordability_score,
         ROUND(GREATEST(0, s.estimated_cost - s.current_savings) / NULLIF(s.months_remaining,0), 2) AS suggested_monthly_amount
  FROM scored s
)
INSERT INTO user_goal_attributes (user_id, goal_id, essentiality_score, urgency_score, dependency_score, affordability_score, suggested_monthly_amount, computed_at)
SELECT c.user_id, c.goal_id, c.essentiality_score, c.urgency_score, c.dependency_score, c.affordability_score, c.suggested_monthly_amount, NOW()
FROM calc c
ON CONFLICT (user_id, goal_id) DO UPDATE
SET essentiality_score = EXCLUDED.essentiality_score,
    urgency_score = EXCLUDED.urgency_score,
    dependency_score = EXCLUDED.dependency_score,
    affordability_score = EXCLUDED.affordability_score,
    suggested_monthly_amount = EXCLUDED.suggested_monthly_amount,
    computed_at = NOW();

-- ============================================================================
-- 4) SUGGESTION ENGINE → user_budget_recommendation
-- Parameters:
-- \set p_user_id 'aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa'
-- \set p_month '2025-10-01'
-- Strategy:
-- - Read last full month actuals (or same month if already in-progress)
-- - Compute wants% and assets% shares
-- - Detect emergency fund presence and underfunding
-- - Score 5 plan templates and output Top-N (here insert all with scores)
-- ============================================================================
WITH params AS (
  SELECT
    NULL::uuid        AS p_user_id,
    DATE '2025-10-01' AS p_month
),
m AS (
  SELECT date_trunc('month', (SELECT p_month FROM params)) AS month
),
actual AS (
  SELECT v.user_id,
         date_trunc('month', v.txn_date) AS month,
         SUM(CASE WHEN txn_type='income' AND direction='credit' THEN amount ELSE 0 END) AS income_amt,
         SUM(CASE WHEN txn_type='wants'  AND direction='debit'  THEN amount ELSE 0 END) AS wants_amt,
         SUM(CASE WHEN txn_type='assets' AND direction='debit'  THEN amount ELSE 0 END) AS assets_amt
  FROM spendsense.vw_txn_effective v
  WHERE date_trunc('month', v.txn_date) = (SELECT month FROM m)
    AND ((SELECT p_user_id FROM params) IS NULL OR v.user_id = (SELECT p_user_id FROM params))
  GROUP BY v.user_id, date_trunc('month', v.txn_date)
),
ratios AS (
  SELECT a.user_id, a.month, a.income_amt,
         CASE WHEN a.income_amt > 0 THEN a.wants_amt  / a.income_amt ELSE NULL END AS wants_share,
         CASE WHEN a.income_amt > 0 THEN a.assets_amt / a.income_amt ELSE NULL END AS assets_share
  FROM actual a
),
emergency_goal AS (
  SELECT g.user_id,
         MAX(CASE WHEN LOWER(g.goal_category) = 'emergency' THEN 1 ELSE 0 END) AS has_emergency,
         SUM(CASE WHEN LOWER(g.goal_category) = 'emergency' THEN GREATEST(0, g.estimated_cost - g.current_savings) ELSE 0 END) AS emergency_gap
  FROM goal.user_goals_master g
  WHERE g.status='active'
    AND ((SELECT p_user_id FROM params) IS NULL OR g.user_id = (SELECT p_user_id FROM params))
  GROUP BY g.user_id
),
scores AS (
  -- Score each plan against user profile (simple weighted example)
  SELECT r.user_id, r.month, bpm.plan_code,
         bpm.base_needs_pct, bpm.base_wants_pct, bpm.base_assets_pct,
         COALESCE(r.wants_share, 0.30) AS wants_share,
         COALESCE(r.assets_share, 0.10) AS assets_share,
         COALESCE(eg.has_emergency, 0) AS has_emergency,
         COALESCE(eg.emergency_gap, 0) AS emergency_gap,
         (
           0.40 * (1 - ABS(bpm.base_wants_pct - COALESCE(r.wants_share, 0.30))) -- closer to current wants is better (less friction)
         + 0.30 * (CASE WHEN (COALESCE(r.assets_share,0.10) < 0.15 OR COALESCE(eg.emergency_gap,0) > 0)
                        THEN (bpm.base_assets_pct) ELSE 0.0 END) -- prefer higher assets when underfunded
         + 0.15 * (CASE WHEN bpm.plan_code = 'BAL_50_30_20' THEN 1 ELSE 0 END) -- baseline bias
         + 0.15 * (CASE WHEN bpm.plan_code = 'EMERGENCY_FIRST' AND COALESCE(eg.emergency_gap,0) > 0 THEN 1 ELSE 0 END)
         )::numeric(8,3) AS score
  FROM ratios r
  JOIN budget_plan_master bpm ON bpm.is_active = TRUE
  LEFT JOIN emergency_goal eg ON eg.user_id = r.user_id
),
chosen AS (
  -- convert template pcts directly to recommendation pcts (MVP)
  SELECT s.user_id, s.month, s.plan_code,
         s.base_needs_pct AS needs_budget_pct,
         s.base_wants_pct AS wants_budget_pct,
         s.base_assets_pct AS savings_budget_pct,
         s.score,
         CASE
           WHEN s.plan_code = 'EMERGENCY_FIRST' AND s.emergency_gap > 0 THEN 'Emergency gap detected; increase savings to accelerate buffer.'
           WHEN s.plan_code = 'DEBT_FIRST' THEN 'Constrain wants and push needs to accelerate debt payoff.'
           WHEN s.plan_code = 'GOAL_PRIORITY' THEN 'Direct more savings toward your top priorities.'
           WHEN s.plan_code = 'LEAN_BASICS' THEN 'Tighten wants temporarily; keep savings momentum.'
           ELSE 'Balanced budgeting for stability.'
         END AS recommendation_reason
  FROM scores s
)
INSERT INTO user_budget_recommendation (user_id, month, plan_code, needs_budget_pct, wants_budget_pct, savings_budget_pct, score, recommendation_reason)
SELECT c.user_id, c.month, c.plan_code, c.needs_budget_pct, c.wants_budget_pct, c.savings_budget_pct, c.score, c.recommendation_reason
FROM chosen c
ON CONFLICT (user_id, month, plan_code) DO UPDATE
SET needs_budget_pct = EXCLUDED.needs_budget_pct,
    wants_budget_pct = EXCLUDED.wants_budget_pct,
    savings_budget_pct = EXCLUDED.savings_budget_pct,
    score = EXCLUDED.score,
    recommendation_reason = EXCLUDED.recommendation_reason;

-- ============================================================================
-- 5) USER COMMIT FROM A RECOMMENDATION
-- Parameters:
-- \set p_user_id 'aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa'
-- \set p_month '2025-10-01'
-- \set p_reco_plan_code 'EMERGENCY_FIRST' -- plan_code chosen
-- \set p_notes 'Committed from suggestions'
-- ============================================================================
WITH params AS (
  SELECT
    'aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa'::uuid AS p_user_id,
    DATE '2025-10-01'                           AS p_month,
    'EMERGENCY_FIRST'                           AS p_reco_plan_code,
    'Committed from suggestions'                AS p_notes
),
r AS (
  SELECT *
  FROM user_budget_recommendation
  WHERE user_id = (SELECT p_user_id FROM params)
    AND month = date_trunc('month', (SELECT p_month FROM params))
    AND plan_code = (SELECT p_reco_plan_code FROM params)
),
upsert_commit AS (
  INSERT INTO user_budget_commit (user_id, month, plan_code, alloc_needs_pct, alloc_wants_pct, alloc_assets_pct, notes, committed_at)
  SELECT r.user_id, r.month, r.plan_code, r.needs_budget_pct, r.wants_budget_pct, r.savings_budget_pct, (SELECT p_notes FROM params), NOW()
  FROM r
  ON CONFLICT (user_id, month) DO UPDATE
  SET plan_code = EXCLUDED.plan_code,
      alloc_needs_pct = EXCLUDED.alloc_needs_pct,
      alloc_wants_pct = EXCLUDED.alloc_wants_pct,
      alloc_assets_pct = EXCLUDED.alloc_assets_pct,
      notes = EXCLUDED.notes,
      committed_at = NOW()
  RETURNING user_id, month, plan_code, alloc_assets_pct
),
active_goals AS (
  SELECT g.user_id, g.goal_id, g.priority_rank,
         COALESCE(ua.essentiality_score, 50) AS ess,
         COALESCE(ua.urgency_score, 50) AS urg
  FROM goal.user_goals_master g
  LEFT JOIN user_goal_attributes ua ON ua.user_id=g.user_id AND ua.goal_id=g.goal_id
  WHERE g.user_id = (SELECT p_user_id FROM params)
    AND g.status = 'active'
),
weights AS (
  -- weight by (priority inverse) + essentials + urgency
  SELECT ag.user_id, ag.goal_id,
         ((CASE WHEN ag.priority_rank IS NOT NULL THEN (6 - LEAST(5, GREATEST(1, ag.priority_rank))) ELSE 3 END)
           + ag.ess/25.0
           + ag.urg/25.0
         )::numeric AS raw_w
  FROM active_goals ag
),
norm AS (
  SELECT w.user_id, w.goal_id,
         CASE WHEN SUM(w2.raw_w) OVER (PARTITION BY w.user_id) > 0
              THEN ROUND(w.raw_w / SUM(w2.raw_w) OVER (PARTITION BY w.user_id), 4)
              ELSE 0 END AS weight_pct
  FROM weights w
  JOIN weights w2 ON w2.user_id=w.user_id
),
income_est AS (
  -- Use current month income as base envelope
  SELECT a.user_id, a.month, a.income_amt
  FROM (
    SELECT user_id,
           date_trunc('month', txn_date) AS month,
           SUM(CASE WHEN txn_type='income' AND direction='credit' THEN amount ELSE 0 END) AS income_amt
    FROM spendsense.vw_txn_effective
    WHERE date_trunc('month', txn_date) = date_trunc('month', (SELECT p_month FROM params))
      AND user_id = (SELECT p_user_id FROM params)
    GROUP BY user_id, date_trunc('month', txn_date)
  ) a
)
INSERT INTO user_budget_commit_goal_alloc (user_id, month, goal_id, weight_pct, planned_amount)
SELECT n.user_id,
       date_trunc('month', (SELECT p_month FROM params)),
       n.goal_id,
       n.weight_pct,
       ROUND(COALESCE(ie.income_amt,0) * ubc.alloc_assets_pct * n.weight_pct, 2) AS planned_amount
FROM norm n
CROSS JOIN upsert_commit ubc
LEFT JOIN income_est ie ON ie.user_id=n.user_id
ON CONFLICT (user_id, month, goal_id) DO UPDATE
SET weight_pct = EXCLUDED.weight_pct,
    planned_amount = EXCLUDED.planned_amount,
    created_at = NOW();

-- ============================================================================
-- 6) MONTHLY AGGREGATE (ACTUALS vs PLAN)
-- Parameters:
-- \set p_month '2025-10-01'
-- ============================================================================
WITH params AS (
  SELECT DATE '2025-10-01' AS p_month
),
m AS (
  SELECT date_trunc('month', (SELECT p_month FROM params)) AS month
),
actuals AS (
  SELECT user_id,
         date_trunc('month', txn_date) AS month,
         SUM(CASE WHEN txn_type='income' AND direction='credit' THEN amount ELSE 0 END) AS income_amt,
         SUM(CASE WHEN txn_type='needs'  AND direction='debit'  THEN amount ELSE 0 END) AS needs_amt,
         SUM(CASE WHEN txn_type='wants'  AND direction='debit'  THEN amount ELSE 0 END) AS wants_amt,
         SUM(CASE WHEN txn_type='assets' AND direction='debit'  THEN amount ELSE 0 END) AS assets_amt
  FROM spendsense.vw_txn_effective
  WHERE date_trunc('month', txn_date) = (SELECT month FROM m)
  GROUP BY user_id, date_trunc('month', txn_date)
),
plan AS (
  SELECT c.user_id, c.month, c.alloc_needs_pct, c.alloc_wants_pct, c.alloc_assets_pct
  FROM user_budget_commit c
  WHERE c.month = (SELECT month FROM m)
),
joined AS (
  SELECT a.user_id, a.month, a.income_amt, a.needs_amt, a.wants_amt, a.assets_amt,
         p.alloc_needs_pct, p.alloc_wants_pct, p.alloc_assets_pct
  FROM actuals a
  LEFT JOIN plan p ON p.user_id=a.user_id AND p.month=a.month
),
planned_values AS (
  SELECT j.*,
         ROUND(COALESCE(j.income_amt,0) * COALESCE(j.alloc_needs_pct,0), 2) AS planned_needs_amt,
         ROUND(COALESCE(j.income_amt,0) * COALESCE(j.alloc_wants_pct,0), 2) AS planned_wants_amt,
         ROUND(COALESCE(j.income_amt,0) * COALESCE(j.alloc_assets_pct,0), 2) AS planned_assets_amt
  FROM joined j
)
INSERT INTO budget_user_month_aggregate (
  user_id, month, income_amt,
  needs_amt, planned_needs_amt, variance_needs_amt,
  wants_amt, planned_wants_amt, variance_wants_amt,
  assets_amt, planned_assets_amt, variance_assets_amt,
  computed_at
)
SELECT p.user_id, p.month, p.income_amt,
       p.needs_amt,  p.planned_needs_amt,  ROUND(p.needs_amt  - p.planned_needs_amt,  2),
       p.wants_amt,  p.planned_wants_amt,  ROUND(p.wants_amt  - p.planned_wants_amt,  2),
       p.assets_amt, p.planned_assets_amt, ROUND(p.assets_amt - p.planned_assets_amt, 2),
       NOW()
FROM planned_values p
ON CONFLICT (user_id, month) DO UPDATE
SET income_amt = EXCLUDED.income_amt,
    needs_amt = EXCLUDED.needs_amt,
    planned_needs_amt = EXCLUDED.planned_needs_amt,
    variance_needs_amt = EXCLUDED.variance_needs_amt,
    wants_amt = EXCLUDED.wants_amt,
    planned_wants_amt = EXCLUDED.planned_wants_amt,
    variance_wants_amt = EXCLUDED.variance_wants_amt,
    assets_amt = EXCLUDED.assets_amt,
    planned_assets_amt = EXCLUDED.planned_assets_amt,
    variance_assets_amt = EXCLUDED.variance_assets_amt,
    computed_at = NOW();

COMMIT;

-- =============================================================================
-- HOW TO RUN (psql):
-- \set p_user_id 'aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa'
-- \set p_month '2025-10-01'
-- \set as_of_date '2025-10-01'
-- Then \i budgetpilot_full_package.sql
-- Re-run sections (3..6) as needed after new data arrives.
-- =============================================================================


