"""
GoalCompass API Endpoints
Goal progress tracking, contributions, snapshots, and milestones
"""
from fastapi import APIRouter, Depends, Query, HTTPException
from typing import Optional, List, Dict, Any
from datetime import datetime, date
from app.routers.auth import get_current_user, UserDep
from app.database.postgresql import SessionLocal
from sqlalchemy import text
from pydantic import BaseModel
import uuid

router = APIRouter()


class RefreshGoalCompassRequest(BaseModel):
    month: str  # YYYY-MM-01 format
    as_of_date: Optional[str] = None  # YYYY-MM-DD format


@router.get("/progress")
async def get_goal_progress(
    goal_id: Optional[str] = Query(None, description="Specific goal ID"),
    month: Optional[str] = Query(None, description="Month in YYYY-MM-01 format"),
    user: UserDep = Depends(get_current_user)
):
    """
    Get goal progress from vw_goal_progress view.
    Returns latest progress per goal or specific goal if goal_id provided.
    """
    session = SessionLocal()
    user_uuid = uuid.UUID(user.user_id) if isinstance(user.user_id, str) else user.user_id
    try:
        if goal_id:
            # Get specific goal progress
            result = session.execute(text("""
                SELECT 
                    user_id, goal_id, goal_category, goal_name, goal_type,
                    month, estimated_cost, progress_amount, progress_pct, 
                    remaining_amount, months_remaining, suggested_monthly_need,
                    on_track_flag, risk_level, commentary
                FROM goalcompass.vw_goal_progress
                WHERE user_id = :user_id AND goal_id = :goal_id
            """), {
                "user_id": str(user_uuid),
                "goal_id": goal_id
            }).mappings().first()
            
            if not result:
                raise HTTPException(status_code=404, detail="Goal progress not found")
            
            return dict(result)
        else:
            # Get all goals progress
            results = session.execute(text("""
                SELECT 
                    user_id, goal_id, goal_category, goal_name, goal_type,
                    month, estimated_cost, progress_amount, progress_pct, 
                    remaining_amount, months_remaining, suggested_monthly_need,
                    on_track_flag, risk_level, commentary
                FROM goalcompass.vw_goal_progress
                WHERE user_id = :user_id
                ORDER BY risk_level DESC, remaining_amount DESC, goal_name
            """), {
                "user_id": str(user_uuid)
            }).mappings().all()
            
            return {"goals": [dict(r) for r in results]}
    finally:
        session.close()


@router.get("/dashboard")
async def get_goal_dashboard(
    month: Optional[str] = Query(None, description="Month in YYYY-MM-01 format"),
    user: UserDep = Depends(get_current_user)
):
    """
    Get dashboard aggregates from materialized view.
    """
    session = SessionLocal()
    user_uuid = uuid.UUID(user.user_id) if isinstance(user.user_id, str) else user.user_id
    try:
        # Default to current month
        if not month:
            now = datetime.utcnow()
            month = f"{now.year}-{now.month:02d}-01"
        
        result = session.execute(text("""
            SELECT 
                user_id, month, active_goals_count, avg_progress_pct,
                total_remaining_amount, goals_on_track_count, goals_high_risk_count
            FROM goalcompass.mv_goalcompass_dashboard_user_month
            WHERE user_id = :user_id AND month = :month
        """), {
            "user_id": str(user_uuid),
            "month": month
        }).mappings().first()
        
        if not result:
            # Return empty dashboard if no data
            return {
                "month": month,
                "active_goals_count": 0,
                "avg_progress_pct": 0,
                "total_remaining_amount": 0,
                "goals_on_track_count": 0,
                "goals_high_risk_count": 0
            }
        
        return dict(result)
    finally:
        session.close()


