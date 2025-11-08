-- ============================================================================
-- Monytix MoneyMoments (Behavioral Nudges) - Full SQL Package (DDL + Seeds + Derivations)
-- Version: 1.0 | Date: 2025-10-23
-- ============================================================================
-- Upstream dependencies (not created here):
-- - spendsense.vw_txn_effective(user_id, txn_date, amount, direction, txn_type, category_code, subcategory_code, merchant_name_norm)
-- - budgetpilot.user_budget_commit(user_id, month, alloc_wants_pct, alloc_assets_pct)
-- - goal.user_goals_master(user_id, goal_id, priority_rank, status)
-- - goalcompass.goal_contribution_fact(user_id, goal_id, month, planned_amount, actual_amount)
-- ============================================================================
BEGIN;
CREATE EXTENSION IF NOT EXISTS pgcrypto;

-- Ensure target schema for MoneyMoments objects
CREATE SCHEMA IF NOT EXISTS moneymoments;

-- Resolve unqualified objects from these schemas in order (prefer moneymoments)
SET search_path = moneymoments, goalcompass, budgetpilot, goal, spendsense, enrichment, core, public;

-- ============================================================================
-- 1) TABLES
-- ============================================================================

-- 1.1 User Traits
DROP TABLE IF EXISTS moneymoments.mm_user_traits CASCADE;
CREATE TABLE moneymoments.mm_user_traits (
  user_id UUID PRIMARY KEY,
  age_band VARCHAR(16) NOT NULL CHECK (age_band IN ('18-24','25-34','35-44','45-54','55+')),
  gender VARCHAR(16) CHECK (gender IN ('female','male','nonbinary','prefer_not_say')),
  region_code VARCHAR(8) NOT NULL,
  lifestyle_tags JSONB NOT NULL DEFAULT '[]'::jsonb,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_mm_user_traits_region ON moneymoments.mm_user_traits(region_code);

-- 1.2 Daily Signals
DROP TABLE IF EXISTS moneymoments.mm_signal_daily CASCADE;
CREATE TABLE moneymoments.mm_signal_daily (
  user_id UUID NOT NULL,
  as_of_date DATE NOT NULL,
  dining_txn_7d INTEGER NOT NULL DEFAULT 0,
  dining_spend_7d NUMERIC(14,2) NOT NULL DEFAULT 0,
  shopping_txn_7d INTEGER NOT NULL DEFAULT 0,
  shopping_spend_7d NUMERIC(14,2) NOT NULL DEFAULT 0,
  travel_txn_30d INTEGER NOT NULL DEFAULT 0,
  travel_spend_30d NUMERIC(14,2) NOT NULL DEFAULT 0,
  wants_share_30d NUMERIC(6,3),
  recurring_merchants_90d INTEGER NOT NULL DEFAULT 0,
  wants_vs_plan_pct NUMERIC(6,3),
  assets_vs_plan_pct NUMERIC(6,3),
  rank1_goal_underfund_amt NUMERIC(14,2) NOT NULL DEFAULT 0,
  rank1_goal_underfund_pct NUMERIC(6,3),
  last_nudge_sent_at TIMESTAMPTZ,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  PRIMARY KEY (user_id, as_of_date)
);

CREATE INDEX IF NOT EXISTS idx_mm_signal_daily_user_date ON moneymoments.mm_signal_daily(user_id, as_of_date);

-- 1.3 Rules & Templates
DROP TABLE IF EXISTS moneymoments.mm_nudge_rule_master CASCADE;
CREATE TABLE moneymoments.mm_nudge_rule_master (
  rule_id VARCHAR(40) PRIMARY KEY,
  name VARCHAR(120) NOT NULL,
  description TEXT,
  target_domain VARCHAR(16) NOT NULL CHECK (target_domain IN ('dining','shopping','travel','general')),
  segment_criteria_json JSONB NOT NULL DEFAULT '{}'::jsonb,
  trigger_conditions_json JSONB NOT NULL,
  score_formula_json JSONB NOT NULL DEFAULT '{}'::jsonb,
  cooldown_days SMALLINT NOT NULL DEFAULT 7,
  daily_cap SMALLINT NOT NULL DEFAULT 1,
  priority SMALLINT NOT NULL DEFAULT 100,
  active BOOLEAN NOT NULL DEFAULT TRUE,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_mm_rule_active ON moneymoments.mm_nudge_rule_master(active, priority);

DROP TABLE IF EXISTS moneymoments.mm_nudge_template_master CASCADE;
CREATE TABLE moneymoments.mm_nudge_template_master (
  template_code VARCHAR(40) PRIMARY KEY,
  rule_id VARCHAR(40) NOT NULL REFERENCES moneymoments.mm_nudge_rule_master(rule_id) ON DELETE CASCADE,
  channel VARCHAR(16) NOT NULL CHECK (channel IN ('in_app','push','email')),
  locale VARCHAR(8) NOT NULL DEFAULT 'en-IN',
  title_template TEXT NOT NULL,
  body_template TEXT NOT NULL,
  cta_text VARCHAR(60),
  cta_deeplink VARCHAR(200),
  humor_style VARCHAR(16) CHECK (humor_style IN ('friendly','witty','punny','dry')),
  active BOOLEAN NOT NULL DEFAULT TRUE,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_mm_template_rule ON moneymoments.mm_nudge_template_master(rule_id, active);

-- Seed Rules & Templates
INSERT INTO moneymoments.mm_nudge_rule_master (
  rule_id, name, description, target_domain, segment_criteria_json, 
  trigger_conditions_json, score_formula_json, cooldown_days, daily_cap, priority, active
)
VALUES (
  'DINING_3PLUS_WEEK',
  'Dining 3+ times this week',
  'If user dines out ≥3 times & wants share is high.',
  'dining',
  '{}',
  '{"dining_txn_7d_min": 3, "wants_share_30d_min": 0.30, "exclude_if_rank1_goal_underfund_amt_lt": 1000}',
  '{}',
  7,
  1,
  10,
  TRUE
)
ON CONFLICT (rule_id) DO NOTHING;

INSERT INTO moneymoments.mm_nudge_template_master (
  template_code, rule_id, channel, locale, title_template, body_template, 
  cta_text, cta_deeplink, humor_style, active
)
VALUES (
  'HUMOR_DINING_SKIP_ONE',
  'DINING_3PLUS_WEEK',
  'in_app',
  'en-IN',
  'Skip just one dinner out = ₹{{save}} closer to {{goal}}',
  'Looks tasty… but your {{goal}} is hungrier 😋 Trim one dine-out this week and park ₹{{save}} to your {{goal}}.',
  'Adjust Budget',
  'monytix://budget/adjust',
  'witty',
  TRUE
)
ON CONFLICT (template_code) DO NOTHING;

-- 1.4 Queue & Delivery
DROP TABLE IF EXISTS moneymoments.mm_nudge_candidate CASCADE;
CREATE TABLE moneymoments.mm_nudge_candidate (
  candidate_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID NOT NULL,
  as_of_date DATE NOT NULL,
  rule_id VARCHAR(40) NOT NULL REFERENCES moneymoments.mm_nudge_rule_master(rule_id) ON DELETE CASCADE,
  template_code VARCHAR(40) NOT NULL REFERENCES moneymoments.mm_nudge_template_master(template_code) ON DELETE RESTRICT,
  score NUMERIC(8,3) NOT NULL DEFAULT 0,
  reason_json JSONB NOT NULL DEFAULT '{}'::jsonb,
  status VARCHAR(16) NOT NULL DEFAULT 'pending' CHECK (status IN ('pending','suppressed','queued','sent','expired')),
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  UNIQUE (user_id, as_of_date, rule_id)
);

CREATE INDEX IF NOT EXISTS idx_mm_candidate_pending ON moneymoments.mm_nudge_candidate(status, as_of_date);

DROP TABLE IF EXISTS moneymoments.mm_user_suppression CASCADE;
CREATE TABLE moneymoments.mm_user_suppression (
  user_id UUID NOT NULL,
  channel VARCHAR(16) NOT NULL CHECK (channel IN ('in_app','push','email')),
  muted_until TIMESTAMPTZ,
  daily_cap SMALLINT NOT NULL DEFAULT 3,
  PRIMARY KEY (user_id, channel)
);

DROP TABLE IF EXISTS moneymoments.mm_nudge_delivery_log CASCADE;
CREATE TABLE moneymoments.mm_nudge_delivery_log (
  delivery_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  candidate_id UUID NOT NULL REFERENCES moneymoments.mm_nudge_candidate(candidate_id) ON DELETE CASCADE,
  user_id UUID NOT NULL,
  rule_id VARCHAR(40) NOT NULL,
  template_code VARCHAR(40) NOT NULL,
  channel VARCHAR(16) NOT NULL CHECK (channel IN ('in_app','push','email')),
  sent_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  send_status VARCHAR(16) NOT NULL DEFAULT 'success' CHECK (send_status IN ('success','failed')),
  error_message TEXT,
  metadata_json JSONB NOT NULL DEFAULT '{}'::jsonb
);

CREATE INDEX IF NOT EXISTS idx_mm_delivery_user_time ON moneymoments.mm_nudge_delivery_log(user_id, sent_at DESC);

DROP TABLE IF EXISTS moneymoments.mm_nudge_interaction_log CASCADE;
CREATE TABLE moneymoments.mm_nudge_interaction_log (
  interaction_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  delivery_id UUID NOT NULL REFERENCES moneymoments.mm_nudge_delivery_log(delivery_id) ON DELETE CASCADE,
  user_id UUID NOT NULL,
  event_type VARCHAR(16) NOT NULL CHECK (event_type IN ('view','click','dismiss')),
  event_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  metadata_json JSONB NOT NULL DEFAULT '{}'::jsonb
);

CREATE INDEX IF NOT EXISTS idx_mm_interaction_user_time ON moneymoments.mm_nudge_interaction_log(user_id, event_at DESC);

-- ============================================================================
-- 2) DERIVATION FUNCTIONS / BLOCKS
-- ============================================================================
-- Note: These derivation blocks use WITH params CTEs for Supabase compatibility
-- Pass as_of_date as a parameter when calling these blocks
-- ============================================================================

-- 2.1 Derive Daily Signals
-- Usage: Replace :as_of_date with your date parameter in a WITH params CTE
-- Example: WITH params AS (SELECT '2025-10-23'::date AS as_of_date) ...
CREATE OR REPLACE FUNCTION moneymoments.derive_signal_daily(p_as_of_date DATE)
RETURNS void
LANGUAGE plpgsql
AS $$
BEGIN
  WITH params AS (SELECT p_as_of_date AS as_of_date),
  -- Map category_code to major_category concept
  tx AS (
    SELECT 
      v.user_id, 
      v.txn_date, 
      v.amount, 
      v.direction, 
      v.txn_type,
      CASE 
        WHEN v.category_code = 'dining' THEN 'Dining'
        WHEN v.category_code = 'shopping' THEN 'Shopping'
        WHEN v.category_code = 'travel' THEN 'Travel'
        ELSE NULL
      END AS major_category
    FROM spendsense.vw_txn_effective v
    WHERE v.txn_date >= ((SELECT as_of_date FROM params)::date - INTERVAL '90 days')
      AND v.txn_date < (SELECT as_of_date FROM params)::date + INTERVAL '1 day'
  ),
  win_7 AS (
    SELECT 
      user_id,
      COUNT(*) FILTER (WHERE major_category='Dining' AND direction='debit') AS dining_txn_7d,
      COALESCE(SUM(amount) FILTER (WHERE major_category='Dining' AND direction='debit'),0) AS dining_spend_7d,
      COUNT(*) FILTER (WHERE major_category='Shopping' AND direction='debit') AS shopping_txn_7d,
      COALESCE(SUM(amount) FILTER (WHERE major_category='Shopping' AND direction='debit'),0) AS shopping_spend_7d
    FROM tx
    WHERE txn_date >= ((SELECT as_of_date FROM params)::date - INTERVAL '7 days')
    GROUP BY user_id
  ),
  win_30 AS (
    SELECT 
      user_id,
      COUNT(*) FILTER (WHERE major_category='Travel' AND direction='debit') AS travel_txn_30d,
      COALESCE(SUM(amount) FILTER (WHERE major_category='Travel' AND direction='debit'),0) AS travel_spend_30d,
      COALESCE(SUM(amount) FILTER (WHERE txn_type='wants' AND direction='debit'),0) AS wants_debits_30d,
      COALESCE(SUM(amount) FILTER (WHERE direction='debit'),0) AS debits_30d
    FROM tx
    WHERE txn_date >= ((SELECT as_of_date FROM params)::date - INTERVAL '30 days')
    GROUP BY user_id
  ),
  recurring AS (
    SELECT 
      user_id, 
      COUNT(*) AS recurring_merchants_90d
    FROM (
      SELECT DISTINCT 
        user_id, 
        COALESCE(merchant_name_norm, ''),
        date_trunc('month', txn_date) AS month,
        amount
      FROM spendsense.vw_txn_effective
      WHERE direction='debit'
        AND txn_date >= ((SELECT as_of_date FROM params)::date - INTERVAL '90 days')
        AND txn_date < (SELECT as_of_date FROM params)::date + INTERVAL '1 day'
    ) g
    GROUP BY user_id
  ),
  budget AS (
    SELECT
      u.user_id,
      c.alloc_wants_pct AS planned_wants_pct,
      CASE 
        WHEN SUM(CASE WHEN v.txn_type='income' THEN v.amount ELSE 0 END) > 0
        THEN (SUM(CASE WHEN v.txn_type='wants' AND v.direction='debit' THEN v.amount ELSE 0 END)
              / SUM(CASE WHEN v.txn_type='income' THEN v.amount ELSE 0 END))
        ELSE NULL 
      END AS actual_wants_pct,
      c.alloc_assets_pct AS planned_assets_pct,
      CASE 
        WHEN SUM(CASE WHEN v.txn_type='income' THEN v.amount ELSE 0 END) > 0
        THEN (SUM(CASE WHEN v.txn_type='assets' AND v.direction='debit' THEN v.amount ELSE 0 END)
              / SUM(CASE WHEN v.txn_type='income' THEN v.amount ELSE 0 END))
        ELSE NULL 
      END AS actual_assets_pct
    FROM (SELECT DISTINCT user_id FROM tx) u
    LEFT JOIN budgetpilot.user_budget_commit c
      ON c.user_id=u.user_id 
      AND date_trunc('month', (SELECT as_of_date FROM params)::date) = c.month
    LEFT JOIN spendsense.vw_txn_effective v
      ON v.user_id=u.user_id
      AND date_trunc('month', v.txn_date) = date_trunc('month', (SELECT as_of_date FROM params)::date)
    GROUP BY u.user_id, c.alloc_wants_pct, c.alloc_assets_pct
  ),
  goals AS (
    SELECT 
      g.user_id,
      COALESCE(SUM(CASE WHEN g.priority_rank=1 THEN GREATEST(0, COALESCE(ga.planned_amount,0) - COALESCE(f.amount,0)) END),0) AS rank1_goal_underfund_amt,
      CASE 
        WHEN SUM(CASE WHEN g.priority_rank=1 THEN COALESCE(ga.planned_amount,0) END) > 0
        THEN (SUM(CASE WHEN g.priority_rank=1 THEN GREATEST(0, COALESCE(ga.planned_amount,0) - COALESCE(f.amount,0)) END)
              / SUM(CASE WHEN g.priority_rank=1 THEN COALESCE(ga.planned_amount,0) END))
        ELSE NULL 
      END AS rank1_goal_underfund_pct
    FROM goal.user_goals_master g
    LEFT JOIN budgetpilot.user_budget_commit_goal_alloc ga
      ON ga.user_id=g.user_id 
      AND ga.goal_id=g.goal_id
      AND ga.month = date_trunc('month', (SELECT as_of_date FROM params)::date)
    LEFT JOIN goalcompass.goal_contribution_fact f
      ON f.user_id=g.user_id 
      AND f.goal_id=g.goal_id
      AND f.month = date_trunc('month', (SELECT as_of_date FROM params)::date)
    WHERE g.status='active'
    GROUP BY g.user_id
  )
  INSERT INTO moneymoments.mm_signal_daily (
    user_id, as_of_date, dining_txn_7d, dining_spend_7d, shopping_txn_7d,
    shopping_spend_7d, travel_txn_30d, travel_spend_30d, wants_share_30d, 
    recurring_merchants_90d, wants_vs_plan_pct, assets_vs_plan_pct, 
    rank1_goal_underfund_amt, rank1_goal_underfund_pct, last_nudge_sent_at
  )
  SELECT
    u.user_id, 
    (SELECT as_of_date FROM params)::date,
    COALESCE(w7.dining_txn_7d,0), 
    COALESCE(w7.dining_spend_7d,0),
    COALESCE(w7.shopping_txn_7d,0), 
    COALESCE(w7.shopping_spend_7d,0),
    COALESCE(w30.travel_txn_30d,0), 
    COALESCE(w30.travel_spend_30d,0),
    CASE 
      WHEN w30.debits_30d > 0 
      THEN ROUND(w30.wants_debits_30d / NULLIF(w30.debits_30d,0), 3) 
      ELSE NULL 
    END,
    COALESCE(rc.recurring_merchants_90d,0),
    CASE 
      WHEN b.planned_wants_pct IS NOT NULL AND b.actual_wants_pct IS NOT NULL
      THEN ROUND(b.actual_wants_pct / NULLIF(b.planned_wants_pct,0) - 1, 3)
      ELSE NULL 
    END,
    CASE 
      WHEN b.planned_assets_pct IS NOT NULL AND b.actual_assets_pct IS NOT NULL
      THEN ROUND(b.actual_assets_pct / NULLIF(b.planned_assets_pct,0) - 1, 3)
      ELSE NULL 
    END,
    COALESCE(g.rank1_goal_underfund_amt,0),
    g.rank1_goal_underfund_pct,
    (SELECT MAX(sent_at) FROM moneymoments.mm_nudge_delivery_log d WHERE d.user_id=u.user_id)
  FROM (SELECT DISTINCT user_id FROM tx) u
  LEFT JOIN win_7 w7 ON w7.user_id=u.user_id
  LEFT JOIN win_30 w30 ON w30.user_id=u.user_id
  LEFT JOIN recurring rc ON rc.user_id=u.user_id
  LEFT JOIN budget b ON b.user_id=u.user_id
  LEFT JOIN goals g ON g.user_id=u.user_id
  ON CONFLICT (user_id, as_of_date) DO UPDATE
  SET 
    dining_txn_7d = EXCLUDED.dining_txn_7d,
    dining_spend_7d = EXCLUDED.dining_spend_7d,
    shopping_txn_7d = EXCLUDED.shopping_txn_7d,
    shopping_spend_7d = EXCLUDED.shopping_spend_7d,
    travel_txn_30d = EXCLUDED.travel_txn_30d,
    travel_spend_30d = EXCLUDED.travel_spend_30d,
    wants_share_30d = EXCLUDED.wants_share_30d,
    recurring_merchants_90d = EXCLUDED.recurring_merchants_90d,
    wants_vs_plan_pct = EXCLUDED.wants_vs_plan_pct,
    assets_vs_plan_pct = EXCLUDED.assets_vs_plan_pct,
    rank1_goal_underfund_amt = EXCLUDED.rank1_goal_underfund_amt,
    rank1_goal_underfund_pct = EXCLUDED.rank1_goal_underfund_pct,
    last_nudge_sent_at = EXCLUDED.last_nudge_sent_at;
END;
$$;

-- 2.2 Derive Dining Nudge Candidates
CREATE OR REPLACE FUNCTION moneymoments.derive_candidates_dining(p_as_of_date DATE)
RETURNS void
LANGUAGE plpgsql
AS $$
BEGIN
  WITH params AS (SELECT p_as_of_date AS as_of_date),
  r AS (
    SELECT
      rule_id,
      (trigger_conditions_json->>'dining_txn_7d_min')::int AS dining_min,
      (trigger_conditions_json->>'wants_share_30d_min')::numeric AS wants_share_min,
      (trigger_conditions_json->>'exclude_if_rank1_goal_underfund_amt_lt')::numeric AS exclude_underfund_lt
    FROM moneymoments.mm_nudge_rule_master
    WHERE rule_id='DINING_3PLUS_WEEK' AND active=TRUE
  ),
  s AS (
    SELECT 
      s.*, 
      t.age_band, 
      t.region_code, 
      t.lifestyle_tags
    FROM moneymoments.mm_signal_daily s
    LEFT JOIN moneymoments.mm_user_traits t ON t.user_id=s.user_id
    WHERE s.as_of_date=(SELECT as_of_date FROM params)::date
  ),
  eligible AS (
    SELECT
      s.user_id,
      'DINING_3PLUS_WEEK'::varchar(40) AS rule_id,
      'HUMOR_DINING_SKIP_ONE'::varchar(40) AS template_code,
      ROUND(
        0.7 
        + 0.2 * LEAST(1.0, s.dining_txn_7d::numeric / NULLIF((SELECT dining_min FROM r),0))
        + 0.1 * COALESCE(s.wants_share_30d,0), 
        3
      ) AS score,
      jsonb_build_object(
        'dining_txn_7d', s.dining_txn_7d,
        'wants_share_30d', s.wants_share_30d,
        'rank1_goal_underfund_amt', s.rank1_goal_underfund_amt
      ) AS reason_json
    FROM s
    CROSS JOIN r
    WHERE s.dining_txn_7d >= r.dining_min
      AND COALESCE(s.wants_share_30d,0) >= r.wants_share_min
      AND s.rank1_goal_underfund_amt >= r.exclude_underfund_lt
  ),
  supp AS (
    SELECT 
      d.user_id, 
      d.rule_id, 
      MAX(d.sent_at) AS last_sent
    FROM moneymoments.mm_nudge_delivery_log d
    JOIN moneymoments.mm_nudge_rule_master r2 ON r2.rule_id=d.rule_id
    WHERE d.rule_id='DINING_3PLUS_WEEK'
    GROUP BY d.user_id, d.rule_id
  )
  INSERT INTO moneymoments.mm_nudge_candidate (
    user_id, as_of_date, rule_id, template_code, score, reason_json, status
  )
  SELECT 
    e.user_id, 
    (SELECT as_of_date FROM params)::date, 
    e.rule_id, 
    e.template_code, 
    e.score,
    e.reason_json, 
    'pending'
  FROM eligible e
  LEFT JOIN supp s ON s.user_id=e.user_id AND s.rule_id=e.rule_id
  LEFT JOIN moneymoments.mm_nudge_rule_master r3 ON r3.rule_id=e.rule_id
  WHERE s.last_sent IS NULL 
     OR s.last_sent < ((SELECT as_of_date FROM params)::date - (r3.cooldown_days||' days')::interval)
  ON CONFLICT (user_id, as_of_date, rule_id) DO NOTHING;
END;
$$;

-- 2.3 Queue Deliveries
CREATE OR REPLACE FUNCTION moneymoments.queue_deliveries(p_as_of_date DATE)
RETURNS void
LANGUAGE plpgsql
AS $$
DECLARE
  v_candidate_ids UUID[];
BEGIN
  WITH params AS (SELECT p_as_of_date AS as_of_date),
  q AS (
    SELECT c.*
    FROM moneymoments.mm_nudge_candidate c
    WHERE c.status='pending' 
      AND c.as_of_date=(SELECT as_of_date FROM params)::date
    ORDER BY c.user_id, c.score DESC, c.created_at
  ),
  cap AS (
    SELECT
      q.user_id,
      'in_app'::varchar(16) AS channel,
      COALESCE(sup.daily_cap, 3) AS cap
    FROM (SELECT DISTINCT user_id FROM q) q
    LEFT JOIN moneymoments.mm_user_suppression sup 
      ON sup.user_id=q.user_id AND sup.channel='in_app'
  ),
  already_sent AS (
    SELECT user_id, COUNT(*) AS sent_today
    FROM moneymoments.mm_nudge_delivery_log
    WHERE sent_at::date = (SELECT as_of_date FROM params)::date 
      AND channel='in_app'
    GROUP BY user_id
  ),
  to_send AS (
    SELECT 
      q.*, 
      cap.cap, 
      COALESCE(al.sent_today,0) AS sent_today
    FROM q
    JOIN cap ON cap.user_id=q.user_id
    LEFT JOIN already_sent al ON al.user_id=q.user_id
    WHERE COALESCE(al.sent_today,0) < cap.cap
  )
  INSERT INTO moneymoments.mm_nudge_delivery_log (
    candidate_id, user_id, rule_id, template_code, channel, send_status, metadata_json
  )
  SELECT
    t.candidate_id, 
    t.user_id, 
    t.rule_id, 
    t.template_code, 
    'in_app', 
    'success',
    jsonb_build_object(
      'deeplink', 'monytix://insights/leaks',
      'render_tokens', t.reason_json
    )
  FROM to_send t
  RETURNING candidate_id INTO v_candidate_ids;

  -- Update candidate status
  UPDATE moneymoments.mm_nudge_candidate
  SET status='sent'
  WHERE candidate_id = ANY(v_candidate_ids);
END;
$$;

COMMIT;


