from fastapi import APIRouter, Depends, HTTPException
from typing import List, Optional, Dict, Any
from pydantic import BaseModel
from app.routers.auth import get_current_user, UserDep
from app.database.postgresql import SessionLocal
from sqlalchemy import text
import uuid
from datetime import date, datetime


router = APIRouter()


class GoalIntake(BaseModel):
    goal_category: str
    goal_name: str
    goal_type: str  # 'short_term' | 'medium_term' | 'long_term'
    estimated_cost: float
    target_date: Optional[str] = None  # ISO date
    current_savings: float = 0
    linked_txn_type: Optional[str] = None   # optional override: 'needs'|'wants'|'assets'
    notes: Optional[str] = None


class QuestionnaireContext(BaseModel):
    age_band: str
    dependents_spouse: Optional[bool] = False
    dependents_children_count: Optional[int] = 0
    dependents_parents_care: Optional[bool] = False
    housing: str
    employment: str
    income_regularity: str
    region_code: str
    emergency_opt_out: Optional[bool] = False


class QuestionnairePayload(BaseModel):
    context: QuestionnaireContext
    selected_goals: List[GoalIntake]


class ReorderItem(BaseModel):
    user_goal_id: str
    priority_rank: int


class LifeContext(BaseModel):
    age_band: str                    # '18-24','25-34','35-44','45-54','55+'
    dependents_spouse: bool
    dependents_children_count: int
    dependents_parents_care: bool
    housing: str                     # 'rent','own_mortgage','own_nomortgage'
    employment: str                  # 'salaried','self_employed','student','homemaker','retired'
    income_regularity: str           # 'very_stable','stable','variable'
    region_code: str


@router.get("/context")
async def get_life_context(user: UserDep = Depends(get_current_user)):
    session = SessionLocal()
    user_uuid = uuid.UUID(user.user_id) if isinstance(user.user_id, str) else user.user_id
    try:
        row = session.execute(text(
            """
            SELECT age_band, dependents_spouse, dependents_children_count, dependents_parents_care,
                   housing, employment, income_regularity, region_code
            FROM goal.user_life_context
            WHERE user_id = :user_id
            """
        ), {"user_id": str(user_uuid)}).mappings().first()
        if not row:
            return None
        return dict(row)
    finally:
        session.close()


@router.put("/context")
async def upsert_life_context(payload: LifeContext, user: UserDep = Depends(get_current_user)):
    session = SessionLocal()
    user_uuid = uuid.UUID(user.user_id) if isinstance(user.user_id, str) else user.user_id
    try:
        session.execute(text(
            """
            INSERT INTO goal.user_life_context (
                user_id, age_band, dependents_spouse, dependents_children_count, dependents_parents_care,
                housing, employment, income_regularity, region_code
            ) VALUES (
                :user_id, :age_band, :dependents_spouse, :dependents_children_count, :dependents_parents_care,
                :housing, :employment, :income_regularity, :region_code
            )
            ON CONFLICT (user_id) DO UPDATE SET
                age_band = EXCLUDED.age_band,
                dependents_spouse = EXCLUDED.dependents_spouse,
                dependents_children_count = EXCLUDED.dependents_children_count,
                dependents_parents_care = EXCLUDED.dependents_parents_care,
                housing = EXCLUDED.housing,
                employment = EXCLUDED.employment,
                income_regularity = EXCLUDED.income_regularity,
                region_code = EXCLUDED.region_code
            """
        ), {"user_id": str(user_uuid), **payload.dict()})
        session.commit()
        return {"status": "ok"}
    except Exception as e:
        session.rollback()
        raise HTTPException(status_code=400, detail=f"Failed to save context: {str(e)}")
    finally:
        session.close()


