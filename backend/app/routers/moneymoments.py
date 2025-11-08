"""
MoneyMoments API Endpoints
Behavioral nudging and habit formation engine
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


# Request/Response Models
class UserTraits(BaseModel):
    age_band: str
    gender: Optional[str] = None
    region_code: str
    lifestyle_tags: Optional[List[str]] = None


class DeriveSignalsRequest(BaseModel):
    as_of_date: str  # YYYY-MM-DD format


class QueueDeliveriesRequest(BaseModel):
    as_of_date: str  # YYYY-MM-DD format


class LogInteractionRequest(BaseModel):
    delivery_id: str
    event_type: str  # 'view', 'click', 'dismiss'
    metadata: Optional[Dict[str, Any]] = None


class SuppressionSettings(BaseModel):
    channel: str  # 'in_app', 'push', 'email'
    muted_until: Optional[str] = None  # ISO datetime
    daily_cap: Optional[int] = None


# User Traits
@router.get("/traits")
async def get_user_traits(user: UserDep = Depends(get_current_user)):
    """Get user traits for nudge personalization."""
    session = SessionLocal()
    user_uuid = uuid.UUID(user.user_id) if isinstance(user.user_id, str) else user.user_id
    try:
        row = session.execute(text("""
            SELECT user_id, age_band, gender, region_code, lifestyle_tags, created_at, updated_at
            FROM moneymoments.mm_user_traits
            WHERE user_id = :user_id
        """), {"user_id": str(user_uuid)}).mappings().first()
        
        if not row:
            return None
        
        return dict(row)
    finally:
        session.close()


@router.put("/traits")
async def upsert_user_traits(
    traits: UserTraits,
    user: UserDep = Depends(get_current_user)
):
    """Create or update user traits."""
    session = SessionLocal()
    user_uuid = uuid.UUID(user.user_id) if isinstance(user.user_id, str) else user.user_id
    try:
        lifestyle_tags_json = traits.lifestyle_tags or []
        
        session.execute(text("""
            INSERT INTO moneymoments.mm_user_traits (
                user_id, age_band, gender, region_code, lifestyle_tags, updated_at
            ) VALUES (
                :user_id, :age_band, :gender, :region_code, :lifestyle_tags::jsonb, NOW()
            )
            ON CONFLICT (user_id) DO UPDATE SET
                age_band = EXCLUDED.age_band,
                gender = EXCLUDED.gender,
                region_code = EXCLUDED.region_code,
                lifestyle_tags = EXCLUDED.lifestyle_tags,
                updated_at = NOW()
        """), {
            "user_id": str(user_uuid),
            "age_band": traits.age_band,
            "gender": traits.gender,
            "region_code": traits.region_code,
            "lifestyle_tags": str(lifestyle_tags_json).replace("'", '"')
        })
        
        session.commit()
        return {"status": "ok", "message": "Traits updated successfully"}
    except Exception as e:
        session.rollback()
        raise HTTPException(status_code=400, detail=f"Failed to update traits: {str(e)}")
    finally:
        session.close()


# Signals
@router.get("/signals")
async def get_signals(
    as_of_date: Optional[str] = Query(None, description="Date in YYYY-MM-DD format"),
    user: UserDep = Depends(get_current_user)
):
    """Get daily behavioral signals for the user."""
    session = SessionLocal()
    user_uuid = uuid.UUID(user.user_id) if isinstance(user.user_id, str) else user.user_id
    try:
        if not as_of_date:
            as_of_date = date.today().isoformat()
        
        row = session.execute(text("""
            SELECT 
                user_id, as_of_date, dining_txn_7d, dining_spend_7d,
                shopping_txn_7d, shopping_spend_7d, travel_txn_30d, travel_spend_30d,
                wants_share_30d, recurring_merchants_90d, wants_vs_plan_pct,
                assets_vs_plan_pct, rank1_goal_underfund_amt, rank1_goal_underfund_pct,
                last_nudge_sent_at, created_at
            FROM moneymoments.mm_signal_daily
            WHERE user_id = :user_id AND as_of_date = :as_of_date
        """), {
            "user_id": str(user_uuid),
            "as_of_date": as_of_date
        }).mappings().first()
        
        if not row:
            return None
        
        return dict(row)
    finally:
        session.close()


@router.post("/signals/derive")
async def derive_signals(
    request: DeriveSignalsRequest,
    user: UserDep = Depends(get_current_user)
):
    """Derive daily signals for all users (or specific date)."""
    session = SessionLocal()
    try:
        # Parse date
        as_of_date_obj = datetime.fromisoformat(request.as_of_date).date()
        
        # Call the derivation function
        session.execute(text("""
            SELECT moneymoments.derive_signal_daily(:as_of_date)
        """), {"as_of_date": as_of_date_obj})
        
        session.commit()
        return {
            "status": "ok",
            "message": f"Signals derived for {request.as_of_date}",
            "as_of_date": request.as_of_date
        }
    except Exception as e:
        session.rollback()
        raise HTTPException(status_code=400, detail=f"Failed to derive signals: {str(e)}")
    finally:
        session.close()


# Nudges
@router.get("/nudges/pending")
async def get_pending_nudges(
    user: UserDep = Depends(get_current_user)
):
    """Get pending nudges for the user."""
    session = SessionLocal()
    user_uuid = uuid.UUID(user.user_id) if isinstance(user.user_id, str) else user.user_id
    try:
        results = session.execute(text("""
            SELECT 
                c.candidate_id, c.user_id, c.as_of_date, c.rule_id, c.template_code,
                c.score, c.reason_json, c.status, c.created_at,
                r.name AS rule_name, r.description AS rule_description,
                t.title_template, t.body_template, t.cta_text, t.cta_deeplink,
                t.humor_style
            FROM moneymoments.mm_nudge_candidate c
            JOIN moneymoments.mm_nudge_rule_master r ON r.rule_id = c.rule_id
            JOIN moneymoments.mm_nudge_template_master t ON t.template_code = c.template_code
            WHERE c.user_id = :user_id AND c.status = 'pending'
            ORDER BY c.score DESC, c.created_at DESC
            LIMIT 10
        """), {"user_id": str(user_uuid)}).mappings().all()
        
        return {"nudges": [dict(r) for r in results]}
    finally:
        session.close()


@router.get("/nudges/delivered")
async def get_delivered_nudges(
    limit: int = Query(20, ge=1, le=100),
    user: UserDep = Depends(get_current_user)
):
    """Get recently delivered nudges for the user."""
    session = SessionLocal()
    user_uuid = uuid.UUID(user.user_id) if isinstance(user.user_id, str) else user.user_id
    try:
        results = session.execute(text("""
            SELECT 
                d.delivery_id, d.candidate_id, d.user_id, d.rule_id, d.template_code,
                d.channel, d.sent_at, d.send_status, d.metadata_json,
                r.name AS rule_name,
                t.title_template, t.body_template, t.cta_text, t.cta_deeplink,
                COALESCE(COUNT(i.interaction_id), 0) AS interaction_count
            FROM moneymoments.mm_nudge_delivery_log d
            JOIN moneymoments.mm_nudge_rule_master r ON r.rule_id = d.rule_id
            JOIN moneymoments.mm_nudge_template_master t ON t.template_code = d.template_code
            LEFT JOIN moneymoments.mm_nudge_interaction_log i ON i.delivery_id = d.delivery_id
            WHERE d.user_id = :user_id
            GROUP BY d.delivery_id, d.candidate_id, d.user_id, d.rule_id, d.template_code,
                     d.channel, d.sent_at, d.send_status, d.metadata_json,
                     r.name, t.title_template, t.body_template, t.cta_text, t.cta_deeplink
            ORDER BY d.sent_at DESC
            LIMIT :limit
        """), {
            "user_id": str(user_uuid),
            "limit": limit
        }).mappings().all()
        
        return {"nudges": [dict(r) for r in results]}
    finally:
        session.close()


@router.post("/nudges/candidates/derive")
async def derive_candidates(
    request: DeriveSignalsRequest,
    user: UserDep = Depends(get_current_user)
):
    """Derive nudge candidates for dining rule (MVP)."""
    session = SessionLocal()
    try:
        as_of_date_obj = datetime.fromisoformat(request.as_of_date).date()
        
        # Call the derivation function
        session.execute(text("""
            SELECT moneymoments.derive_candidates_dining(:as_of_date)
        """), {"as_of_date": as_of_date_obj})
        
        session.commit()
        return {
            "status": "ok",
            "message": f"Candidates derived for {request.as_of_date}",
            "as_of_date": request.as_of_date
        }
    except Exception as e:
        session.rollback()
        raise HTTPException(status_code=400, detail=f"Failed to derive candidates: {str(e)}")
    finally:
        session.close()


@router.post("/nudges/queue")
async def queue_deliveries(
    request: QueueDeliveriesRequest,
    user: UserDep = Depends(get_current_user)
):
    """Queue and deliver pending nudges."""
    session = SessionLocal()
    try:
        as_of_date_obj = datetime.fromisoformat(request.as_of_date).date()
        
        # Call the queue function
        session.execute(text("""
            SELECT moneymoments.queue_deliveries(:as_of_date)
        """), {"as_of_date": as_of_date_obj})
        
        session.commit()
        return {
            "status": "ok",
            "message": f"Deliveries queued for {request.as_of_date}",
            "as_of_date": request.as_of_date
        }
    except Exception as e:
        session.rollback()
        raise HTTPException(status_code=400, detail=f"Failed to queue deliveries: {str(e)}")
    finally:
        session.close()


# Interactions
@router.post("/nudges/interactions")
async def log_interaction(
    interaction: LogInteractionRequest,
    user: UserDep = Depends(get_current_user)
):
    """Log user interaction with a nudge (view, click, dismiss)."""
    session = SessionLocal()
    user_uuid = uuid.UUID(user.user_id) if isinstance(user.user_id, str) else user.user_id
    try:
        # Verify delivery belongs to user
        delivery = session.execute(text("""
            SELECT delivery_id, user_id FROM moneymoments.mm_nudge_delivery_log
            WHERE delivery_id = :delivery_id AND user_id = :user_id
        """), {
            "delivery_id": interaction.delivery_id,
            "user_id": str(user_uuid)
        }).scalar()
        
        if not delivery:
            raise HTTPException(status_code=404, detail="Delivery not found")
        
        # Insert interaction
        result = session.execute(text("""
            INSERT INTO moneymoments.mm_nudge_interaction_log (
                delivery_id, user_id, event_type, metadata_json
            ) VALUES (
                :delivery_id, :user_id, :event_type, :metadata_json::jsonb
            ) RETURNING interaction_id
        """), {
            "delivery_id": interaction.delivery_id,
            "user_id": str(user_uuid),
            "event_type": interaction.event_type,
            "metadata_json": str(interaction.metadata or {}).replace("'", '"')
        })
        
        interaction_id = result.scalar()
        session.commit()
        
        return {
            "status": "ok",
            "interaction_id": str(interaction_id),
            "message": "Interaction logged successfully"
        }
    except HTTPException:
        session.rollback()
        raise
    except Exception as e:
        session.rollback()
        raise HTTPException(status_code=400, detail=f"Failed to log interaction: {str(e)}")
    finally:
        session.close()


# Suppression
@router.get("/suppression")
async def get_suppression_settings(
    user: UserDep = Depends(get_current_user)
):
    """Get user suppression settings for all channels."""
    session = SessionLocal()
    user_uuid = uuid.UUID(user.user_id) if isinstance(user.user_id, str) else user.user_id
    try:
        results = session.execute(text("""
            SELECT user_id, channel, muted_until, daily_cap
            FROM moneymoments.mm_user_suppression
            WHERE user_id = :user_id
        """), {"user_id": str(user_uuid)}).mappings().all()
        
        return {"settings": [dict(r) for r in results]}
    finally:
        session.close()


@router.put("/suppression")
async def update_suppression(
    settings: SuppressionSettings,
    user: UserDep = Depends(get_current_user)
):
    """Update suppression settings for a channel."""
    session = SessionLocal()
    user_uuid = uuid.UUID(user.user_id) if isinstance(user.user_id, str) else user.user_id
    try:
        muted_until_dt = None
        if settings.muted_until:
            muted_until_dt = datetime.fromisoformat(settings.muted_until.replace('Z', '+00:00'))
        
        session.execute(text("""
            INSERT INTO moneymoments.mm_user_suppression (
                user_id, channel, muted_until, daily_cap
            ) VALUES (
                :user_id, :channel, :muted_until, :daily_cap
            )
            ON CONFLICT (user_id, channel) DO UPDATE SET
                muted_until = EXCLUDED.muted_until,
                daily_cap = EXCLUDED.daily_cap
        """), {
            "user_id": str(user_uuid),
            "channel": settings.channel,
            "muted_until": muted_until_dt,
            "daily_cap": settings.daily_cap or 3
        })
        
        session.commit()
        return {"status": "ok", "message": "Suppression settings updated"}
    except Exception as e:
        session.rollback()
        raise HTTPException(status_code=400, detail=f"Failed to update suppression: {str(e)}")
    finally:
        session.close()


# Analytics
@router.get("/analytics/ctr")
async def get_ctr_analytics(
    days: int = Query(30, ge=1, le=365),
    user: UserDep = Depends(get_current_user)
):
    """Get click-through rate analytics for user's nudges."""
    session = SessionLocal()
    user_uuid = uuid.UUID(user.user_id) if isinstance(user.user_id, str) else user.user_id
    try:
        result = session.execute(text("""
            WITH delivered AS (
                SELECT COUNT(*) AS total_delivered
                FROM moneymoments.mm_nudge_delivery_log
                WHERE user_id = :user_id
                  AND sent_at >= NOW() - (CAST(:days AS text) || ' days')::interval
            ),
            clicked AS (
                SELECT COUNT(DISTINCT delivery_id) AS total_clicked
                FROM moneymoments.mm_nudge_interaction_log
                WHERE user_id = :user_id
                  AND event_type = 'click'
                  AND event_at >= NOW() - (CAST(:days AS text) || ' days')::interval
            ),
            viewed AS (
                SELECT COUNT(DISTINCT delivery_id) AS total_viewed
                FROM moneymoments.mm_nudge_interaction_log
                WHERE user_id = :user_id
                  AND event_type = 'view'
                  AND event_at >= NOW() - (CAST(:days AS text) || ' days')::interval
            )
            SELECT 
                COALESCE(d.total_delivered, 0) AS total_delivered,
                COALESCE(v.total_viewed, 0) AS total_viewed,
                COALESCE(c.total_clicked, 0) AS total_clicked,
                CASE 
                    WHEN COALESCE(d.total_delivered, 0) > 0 
                    THEN ROUND(100.0 * COALESCE(v.total_viewed, 0) / d.total_delivered, 2)
                    ELSE 0 
                END AS view_rate,
                CASE 
                    WHEN COALESCE(v.total_viewed, 0) > 0 
                    THEN ROUND(100.0 * COALESCE(c.total_clicked, 0) / v.total_viewed, 2)
                    ELSE 0 
                END AS ctr
            FROM delivered d
            CROSS JOIN viewed v
            CROSS JOIN clicked c
        """), {
            "user_id": str(user_uuid),
            "days": days
        }).mappings().first()
        
        return dict(result) if result else {
            "total_delivered": 0,
            "total_viewed": 0,
            "total_clicked": 0,
            "view_rate": 0,
            "ctr": 0
        }
    finally:
        session.close()


