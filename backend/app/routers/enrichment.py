"""
Enrichment API Endpoints
Rule-based enrichment and user overrides
"""
from fastapi import APIRouter, Depends, HTTPException, status, Query
from typing import List, Optional
from pydantic import BaseModel
from app.routers.auth import get_current_user, UserDep
from app.services.enrichment import EnrichmentService, get_enrichment_service

router = APIRouter()


class EnrichmentRuleCreate(BaseModel):
    name: str
    priority: int = 100
    merchant_regex: Optional[str] = None
    description_regex: Optional[str] = None
    amount_min: Optional[float] = None
    amount_max: Optional[float] = None
    category: str
    subcategory: Optional[str] = None
    classification: str  # 'income', 'needs', 'wants', 'assets'


class EnrichmentOverrideCreate(BaseModel):
    transaction_id: str
    merchant_override: Optional[str] = None
    subcategory_override: Optional[str] = None
    category_override: Optional[str] = None
    classification_override: Optional[str] = None
    reason: Optional[str] = "User correction"


class EffectiveEnrichment(BaseModel):
    transaction_id: str
    effective_merchant: str
    effective_subcategory: Optional[str]
    effective_category: str
    effective_classification: str
    effective_confidence: float
    is_overridden: bool
    override_reason: Optional[str] = None


@router.post("/rules")
async def create_enrichment_rule(
    rule: EnrichmentRuleCreate,
    user: UserDep = Depends(get_current_user)
):
    """Create a new enrichment rule"""
    from app.models.enrichment_models import EnrichmentRule
    from app.database.postgresql import SessionLocal
    import uuid
    
    session = SessionLocal()
    try:
        rule_obj = EnrichmentRule(
            id=str(uuid.uuid4()),
            user_id=user.user_id,
            name=rule.name,
            priority=rule.priority,
            merchant_regex=rule.merchant_regex,
            description_regex=rule.description_regex,
            amount_min=rule.amount_min,
            amount_max=rule.amount_max,
            category=rule.category,
            subcategory=rule.subcategory,
            classification=rule.classification,
            is_active=True
        )
        
        session.add(rule_obj)
        session.commit()
        
        return {
            "rule_id": rule_obj.id,
            "message": "Enrichment rule created successfully"
        }
    finally:
        session.close()


@router.get("/rules")
async def list_enrichment_rules(
    user: UserDep = Depends(get_current_user)
):
    """List all enrichment rules for user"""
    from app.models.enrichment_models import EnrichmentRule
    from app.database.postgresql import SessionLocal
    
    session = SessionLocal()
    try:
        rules = session.query(EnrichmentRule).filter(
            EnrichmentRule.user_id == user.user_id,
            EnrichmentRule.is_active == True
        ).order_by(EnrichmentRule.priority.asc()).all()
        
        return {
            "rules": [
                {
                    "id": rule.id,
                    "name": rule.name,
                    "priority": rule.priority,
                    "category": rule.category,
                    "subcategory": rule.subcategory,
                    "classification": rule.classification,
                    "merchant_regex": rule.merchant_regex,
                    "description_regex": rule.description_regex,
                    "is_active": rule.is_active
                }
                for rule in rules
            ]
        }
    finally:
        session.close()


@router.post("/enrich/{transaction_id}")
async def enrich_transaction(
    transaction_id: str,
    user: UserDep = Depends(get_current_user)
):
    """Apply enrichment to a transaction"""
    from app.models.postgresql_models import Transaction
    from app.database.postgresql import SessionLocal
    
    session = SessionLocal()
    try:
        # Get transaction
        transaction = session.query(Transaction).filter(
            Transaction.id == transaction_id,
            Transaction.user_id == user.user_id
        ).first()
        
        if not transaction:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Transaction not found"
            )
        
        # Convert to dict
        txn_dict = {
            'id': transaction.id,
            'description': transaction.description,
            'amount': transaction.amount,
            'merchant': transaction.merchant,
            'bank': transaction.bank,
            'transaction_type': transaction.transaction_type.value
        }
        
        # Enrich
        service = EnrichmentService(user.user_id)
        enrichment = service.enrich_transaction(txn_dict)
        
        # Save enrichment
        enrichment_id = service.save_enrichment(transaction_id, enrichment)
        
        return {
            "transaction_id": transaction_id,
            "enrichment_id": enrichment_id,
            "enrichment": enrichment,
            "message": "Transaction enriched successfully"
        }
    finally:
        session.close()


@router.post("/override")
async def create_enrichment_override(
    override: EnrichmentOverrideCreate,
    user: UserDep = Depends(get_current_user)
):
    """Create user override for enrichment"""
    service = EnrichmentService(user.user_id)
    
    override_data = {
        'merchant': override.merchant_override,
        'subcategory': override.subcategory_override,
        'category': override.category_override,
        'classification': override.classification_override,
        'reason': override.reason
    }
    
    override_id = service.create_override(
        override.transaction_id,
        override_data
    )
    
    return {
        "override_id": override_id,
        "transaction_id": override.transaction_id,
        "message": "Override created successfully"
    }


@router.get("/effective/{transaction_id}")
async def get_effective_enrichment(
    transaction_id: str,
    user: UserDep = Depends(get_current_user)
):
    """Get effective enrichment (with overrides applied)"""
    service = EnrichmentService(user.user_id)
    
    enrichment = service.get_effective_enrichment(transaction_id)
    
    if not enrichment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Enrichment not found"
        )
    
    return enrichment


@router.get("/effective")
async def list_effective_enrichments(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=1000),
    classification: Optional[str] = None,
    is_overridden: Optional[bool] = None,
    user: UserDep = Depends(get_current_user)
):
    """List transactions with effective enrichment (using view)"""
    from app.database.postgresql import SessionLocal
    from sqlalchemy import text
    
    session = SessionLocal()
    try:
        # Query the view
        query = f"""
        SELECT * FROM vw_txn_effective
        WHERE user_id = :user_id
        """
        
        if classification:
            query += " AND effective_classification = :classification"
        
        if is_overridden is not None:
            query += f" AND is_overridden = {is_overridden}"
        
        query += " ORDER BY transaction_date DESC LIMIT :limit OFFSET :offset"
        
        result = session.execute(
            text(query),
            {
                'user_id': user.user_id,
                'classification': classification,
                'limit': limit,
                'offset': skip
            }
        )
        
        rows = result.fetchall()
        
        return {
            "data": [
                {
                    "transaction_id": row[0],
                    "effective_merchant": row[5] if len(row) > 5 else None,
                    "effective_subcategory": row[6] if len(row) > 6 else None,
                    "effective_category": row[7] if len(row) > 7 else None,
                    "effective_classification": row[8] if len(row) > 8 else None,
                    "effective_confidence": float(row[9]) if len(row) > 9 else 0.0,
                    "is_overridden": row[12] if len(row) > 12 else False,
                    "amount": float(row[2]) if len(row) > 2 else 0.0,
                    "transaction_date": str(row[4]) if len(row) > 4 else None
                }
                for row in rows
            ],
            "count": len(rows)
        }
    finally:
        session.close()