@router.get("/insights")
async def get_goal_insights(
    month: Optional[str] = Query(None, description="Month in YYYY-MM-01 format"),
    user: UserDep = Depends(get_current_user)
):
    """
    Get goal insights JSON from materialized view.
    """
    session = SessionLocal()
    user_uuid = uuid.UUID(user.user_id) if isinstance(user.user_id, str) else user.user_id
    try:
        # Default to current month
        if not month:
            now = datetime.utcnow()
            month = f"{now.year}-{now.month:02d}-01"
        
        result = session.execute(text("""
            SELECT 
                user_id, month, goal_cards
            FROM goalcompass.mv_goalcompass_insights_user_month
            WHERE user_id = :user_id AND month = :month
        """), {
            "user_id": str(user_uuid),
            "month": month
        }).mappings().first()
        
        if not result:
            return {
                "month": month,
                "goal_cards": []
            }
        
        # Convert date to string if needed
        month_str = result["month"].isoformat() if hasattr(result["month"], "isoformat") else str(result["month"])
        
        return {
            "month": month_str,
            "goal_cards": result["goal_cards"] if result["goal_cards"] else []
        }
    finally:
        session.close()


@router.get("/milestones/{goal_id}")
async def get_goal_milestones(
    goal_id: str,
    user: UserDep = Depends(get_current_user)
):
    """
    Get milestone achievements for a specific goal.
    """
    session = SessionLocal()
    user_uuid = uuid.UUID(user.user_id) if isinstance(user.user_id, str) else user.user_id
    try:
        # Get milestones with achievement status
        results = session.execute(text("""
            SELECT 
                mm.milestone_id, mm.threshold_pct, mm.label, mm.description,
                ugms.achieved_flag, ugms.achieved_at, ugms.progress_pct_at_ach
            FROM goalcompass.goal_milestone_master mm
            JOIN goal.user_goals_master g 
                ON g.goal_category = mm.goal_category 
                AND g.goal_name = mm.goal_name
            LEFT JOIN goalcompass.user_goal_milestone_status ugms
                ON ugms.user_id = g.user_id 
                AND ugms.goal_id = g.goal_id 
                AND ugms.milestone_id = mm.milestone_id
            WHERE g.user_id = :user_id AND g.goal_id = :goal_id
            ORDER BY mm.display_order
        """), {
            "user_id": str(user_uuid),
            "goal_id": goal_id
        }).mappings().all()
        
        return {
            "goal_id": goal_id,
            "milestones": [dict(r) for r in results]
        }
    finally:
        session.close()