@router.get("/catalog")
async def get_goal_catalog(user: UserDep = Depends(get_current_user)):
    """Return catalog grouped by horizon tabs with mini explainers."""
    session = SessionLocal()
    try:
        rows = session.execute(text(
            """
            SELECT goal_category, goal_name, default_horizon, policy_linked_txn_type,
                   suggested_min_amount_formula, display_order
            FROM goal.goal_category_master
            WHERE active = TRUE
            ORDER BY default_horizon, display_order, goal_name
            """
        )).mappings().all()

        grouped: Dict[str, List[Dict[str, Any]]] = {"short": [], "medium": [], "long": []}

        # Fetch context to annotate catalog with recommendations/hints
        ctx = session.execute(text(
            """
            SELECT age_band, dependents_spouse, dependents_children_count, dependents_parents_care,
                   housing, employment, income_regularity, region_code
            FROM goal.user_life_context WHERE user_id = :user_id
            """
        ), {"user_id": str(uuid.UUID(user.user_id))}).mappings().first()
        for r in rows:
            # Map default_horizon to short/medium/long tabs for UI
            """
            default_horizon values: short_term | medium_term | long_term
            UI groups: short | medium | long
            """
            tab = {
                "short_term": "short",
                "medium_term": "medium",
                "long_term": "long"
            }.get(r["default_horizon"], "long")
            recommended = False
            context_hint: Optional[str] = None

            if ctx is not None:
                # Recommend Term Insurance if dependents (spouse/children)
                if r["goal_name"].lower().startswith("term") and (
                    ctx["dependents_spouse"] or (ctx["dependents_children_count"] or 0) > 0
                ):
                    recommended = True

                # Recommend Parental Care Fund if parents_care
                if "parent" in r["goal_name"].lower() and ctx["dependents_parents_care"]:
                    recommended = True

                # Emergency Fund: increase multiple for variable income
                if "emergency fund" in r["goal_name"].lower() and ctx["income_regularity"] == "variable":
                    context_hint = "Consider higher multiple due to variable income"

            grouped[tab].append({
                "goal_category": r["goal_category"],
                "goal_name": r["goal_name"],
                "default_horizon": r["default_horizon"],
                "policy_linked_txn_type": r["policy_linked_txn_type"],
                "auto_suggest": r["suggested_min_amount_formula"],
                "recommended": recommended,
                "context_hint": context_hint
            })
        return grouped
    finally:
        session.close()


