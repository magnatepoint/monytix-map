-- ============================================================================
-- Monytix — GoalCompass (MVP) : Full SQL Package
-- Version: 1.0 (PostgreSQL 13+)
-- ============================================================================
-- Upstream dependencies (not created here):
-- - goal.user_goals_master(user_id, goal_id, goal_category, goal_name, goal_type,
--   linked_txn_type, estimated_cost, target_date, current_savings, priority_rank, status, created_at, updated_at)
-- - budgetpilot.user_budget_commit_goal_alloc(user_id, month, goal_id, weight_pct, planned_amount)
-- - budgetpilot.budget_user_month_aggregate(user_id, month, income_amt, assets_amt, ...)
-- - spendsense.vw_txn_effective(user_id, txn_date, amount, direction, txn_type,
--   category_code, subcategory_code, merchant_name_norm)
-- ============================================================================
BEGIN;
CREATE EXTENSION IF NOT EXISTS pgcrypto;

-- Ensure target schema for GoalCompass objects
CREATE SCHEMA IF NOT EXISTS goalcompass;

-- Resolve unqualified objects from these schemas in order (prefer goalcompass)
SET search_path = goalcompass, budgetpilot, goal, spendsense, enrichment, core, public;

-- ============================================================================
-- 1) TABLES
-- ============================================================================
-- 1.1 Master milestones per goal category/name (generic templates)
CREATE TABLE IF NOT EXISTS goalcompass.goal_milestone_master (
  milestone_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  goal_category VARCHAR(50) NOT NULL,
  goal_name VARCHAR(80) NOT NULL,
  threshold_pct NUMERIC(5,2) NOT NULL CHECK (threshold_pct >= 0 AND threshold_pct <= 100),
  label VARCHAR(80) NOT NULL, -- e.g., "Kickoff", "25% Funded", "Halfway", "Fully Funded"
  description TEXT,
  display_order SMALLINT NOT NULL DEFAULT 100,
  UNIQUE (goal_category, goal_name, threshold_pct)
);

-- 1.2 User milestone status (what has been achieved for each goal)
CREATE TABLE IF NOT EXISTS goalcompass.user_goal_milestone_status (
  ugms_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID NOT NULL,
  goal_id UUID NOT NULL,
  milestone_id UUID NOT NULL REFERENCES goalcompass.goal_milestone_master(milestone_id) ON UPDATE CASCADE ON DELETE CASCADE,
  achieved_flag BOOLEAN NOT NULL DEFAULT FALSE,
  achieved_at TIMESTAMPTZ,
  progress_pct_at_ach NUMERIC(6,2),
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  UNIQUE (user_id, goal_id, milestone_id)
);

-- 1.3 Contributions applied to goals
-- MVP strategy: Distribute monthly 'assets' actuals proportionally by committed goal weights for that month.
CREATE TABLE IF NOT EXISTS goalcompass.goal_contribution_fact (
  gcf_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID NOT NULL,
  goal_id UUID NOT NULL,
  month DATE NOT NULL, -- first day of month
  source VARCHAR(24) NOT NULL CHECK (source IN ('proportional_assets','direct_txn','manual_adjust')),
  amount NUMERIC(14,2) NOT NULL DEFAULT 0,
  notes TEXT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  UNIQUE (user_id, goal_id, month, source)
);

-- 1.4 Goal snapshot (rolling status per month per goal)
CREATE TABLE IF NOT EXISTS goalcompass.goal_compass_snapshot (
  user_id UUID NOT NULL,
  goal_id UUID NOT NULL,
  month DATE NOT NULL, -- first day of month
  estimated_cost NUMERIC(14,2) NOT NULL,
  target_date DATE,
  starting_savings NUMERIC(14,2) NOT NULL DEFAULT 0, -- as recorded in goal.user_goals_master at goal creation or last override
  cumulative_contrib NUMERIC(14,2) NOT NULL DEFAULT 0, -- sum(goalcompass.goal_contribution_fact.amount up to month inclusive)
  progress_amount NUMERIC(14,2) NOT NULL DEFAULT 0, -- starting_savings + cumulative_contrib
  progress_pct NUMERIC(6,2) NOT NULL DEFAULT 0, -- progress_amount / estimated_cost * 100
  remaining_amount NUMERIC(14,2) NOT NULL DEFAULT 0, -- MAX(0, estimated_cost - progress_amount)
  months_remaining INTEGER, -- ceil months difference from month to target_date
  suggested_monthly_need NUMERIC(14,2), -- remaining_amount / months_remaining (min 1)
  on_track_flag BOOLEAN NOT NULL DEFAULT FALSE,
  risk_level VARCHAR(12) NOT NULL DEFAULT 'medium' CHECK (risk_level IN ('low','medium','high')),
  commentary TEXT,
  computed_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  PRIMARY KEY (user_id, goal_id, month)
);