@router.post("/refresh")
async def refresh_goalcompass(
    payload: RefreshGoalCompassRequest,
    user: UserDep = Depends(get_current_user)
):
    """
    Refresh GoalCompass data for a specific month.
    Runs sections 3.1, 3.3, and 3.4 from migration 010_goalcompass_full_package.sql
    """
    session = SessionLocal()
    user_uuid = uuid.UUID(user.user_id) if isinstance(user.user_id, str) else user.user_id
    try:
        # Check if goalcompass schema exists
        try:
            schema_check = session.execute(text("""
                SELECT EXISTS (
                    SELECT 1 FROM information_schema.schemata 
                    WHERE schema_name = 'goalcompass'
                )
            """)).scalar()
        except Exception as e:
            session.rollback()
            raise HTTPException(
                status_code=500, 
                detail=f"Failed to check schema: {str(e)}. Please ensure database connection is working."
            )
        
        if not schema_check:
            raise HTTPException(
                status_code=500, 
                detail="GoalCompass schema not found. Please run migration 010_goalcompass_schema_only.sql in Supabase SQL Editor first."
            )
        
        # Check if required tables exist
        try:
            table_check = session.execute(text("""
                SELECT EXISTS (
                    SELECT 1 FROM information_schema.tables 
                    WHERE table_schema = 'goalcompass' 
                    AND table_name = 'goal_compass_snapshot'
                )
            """)).scalar()
        except Exception as e:
            session.rollback()
            raise HTTPException(
                status_code=500, 
                detail=f"Failed to check tables: {str(e)}"
            )
        
        if not table_check:
            raise HTTPException(
                status_code=500, 
                detail="GoalCompass tables not found. Please run migration 010_goalcompass_schema_only.sql in Supabase SQL Editor."
            )
        
        # Default as_of_date to month if not provided
        as_of_date = payload.as_of_date or payload.month
        
        # Section 3.1: Distribute asset contributions
        try:
            session.execute(text("""
                WITH params AS (
                    SELECT :user_id::uuid AS p_user_id, :month::date AS p_month
                ),
                m AS (
                    SELECT date_trunc('month', (SELECT p_month FROM params))::date AS month
                ),
                assets_actual AS (
                    SELECT b.user_id, b.month, b.assets_amt
                    FROM budgetpilot.budget_user_month_aggregate b
                    WHERE b.month = (SELECT month FROM m)
                      AND b.user_id = (SELECT p_user_id FROM params)
                ),
                weights AS (
                    SELECT g.user_id, g.month, g.goal_id, g.weight_pct
                    FROM budgetpilot.user_budget_commit_goal_alloc g
                    WHERE g.month = (SELECT month FROM m)
                      AND g.user_id = (SELECT p_user_id FROM params)
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
                SET amount = EXCLUDED.amount, notes = EXCLUDED.notes, created_at = NOW()
            """), {
                "user_id": str(user_uuid),
                "month": payload.month
            })
            session.commit()
        except Exception as e:
            session.rollback()
            # This is okay if there are no allocations yet - just log and continue
            print(f"Warning: Could not distribute contributions (may not have allocations yet): {str(e)}")
        
        # Section 3.3: Build goal snapshot
        # First check if user has any active goals
        goal_count = session.execute(text("""
            SELECT COUNT(*) FROM goal.user_goals_master 
            WHERE status='active' AND user_id = :user_id
        """), {"user_id": str(user_uuid)}).scalar()
        
        if goal_count == 0:
            # No active goals - return early but still success
            return {
                "message": "GoalCompass refreshed successfully (no active goals found)",
                "month": payload.month,
                "user_id": str(user_uuid),
                "goals_found": 0
            }
        
        try:
            session.execute(text("""
            WITH params AS (
                SELECT :user_id::uuid AS p_user_id, :month::date AS p_month, :as_of_date::date AS as_of_date
            ),
            ug AS (
                SELECT g.*
                FROM goal.user_goals_master g
                WHERE g.status='active'
                  AND g.user_id = (SELECT p_user_id FROM params)
            ),
            contrib_upto AS (
                SELECT c.user_id, c.goal_id,
                    SUM(CASE WHEN c.month <= date_trunc('month', (SELECT p_month FROM params))::date THEN c.amount ELSE 0 END) AS cumulative_contrib
                FROM goalcompass.goal_contribution_fact c
                GROUP BY c.user_id, c.goal_id
            ),
            base AS (
                SELECT
                    u.user_id, u.goal_id,
                    date_trunc('month', (SELECT p_month FROM params))::date AS month,
                    u.estimated_cost, u.target_date,
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
                computed_at = NOW()
            """), {
                "user_id": str(user_uuid),
                "month": payload.month,
                "as_of_date": as_of_date
            })
            session.commit()
        except Exception as e:
            session.rollback()
            import traceback
            error_detail = traceback.format_exc()
            print(f"Error building goal snapshot: {error_detail}")
            # Check if it's a table/schema error
            error_str = str(e).lower()
            if 'does not exist' in error_str or 'relation' in error_str:
                raise HTTPException(
                    status_code=500, 
                    detail=f"Table or schema does not exist. Please run migration 010_goalcompass_schema_only.sql first. Error: {str(e)}"
                )
            raise HTTPException(status_code=500, detail=f"Failed to build goal snapshot: {str(e)}")
        
        # Section 3.4: Update milestones
        try:
            session.execute(text("""
            WITH params AS (
                SELECT :user_id::uuid AS p_user_id, :month::date AS p_month
            ),
            latest AS (
                SELECT s.user_id, s.goal_id, s.month, s.progress_pct
                FROM goalcompass.goal_compass_snapshot s
                WHERE s.month = date_trunc('month', (SELECT p_month FROM params))
                  AND s.user_id = (SELECT p_user_id FROM params)
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
                progress_pct_at_ach = COALESCE(goalcompass.user_goal_milestone_status.progress_pct_at_ach, EXCLUDED.progress_pct_at_ach)
            """), {
                "user_id": str(user_uuid),
                "month": payload.month
            })
            session.commit()
        except Exception as e:
            session.rollback()
            # Milestone update failure is not critical, log and continue
            print(f"Warning: Could not update milestones: {str(e)}")
        
        # Refresh materialized views (non-blocking if views don't exist yet)
        try:
            session.execute(text("REFRESH MATERIALIZED VIEW CONCURRENTLY goalcompass.mv_goalcompass_dashboard_user_month"))
            session.commit()
        except Exception as e:
            session.rollback()
            # If concurrent refresh fails, try regular refresh
            try:
                session.execute(text("REFRESH MATERIALIZED VIEW goalcompass.mv_goalcompass_dashboard_user_month"))
                session.commit()
            except Exception as e2:
                print(f"Warning: Could not refresh dashboard view: {str(e2)}")
        
        try:
            session.execute(text("REFRESH MATERIALIZED VIEW CONCURRENTLY goalcompass.mv_goalcompass_insights_user_month"))
            session.commit()
        except Exception as e:
            session.rollback()
            # If concurrent refresh fails, try regular refresh
            try:
                session.execute(text("REFRESH MATERIALIZED VIEW goalcompass.mv_goalcompass_insights_user_month"))
                session.commit()
            except Exception as e2:
                print(f"Warning: Could not refresh insights view: {str(e2)}")
        
        return {
            "message": "GoalCompass refreshed successfully",
            "month": payload.month,
            "user_id": str(user_uuid)
        }
    except HTTPException:
        raise
    except Exception as e:
        session.rollback()
        import traceback
        error_detail = traceback.format_exc()
        print(f"Error refreshing GoalCompass: {error_detail}")
        # Provide more detailed error message
        error_str = str(e).lower()
        if 'does not exist' in error_str or 'relation' in error_str or 'schema' in error_str:
            raise HTTPException(
                status_code=500, 
                detail=f"GoalCompass schema or tables do not exist. Please run the migration SQL first. Error: {str(e)}"
            )
        raise HTTPException(
            status_code=500, 
            detail=f"Failed to refresh GoalCompass: {str(e)}. Check backend logs for full traceback."
        )
    finally:
        session.close()