@router.post("/")
async def create_user_goal(payload: GoalIntake, user: UserDep = Depends(get_current_user)):
    """Insert a user goal; DB triggers derive linked_txn_type and priority_rank."""
    session = SessionLocal()
    user_uuid = uuid.UUID(user.user_id) if isinstance(user.user_id, str) else user.user_id
    try:
        # Validate master existence and get default policy
        cat = session.execute(text(
            """
            SELECT default_horizon, policy_linked_txn_type
            FROM goal.goal_category_master
            WHERE goal_category = :gc AND goal_name = :gn AND active = TRUE
            """
        ), {"gc": payload.goal_category, "gn": payload.goal_name}).mappings().first()
        if not cat:
            # Allow custom goal: upsert into master when category is 'Custom'
            if payload.goal_category == 'Custom':
                default_horizon = payload.goal_type
                if default_horizon not in ('short_term','medium_term','long_term'):
                    default_horizon = 'short_term'
                session.execute(text(
                    """
                    INSERT INTO goal.goal_category_master (
                        goal_category, goal_name, default_horizon, policy_linked_txn_type, is_mandatory_flag, active
                    ) VALUES (
                        :gc, :gn, :h, 'wants', FALSE, TRUE
                    ) ON CONFLICT (goal_category, goal_name) DO NOTHING
                    """
                ), {"gc": payload.goal_category, "gn": payload.goal_name, "h": default_horizon})
                cat = {"default_horizon": default_horizon, "policy_linked_txn_type": 'wants'}
            else:
                raise HTTPException(status_code=400, detail="Invalid goal_category/goal_name combination")
        goal_name = payload.goal_name
        goal_type = payload.goal_type
        linked_txn_type = cat["policy_linked_txn_type"]

        # Validate/derive target_date
        today = date.today()
        target_date = None
        if payload.target_date:
            try:
                td_parsed = datetime.fromisoformat(payload.target_date).date()
                if td_parsed < today:
                    raise HTTPException(status_code=400, detail="target_date must be today or later")
                target_date = td_parsed
            except ValueError:
                raise HTTPException(status_code=400, detail="Invalid target_date format; expected ISO date")
        else:
            # Retirement default using age band (recommend ~60 years)
            if goal_name.lower().startswith("retirement"):
                ctx_age = session.execute(text(
                    "SELECT age_band FROM goal.user_life_context WHERE user_id = :u"
                ), {"u": str(user_uuid)}).scalar()
                approx_age = None
                if ctx_age:
                    approx_age = {
                        "18-24": 21,
                        "25-34": 30,
                        "35-44": 40,
                        "45-54": 50,
                        "55+": 55
                    }.get(ctx_age, None)
                years_to_target = 60 - approx_age if approx_age is not None else 20
                years_to_target = max(0, years_to_target)
                try:
                    target_date = date(today.year + years_to_target, today.month, min(today.day, 28))
                except Exception:
                    target_date = date(today.year + years_to_target, today.month, 28)
            else:
                # Default from horizon window
                months = {
                    "short_term": 24,
                    "medium_term": 48,
                    "long_term": 84
                }.get(goal_type, 36)
                year_offset = months // 12
                try:
                    target_date = date(today.year + year_offset, today.month, min(today.day, 28))
                except Exception:
                    target_date = date(today.year + year_offset, today.month, 28)

        # Choose cost value
        est_cost = payload.estimated_cost if payload.estimated_cost is not None else payload.target_amount

        # Enforce Emergency Fund existence unless exempt
        # Skip enforcement if this goal is Emergency Fund itself
        is_emergency_goal = goal_name.lower().startswith("emergency fund")
        if not is_emergency_goal:
            ctx = session.execute(text(
                "SELECT income_regularity, emergency_opt_out FROM goal.user_life_context WHERE user_id = :u"
            ), {"u": str(user_uuid)}).mappings().first()
            income_regularity = ctx["income_regularity"] if ctx else None
            emergency_opt_out = ctx["emergency_opt_out"] if ctx and ctx["emergency_opt_out"] is not None else False
            if income_regularity != "very_stable" and not emergency_opt_out:
                has_emergency = session.execute(text(
                """
                SELECT 1
                FROM goal.user_goals_master ug
                WHERE ug.user_id = :user_id
                  AND ug.goal_category = 'Emergency'
                  AND ug.goal_name ILIKE 'Emergency Fund%'
                LIMIT 1
                """
                ), {"user_id": str(user_uuid)}).scalar() is not None
                if not has_emergency:
                    raise HTTPException(status_code=400, detail="Emergency Fund required before adding other goals (or opt out in context)")

        result = session.execute(text(
            """
            INSERT INTO goal.user_goals_master (
                user_id, goal_category, goal_name, goal_type, linked_txn_type,
                estimated_cost, target_date, current_savings, notes
            ) VALUES (
                :user_id, :goal_category, :goal_name, :goal_type, :linked_txn_type,
                :estimated_cost, :target_date, :current_savings, :notes
            ) RETURNING goal_id
            """
        ), {
            "user_id": str(user_uuid),
            "goal_category": payload.goal_category,
            "goal_name": goal_name,
            "goal_type": goal_type,
            "linked_txn_type": (payload.linked_txn_type or linked_txn_type),
            "estimated_cost": est_cost,
            "target_date": target_date.isoformat() if isinstance(target_date, date) else payload.target_date,
            "current_savings": payload.current_savings,
            "notes": payload.notes
        })
        new_id = result.scalar()
        session.commit()
        return {"goal_id": str(new_id)}
    except HTTPException:
        session.rollback()
        raise
    except Exception as e:
        session.rollback()
        raise HTTPException(status_code=400, detail=f"Failed to create goal: {str(e)}")
    finally:
        session.close()