@router.get("/analytics/behavior-shift")
async def get_behavior_shift(
    months: int = Query(3, ge=1, le=12),
    user: UserDep = Depends(get_current_user)
):
    """Get behavior shift metrics (wants% change over time)."""
    session = SessionLocal()
    user_uuid = uuid.UUID(user.user_id) if isinstance(user.user_id, str) else user.user_id
    try:
        results = session.execute(text("""
            SELECT 
                as_of_date,
                wants_share_30d,
                wants_vs_plan_pct,
                assets_vs_plan_pct,
                rank1_goal_underfund_pct
            FROM moneymoments.mm_signal_daily
            WHERE user_id = :user_id
              AND as_of_date >= CURRENT_DATE - (CAST(:months AS text) || ' months')::interval
            ORDER BY as_of_date DESC
        """), {
            "user_id": str(user_uuid),
            "months": months
        }).mappings().all()
        
        signals = [dict(r) for r in results]
        
        # Calculate month-over-month change
        if len(signals) >= 2:
            current = signals[0]
            previous = signals[-1] if len(signals) > 1 else current
            
            wants_shift = None
            if current.get('wants_share_30d') and previous.get('wants_share_30d'):
                wants_shift = current['wants_share_30d'] - previous['wants_share_30d']
        else:
            wants_shift = None
        
        return {
            "signals": signals,
            "wants_shift": wants_shift,
            "months_tracked": len(signals)
        }
    finally:
        session.close()