@router.get("/contributions")
async def get_goal_contributions(
    goal_id: Optional[str] = Query(None),
    month: Optional[str] = Query(None),
    user: UserDep = Depends(get_current_user)
):
    """
    Get contribution history for goals.
    """
    session = SessionLocal()
    user_uuid = uuid.UUID(user.user_id) if isinstance(user.user_id, str) else user.user_id
    try:
        if goal_id:
            query = text("""
                SELECT 
                    gcf.gcf_id, gcf.user_id, gcf.goal_id, gcf.month, gcf.source,
                    gcf.amount, gcf.notes, gcf.created_at,
                    g.goal_name
                FROM goalcompass.goal_contribution_fact gcf
                JOIN goal.user_goals_master g ON g.goal_id = gcf.goal_id
                WHERE gcf.user_id = :user_id AND gcf.goal_id = :goal_id
                ORDER BY gcf.month DESC, gcf.created_at DESC
            """)
            params = {"user_id": str(user_uuid), "goal_id": goal_id}
        elif month:
            query = text("""
                SELECT 
                    gcf.gcf_id, gcf.user_id, gcf.goal_id, gcf.month, gcf.source,
                    gcf.amount, gcf.notes, gcf.created_at,
                    g.goal_name
                FROM goalcompass.goal_contribution_fact gcf
                JOIN goal.user_goals_master g ON g.goal_id = gcf.goal_id
                WHERE gcf.user_id = :user_id AND gcf.month = :month
                ORDER BY gcf.goal_id, gcf.created_at DESC
            """)
            params = {"user_id": str(user_uuid), "month": month}
        else:
            query = text("""
                SELECT 
                    gcf.gcf_id, gcf.user_id, gcf.goal_id, gcf.month, gcf.source,
                    gcf.amount, gcf.notes, gcf.created_at,
                    g.goal_name
                FROM goalcompass.goal_contribution_fact gcf
                JOIN goal.user_goals_master g ON g.goal_id = gcf.goal_id
                WHERE gcf.user_id = :user_id
                ORDER BY gcf.month DESC, gcf.goal_id, gcf.created_at DESC
            """)
            params = {"user_id": str(user_uuid)}
        
        results = session.execute(query, params).mappings().all()
        
        return {"contributions": [dict(r) for r in results]}
    finally:
        session.close()