CREATE INDEX IF NOT EXISTS idx_gcf_user_month ON goalcompass.goal_contribution_fact(user_id, month);
CREATE INDEX IF NOT EXISTS idx_gcs_user_month ON goalcompass.goal_compass_snapshot(user_id, month);

-- ============================================================================
-- 2) SEED MILESTONES (generic; feel free to extend per goal type)
-- ============================================================================
INSERT INTO goalcompass.goal_milestone_master (goal_category, goal_name, threshold_pct, label, description, display_order) VALUES
-- Emergency Fund
('Emergency','Emergency Fund', 1, 'Kickoff', 'You started your buffer!', 10),
('Emergency','Emergency Fund', 25, '25% Funded', 'Quarter-way to safety net', 20),
('Emergency','Emergency Fund', 50, 'Halfway', '50% of target saved', 30),
('Emergency','Emergency Fund', 75, '75% Funded', 'Almost there!', 40),
('Emergency','Emergency Fund',100, 'Fully Funded', 'Emergency fund target reached', 50),
-- Retirement (generic)
('Retirement','Retirement Corpus', 1, 'Kickoff', 'Investments for retirement started', 10),
('Retirement','Retirement Corpus', 25, '25% Milestone', 'Foundational base set', 20),
('Retirement','Retirement Corpus', 50, 'Halfway', 'Midway to corpus', 30),
('Retirement','Retirement Corpus', 75, '75% Milestone', 'Strong momentum', 40),
('Retirement','Retirement Corpus',100, 'Corpus Target', 'Target corpus achieved', 50),
-- Home Down Payment
('Housing','Home Down Payment', 1, 'Kickoff', 'Started saving for home down payment', 10),
('Housing','Home Down Payment', 25, '25% Saved', 'Good momentum', 20),
('Housing','Home Down Payment', 50, 'Halfway', 'Half of down payment in place', 30),
('Housing','Home Down Payment', 75, '75% Saved', 'Almost there', 40),
('Housing','Home Down Payment',100, 'Target Met', 'Down payment ready', 50),
-- Education (Children)
('Education','Children Education', 1, 'Kickoff', 'Started saving for education', 10),
('Education','Children Education', 25, '25% Saved', 'Quarter-way to target', 20),
('Education','Children Education', 50, 'Halfway', 'Midway to education fund', 30),
('Education','Children Education', 75, '75% Saved', 'Strong progress', 40),
('Education','Children Education',100, 'Target Met', 'Education fund ready', 50),
-- Travel (generic)
('Travel','Vacation / Travel', 1, 'Kickoff', 'Trip kitty started', 10),
('Travel','Vacation / Travel', 50, 'Halfway', 'Half saved for travel', 20),
('Travel','Vacation / Travel',100, 'Target Met', 'Travel target funded', 30)
ON CONFLICT (goal_category, goal_name, threshold_pct) DO NOTHING;

-- ============================================================================
-- 3) DERIVATION LOGIC
-- ============================================================================
-- Note: Sections 3.1, 3.3, and 3.4 use WITH params clauses with default values.
-- To customize, modify the date/user_id values in the params CTE at the start of each section.
-- Alternatively, you can use psql variables by replacing params with :p_user_id, :p_month, :as_of_date