@router.post("/submit")
async def submit_questionnaire(payload: QuestionnairePayload, user: UserDep = Depends(get_current_user)):
    """Bulk submit: upsert life context, insert selected goals, return ids and ranks."""
    session = SessionLocal()
    user_uuid = uuid.UUID(user.user_id) if isinstance(user.user_id, str) else user.user_id
    try:
        # 1) Upsert life context
        ctx = payload.context
        session.execute(text(
            """
            INSERT INTO goal.user_life_context (
                user_id, age_band, dependents_spouse, dependents_children_count, dependents_parents_care,
                housing, employment, income_regularity, region_code, emergency_opt_out
            ) VALUES (
                :user_id, :age_band, :dependents_spouse, :dependents_children_count, :dependents_parents_care,
                :housing, :employment, :income_regularity, :region_code, :emergency_opt_out
            )
            ON CONFLICT (user_id) DO UPDATE SET
                age_band = EXCLUDED.age_band,
                dependents_spouse = EXCLUDED.dependents_spouse,
                dependents_children_count = EXCLUDED.dependents_children_count,
                dependents_parents_care = EXCLUDED.dependents_parents_care,
                housing = EXCLUDED.housing,
                employment = EXCLUDED.employment,
                income_regularity = EXCLUDED.income_regularity,
                region_code = EXCLUDED.region_code,
                emergency_opt_out = EXCLUDED.emergency_opt_out
            """
        ), {
            "user_id": str(user_uuid),
            **ctx.dict()
        })

        results: List[dict] = []

        # 2) Insert each goal
        for g in payload.selected_goals:
            # Validate master
            master = session.execute(text(
                """
                SELECT default_horizon, policy_linked_txn_type
                FROM goal.goal_category_master
                WHERE goal_category = :gc AND goal_name = :gn AND active = TRUE
                """
            ), {"gc": g.goal_category, "gn": g.goal_name}).mappings().first()
            if not master:
                if g.goal_category == 'Custom':
                    default_horizon = g.goal_type or 'short_term'
                    session.execute(text(
                        """
                        INSERT INTO goal.goal_category_master (
                            goal_category, goal_name, default_horizon, policy_linked_txn_type, is_mandatory_flag, active
                        ) VALUES (
                            :gc, :gn, :h, 'wants', FALSE, TRUE
                        ) ON CONFLICT (goal_category, goal_name) DO NOTHING
                        """
                    ), {"gc": g.goal_category, "gn": g.goal_name, "h": default_horizon})
                    master = {"default_horizon": default_horizon, "policy_linked_txn_type": 'wants'}
                else:
                    raise HTTPException(status_code=400, detail=f"Invalid goal: {g.goal_category} / {g.goal_name}")

            # Default goal_type from default_horizon if missing
            goal_type = g.goal_type or master["default_horizon"]

            # Validate/derive target_date like single create
            today = date.today()
            if g.target_date:
                td = datetime.fromisoformat(g.target_date).date()
                if td < today:
                    raise HTTPException(status_code=400, detail="target_date must be today or later")
                target_date = td
            else:
                months = {"short_term": 24, "medium_term": 48, "long_term": 84}.get(goal_type, 36)
                year_offset = months // 12
                target_date = date(today.year + year_offset, today.month, min(today.day, 28))

            # Emergency fund prerequisite (skip if emergency itself)
            is_emergency = g.goal_category == "Emergency" and g.goal_name.lower().startswith("emergency fund")
            if not is_emergency and ctx.income_regularity != "very_stable" and not (ctx.emergency_opt_out or False):
                has_emergency = session.execute(text(
                    """
                    SELECT 1 FROM goal.user_goals_master
                    WHERE user_id = :user_id
                      AND goal_category = 'Emergency'
                      AND goal_name ILIKE 'Emergency Fund%'
                    LIMIT 1
                    """
                ), {"user_id": str(user_uuid)}).scalar() is not None
                if not has_emergency:
                    raise HTTPException(status_code=400, detail="Emergency Fund required before adding other goals (or opt out in context)")

            # Insert
            ins = session.execute(text(
                """
                INSERT INTO goal.user_goals_master (
                    user_id, goal_category, goal_name, goal_type, linked_txn_type,
                    estimated_cost, target_date, current_savings, notes
                ) VALUES (
                    :user_id, :goal_category, :goal_name, :goal_type, :linked_txn_type,
                    :estimated_cost, :target_date, :current_savings, :notes
                ) RETURNING goal_id
                """
            ), {
                "user_id": str(user_uuid),
                "goal_category": g.goal_category,
                "goal_name": g.goal_name,
                "goal_type": goal_type,
                "linked_txn_type": (g.linked_txn_type or master["policy_linked_txn_type"]),
                "estimated_cost": g.estimated_cost,
                "target_date": target_date.isoformat(),
                "current_savings": g.current_savings,
                "notes": g.notes
            })
            gid = ins.scalar()

            # Fetch computed priority_rank
            row = session.execute(text(
                "SELECT priority_rank FROM goal.user_goals_master WHERE goal_id = :gid"
            ), {"gid": str(gid)}).first()

            results.append({"goal_id": str(gid), "priority_rank": (row[0] if row else None)})

        session.commit()
        return {"created": results}
    except HTTPException:
        session.rollback()
        raise
    except Exception as e:
        session.rollback()
        raise HTTPException(status_code=400, detail=f"Failed to submit questionnaire: {str(e)}")
    finally:
        session.close()


