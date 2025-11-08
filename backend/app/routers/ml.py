from fastapi import APIRouter, Depends, Query
from typing import Optional
from datetime import datetime
from app.routers.auth import get_current_user, UserDep

router = APIRouter()


@router.get("/categories/predict")
async def predict_category(
    description: str,
    amount: float,
    merchant: Optional[str] = None,
    user: UserDep = Depends(get_current_user)
):
    """
    Predict transaction category using merchant_rules (rule-based learning).
    
    This uses the merchant_rules that were automatically created from user edits,
    so it learns from user corrections over time.
    """
    from app.services.pg_rules_client import PGRulesClient
    
    # Use rule-based matching (which learns from user edits)
    # TODO: Extract tenant_id from user if available
    tenant_id = None  # Can be extracted from user context if multi-tenant
    
    match = PGRulesClient.match_merchant(
        merchant_name=merchant,
        description=description,
        user_id=str(user.user_id),
        tenant_id=tenant_id,
        use_cache=True
    )
    
    if match:
        return {
            "category": match.get("category_code"),
            "subcategory": match.get("subcategory_code"),
            "confidence": match.get("confidence", 0.85),
            "rule_id": match.get("rule_id"),
            "applies_to": match.get("applies_to"),  # 'merchant' or 'description'
            "matched": match.get("matched_text"),  # The text that matched the pattern
            "source": match.get("source"),  # 'learned' | 'seed' | 'ops'
            "method": "rule_based"  # Indicates it came from learned rules
        }
    
    # Fallback: no rule matched
    return {
        "category": "others",
        "confidence": 0.5,
        "method": "fallback"
    }


@router.get("/insights")
async def get_ml_insights(
    user: UserDep = Depends(get_current_user),
    period: str = Query("month", regex="^(day|week|month|year)$")
):
    """Get ML-powered insights"""
    # TODO: Implement ML insights generation
    return {
        "spending_trends": [],
        "anomalies": [],
        "recommendations": [],
        "predictions": []
    }


@router.get("/anomalies")
async def detect_anomalies(
    user: UserDep = Depends(get_current_user),
    days: int = Query(30, ge=1, le=365)
):
    """Detect anomalous transactions"""
    # TODO: Implement anomaly detection
    return []


@router.get("/predictions")
async def get_predictions(
    user: UserDep = Depends(get_current_user)
):
    """Get spending predictions"""
    # TODO: Implement prediction model
    return {
        "predicted_monthly_spending": 0.0,
        "confidence": 0.0
    }