-- 3.1 Contributions from proportional 'assets' actuals
-- Distribute monthly assets_amt from budgetpilot.budget_user_month_aggregate by goal weights in budgetpilot.user_budget_commit_goal_alloc
WITH params AS (
  SELECT
    NULL::uuid        AS p_user_id,  -- Set to specific UUID or NULL for all users
    DATE '2025-10-01' AS p_month      -- Set to target month (first day of month)
),
m AS (
  SELECT date_trunc('month', (SELECT p_month FROM params))::date AS month
),
assets_actual AS (
  SELECT b.user_id, b.month, b.assets_amt
  FROM budgetpilot.budget_user_month_aggregate b
  WHERE b.month = (SELECT month FROM m)
    AND ((SELECT p_user_id FROM params) IS NULL OR b.user_id = (SELECT p_user_id FROM params))
),
weights AS (
  SELECT g.user_id, g.month, g.goal_id, g.weight_pct
  FROM budgetpilot.user_budget_commit_goal_alloc g
  WHERE g.month = (SELECT month FROM m)
    AND ((SELECT p_user_id FROM params) IS NULL OR g.user_id = (SELECT p_user_id FROM params))
),
alloc AS (
  SELECT
    w.user_id, w.goal_id, w.month,
    ROUND(COALESCE(a.assets_amt,0) * w.weight_pct, 2) AS amount
  FROM weights w
  LEFT JOIN assets_actual a ON a.user_id=w.user_id AND a.month=w.month
)
INSERT INTO goalcompass.goal_contribution_fact (user_id, goal_id, month, source, amount, notes)
SELECT user_id, goal_id, month, 'proportional_assets', amount, 'Auto-distributed from assets actuals'
FROM alloc
WHERE amount > 0
ON CONFLICT (user_id, goal_id, month, source) DO UPDATE
SET amount = EXCLUDED.amount,
    notes = EXCLUDED.notes,
    created_at = NOW();

-- 3.2 OPTIONAL: Direct transaction mapping to a goal (not typical in MVP)
-- Example: If you tag a txn to a goal_id via overrides (future scope), you can load 'direct_txn' here.
-- INSERT ... goalcompass.goal_contribution_fact (source='direct_txn')

-- 3.3 Build Goal Snapshot for the month
WITH params AS (
  SELECT
    NULL::uuid        AS p_user_id,  -- Set to specific UUID or NULL for all users
    DATE '2025-10-01' AS p_month,     -- Set to target month (first day of month)
    DATE '2025-10-01' AS as_of_date   -- Decision date for months_remaining etc.
),
ug AS (
  SELECT g.*
  FROM goal.user_goals_master g
  WHERE g.status='active'
    AND ((SELECT p_user_id FROM params) IS NULL OR g.user_id = (SELECT p_user_id FROM params))
),
contrib_upto AS (
  -- all contributions up to current month (inclusive)
  SELECT c.user_id, c.goal_id,
    SUM(CASE WHEN c.month <= date_trunc('month', (SELECT p_month FROM params))::date THEN c.amount ELSE 0 END) AS cumulative_contrib
  FROM goalcompass.goal_contribution_fact c
  GROUP BY c.user_id, c.goal_id
),
base AS (
  SELECT
    u.user_id,
    u.goal_id,
    date_trunc('month', (SELECT p_month FROM params))::date AS month,
    u.estimated_cost,
    u.target_date,
    COALESCE(u.current_savings,0) AS starting_savings,
    COALESCE(c.cumulative_contrib,0) AS cumulative_contrib
  FROM ug u
  LEFT JOIN contrib_upto c ON c.user_id=u.user_id AND c.goal_id=u.goal_id
),
calc AS (
  SELECT
    b.*,
    ROUND(b.starting_savings + b.cumulative_contrib, 2) AS progress_amount,
    ROUND(CASE WHEN b.estimated_cost > 0 THEN 100.0 * (b.starting_savings + b.cumulative_contrib) / b.estimated_cost ELSE 0 END, 2) AS progress_pct,
    GREATEST(0, ROUND(b.estimated_cost - (b.starting_savings + b.cumulative_contrib), 2)) AS remaining_amount,
    CASE
      WHEN b.target_date IS NULL THEN NULL
      ELSE CEIL(EXTRACT(EPOCH FROM (b.target_date::timestamp - (SELECT as_of_date FROM params)::timestamp)) / (30*24*3600))::int
    END AS months_remaining
  FROM base b
),
with_suggested_need AS (
  SELECT
    c.*,
    ROUND(CASE WHEN COALESCE(c.months_remaining, 1) < 1 THEN c.remaining_amount
         WHEN c.remaining_amount > 0 THEN c.remaining_amount / NULLIF(c.months_remaining,0)
         ELSE 0 END, 2) AS suggested_monthly_need
  FROM calc c
),
finalized AS (
  SELECT
    w.*,
    CASE
      WHEN w.months_remaining IS NULL THEN FALSE
      WHEN w.remaining_amount <= 0 THEN TRUE
      WHEN w.suggested_monthly_need IS NULL THEN FALSE
      ELSE (
        -- Compare suggested monthly need vs current month planned assets for the goal (proxy)
        EXISTS (
          SELECT 1 FROM budgetpilot.user_budget_commit_goal_alloc ga
          WHERE ga.user_id=w.user_id AND ga.goal_id=w.goal_id AND ga.month=date_trunc('month', (SELECT p_month FROM params))::date
            AND ga.planned_amount >= (CASE WHEN w.months_remaining <= 0 THEN w.remaining_amount ELSE w.suggested_monthly_need END)
        )
      )
    END AS on_track_flag
  FROM with_suggested_need w
),
risked AS (
  SELECT
    f.*,
    CASE
      WHEN f.remaining_amount <= 0 THEN 'low'
      WHEN f.months_remaining IS NULL THEN 'medium'
      WHEN f.months_remaining <= 3 AND f.progress_pct < 60 THEN 'high'
      WHEN f.months_remaining <= 6 AND f.progress_pct < 70 THEN 'high'
      WHEN f.months_remaining <= 12 AND f.progress_pct < 40 THEN 'medium'
      ELSE 'low'
    END AS risk_level,
    CASE
      WHEN f.remaining_amount <= 0 THEN 'Goal funded. Consider locking gains or reallocating.'
      WHEN f.on_track_flag THEN 'On track based on current monthly plan.'
      ELSE 'Shortfall vs plan. Increase monthly contribution or extend target date.'
    END AS commentary
  FROM finalized f
)
INSERT INTO goalcompass.goal_compass_snapshot (
  user_id, goal_id, month, estimated_cost, target_date, starting_savings, cumulative_contrib,
  progress_amount, progress_pct, remaining_amount, months_remaining, suggested_monthly_need,
  on_track_flag, risk_level, commentary, computed_at
)
SELECT
  r.user_id, r.goal_id, r.month, r.estimated_cost, r.target_date, r.starting_savings, r.cumulative_contrib,
  r.progress_amount, r.progress_pct, r.remaining_amount, r.months_remaining, r.suggested_monthly_need,
  r.on_track_flag, r.risk_level, r.commentary, NOW()