@router.put("/reorder")
async def reorder_goals(items: List[ReorderItem], user: UserDep = Depends(get_current_user)):
    """Update priority_rank in bulk for a user's goals."""
    session = SessionLocal()
    user_uuid = uuid.UUID(user.user_id) if isinstance(user.user_id, str) else user.user_id
    try:
        for item in items:
            session.execute(text(
                """
                UPDATE goal.user_goals_master
                SET priority_rank = :rank
                WHERE user_goal_id = :id AND user_id = :user_id
                """
            ), {
                "rank": item.priority_rank,
                "id": item.user_goal_id,
                "user_id": str(user_uuid)
            })
        session.commit()
        return {"updated": len(items)}
    except Exception as e:
        session.rollback()
        raise HTTPException(status_code=400, detail=f"Failed to reorder: {str(e)}")
    finally:
        session.close()


@router.get("/summary")
async def goals_summary(user: UserDep = Depends(get_current_user)):
    """Portfolio summary and readiness flags (e.g., missing Emergency Fund)."""
    session = SessionLocal()
    user_uuid = uuid.UUID(user.user_id) if isinstance(user.user_id, str) else user.user_id
    try:
        goals = session.execute(text(
            """
            SELECT g.goal_id, g.goal_category, g.goal_name, g.goal_type,
                   g.priority_rank, g.linked_txn_type,
                   g.estimated_cost, g.current_savings, g.target_date,
                   (g.estimated_cost - g.current_savings) AS funding_gap
            FROM goal.user_goals_master g
            WHERE g.user_id = :user_id
            ORDER BY g.priority_rank NULLS LAST, g.target_date NULLS LAST
            """
        ), {"user_id": str(user_uuid)}).mappings().all()

        # Readiness: emergency fund present?
        has_emergency = session.execute(text(
            """
            SELECT 1 FROM goal.user_goals_master
            WHERE user_id = :user_id
              AND goal_category = 'Emergency'
              AND goal_name ILIKE 'Emergency Fund%'
            LIMIT 1
            """
        ), {"user_id": str(user_uuid)}).scalar() is not None

        flags = []
        if not has_emergency:
            flags.append({
                "type": "missing_fundamental",
                "message": "Emergency Fund not set up"
            })

        return {
            "goals": goals,
            "flags": flags
        }
    finally:
        session.close()


class GoalUpdate(BaseModel):
    estimated_cost: Optional[float] = None
    current_savings: Optional[float] = None
    target_date: Optional[str] = None  # ISO date
    notes: Optional[str] = None


@router.patch("/{goal_id}")
async def update_goal(goal_id: str, payload: GoalUpdate, user: UserDep = Depends(get_current_user)):
    """Update an existing goal."""
    session = SessionLocal()
    user_uuid = uuid.UUID(user.user_id) if isinstance(user.user_id, str) else user.user_id
    try:
        # Verify ownership
        existing = session.execute(text(
            """
            SELECT goal_id FROM goal.user_goals_master
            WHERE goal_id = :goal_id AND user_id = :user_id
            """
        ), {"goal_id": goal_id, "user_id": str(user_uuid)}).scalar()
        
        if not existing:
            raise HTTPException(status_code=404, detail="Goal not found")

        # Build update dict
        updates: Dict[str, Any] = {}
        if payload.estimated_cost is not None:
            updates["estimated_cost"] = payload.estimated_cost
        if payload.current_savings is not None:
            updates["current_savings"] = payload.current_savings
        if payload.target_date is not None:
            try:
                td = datetime.fromisoformat(payload.target_date).date()
                if td < date.today():
                    raise HTTPException(status_code=400, detail="target_date must be today or later")
                updates["target_date"] = td.isoformat()
            except ValueError:
                raise HTTPException(status_code=400, detail="Invalid target_date format; expected ISO date")
        if payload.notes is not None:
            updates["notes"] = payload.notes

        if not updates:
            return {"message": "No updates provided"}

        # Build dynamic update query
        set_clauses = []
        params = {"goal_id": goal_id, "user_id": str(user_uuid)}
        for key, value in updates.items():
            set_clauses.append(f"{key} = :{key}")
            params[key] = value

        session.execute(text(
            f"""
            UPDATE goal.user_goals_master
            SET {', '.join(set_clauses)}
            WHERE goal_id = :goal_id AND user_id = :user_id
            """
        ), params)
        
        session.commit()
        return {"message": "Goal updated successfully", "goal_id": goal_id}
    except HTTPException:
        session.rollback()
        raise
    except Exception as e:
        session.rollback()
        raise HTTPException(status_code=400, detail=f"Failed to update goal: {str(e)}")
    finally:
        session.close()