FROM risked r
ON CONFLICT (user_id, goal_id, month) DO UPDATE
SET estimated_cost = EXCLUDED.estimated_cost,
    target_date = EXCLUDED.target_date,
    starting_savings = EXCLUDED.starting_savings,
    cumulative_contrib = EXCLUDED.cumulative_contrib,
    progress_amount = EXCLUDED.progress_amount,
    progress_pct = EXCLUDED.progress_pct,
    remaining_amount = EXCLUDED.remaining_amount,
    months_remaining = EXCLUDED.months_remaining,
    suggested_monthly_need = EXCLUDED.suggested_monthly_need,
    on_track_flag = EXCLUDED.on_track_flag,
    risk_level = EXCLUDED.risk_level,
    commentary = EXCLUDED.commentary,
    computed_at = NOW();

-- 3.4 Update milestone achievements based on latest snapshot
WITH params AS (
  SELECT
    NULL::uuid        AS p_user_id,  -- Set to specific UUID or NULL for all users
    DATE '2025-10-01' AS p_month      -- Set to target month (first day of month)
),
latest AS (
  SELECT s.user_id, s.goal_id, s.month, s.progress_pct
  FROM goalcompass.goal_compass_snapshot s
  WHERE s.month = date_trunc('month', (SELECT p_month FROM params))
    AND ((SELECT p_user_id FROM params) IS NULL OR s.user_id = (SELECT p_user_id FROM params))
),
targets AS (
  SELECT l.user_id, l.goal_id, l.progress_pct, mm.milestone_id, mm.threshold_pct
  FROM latest l
  JOIN goal.user_goals_master g ON g.user_id=l.user_id AND g.goal_id=l.goal_id
  JOIN goalcompass.goal_milestone_master mm
    ON mm.goal_category=g.goal_category AND mm.goal_name=g.goal_name
),
ach AS (
  SELECT t.*, (t.progress_pct >= t.threshold_pct) AS achieved_now
  FROM targets t
)
INSERT INTO goalcompass.user_goal_milestone_status (user_id, goal_id, milestone_id, achieved_flag, achieved_at, progress_pct_at_ach)
SELECT
  a.user_id, a.goal_id, a.milestone_id,
  a.achieved_now, CASE WHEN a.achieved_now THEN NOW() ELSE NULL END,
  CASE WHEN a.achieved_now THEN a.progress_pct ELSE NULL END
FROM ach a
ON CONFLICT (user_id, goal_id, milestone_id) DO UPDATE
SET achieved_flag = EXCLUDED.achieved_flag,
    achieved_at = COALESCE(goalcompass.user_goal_milestone_status.achieved_at, EXCLUDED.achieved_at),
    progress_pct_at_ach = COALESCE(goalcompass.user_goal_milestone_status.progress_pct_at_ach, EXCLUDED.progress_pct_at_ach);

-- ============================================================================
-- 4) ANALYTICS VIEWS
-- ============================================================================
-- 4.1 Goal progress view (latest month)
CREATE OR REPLACE VIEW goalcompass.vw_goal_progress AS
WITH latest_month AS (
  SELECT user_id, goal_id, MAX(month) AS max_month
  FROM goalcompass.goal_compass_snapshot
  GROUP BY user_id, goal_id
)
SELECT
  s.user_id, s.goal_id, g.goal_category, g.goal_name, g.goal_type,
  s.month, s.estimated_cost, s.progress_amount, s.progress_pct, s.remaining_amount,
  s.months_remaining, s.suggested_monthly_need, s.on_track_flag, s.risk_level, s.commentary
FROM goalcompass.goal_compass_snapshot s
JOIN latest_month lm ON lm.user_id=s.user_id AND lm.goal_id=s.goal_id AND lm.max_month=s.month
JOIN goal.user_goals_master g ON g.user_id=s.user_id AND g.goal_id=s.goal_id;

-- 4.2 Materialized dashboard views
CREATE MATERIALIZED VIEW IF NOT EXISTS goalcompass.mv_goalcompass_dashboard_user_month AS
SELECT
  s.user_id,
  s.month,
  COUNT(*) FILTER (WHERE s.remaining_amount > 0) AS active_goals_count,
  ROUND(AVG(s.progress_pct), 2) AS avg_progress_pct,
  SUM(s.remaining_amount) AS total_remaining_amount,
  SUM(CASE WHEN s.on_track_flag THEN 1 ELSE 0 END) AS goals_on_track_count,
  SUM(CASE WHEN s.risk_level='high' THEN 1 ELSE 0 END) AS goals_high_risk_count
FROM goalcompass.goal_compass_snapshot s
GROUP BY s.user_id, s.month;

CREATE UNIQUE INDEX IF NOT EXISTS idx_mv_gc_dash_user_month ON goalcompass.mv_goalcompass_dashboard_user_month(user_id, month);

CREATE MATERIALIZED VIEW IF NOT EXISTS goalcompass.mv_goalcompass_insights_user_month AS
SELECT
  s.user_id, s.month,
  jsonb_agg(
    jsonb_build_object(
      'goal_id', s.goal_id,
      'name', g.goal_name,
      'progress_pct', s.progress_pct,
      'remaining', s.remaining_amount,
      'on_track', s.on_track_flag,
      'risk', s.risk_level,
      'suggested_monthly', s.suggested_monthly_need
    ) ORDER BY s.risk_level DESC, s.remaining_amount DESC
  ) AS goal_cards
FROM goalcompass.goal_compass_snapshot s
JOIN goal.user_goals_master g ON g.user_id=s.user_id AND g.goal_id=s.goal_id
GROUP BY s.user_id, s.month;

CREATE UNIQUE INDEX IF NOT EXISTS idx_mv_gc_insights_user_month ON goalcompass.mv_goalcompass_insights_user_month(user_id, month);

-- ============================================================================
-- 5) HOW TO RUN
-- ============================================================================
-- Prerequisites:
-- - SpendSense + BudgetPilot packages executed and data present for a user/month
-- Steps:
-- 1. Run the full migration file to create schema and tables:
--    \i 010_goalcompass_full_package.sql
-- 2. Customize parameters in sections 3.1, 3.3, and 3.4:
--    - Modify the WITH params clauses to set p_user_id, p_month, and as_of_date
--    - Or use psql variables by replacing params with :p_user_id, :p_month, :as_of_date
-- 3. Rerun sections 3.* monthly (or daily) to refresh contributions and snapshots
-- 4. Refresh materialized views:
--    REFRESH MATERIALIZED VIEW CONCURRENTLY goalcompass.mv_goalcompass_dashboard_user_month;
--    REFRESH MATERIALIZED VIEW CONCURRENTLY goalcompass.mv_goalcompass_insights_user_month;
-- ============================================================================
COMMIT;

