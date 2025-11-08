"""
Learning Service
Automatically creates merchant_rules and learns from user edits
Production-safe with tenant scoping, pattern quality, and idempotency
"""

from app.database.postgresql import SessionLocal
from app.models.spendsense_models import MerchantRule, DimCategory, DimSubcategory
from sqlalchemy import text
from sqlalchemy.dialects.postgresql import insert as pg_insert
from typing import Optional
import re
import hashlib
import uuid as _uuid

# Priority constants: user-learned rules outrank generic seeds
USER_RULE_PRIORITY = 10   # Merchant-based rules from user edits (wins over seed rules 15-90)
DESC_RULE_PRIORITY = 12   # Description-based rules (less reliable than merchant, but still user-driven)

# Stopwords to filter out from description patterns
STOPWORDS = {'upi', 'imps', 'neft', 'rtgs', 'txn', 'transaction', 'ref', 'utr', 'rrn', 'payment', 'card', 'bill', 'dr', 'cr', 'debit', 'credit'}

# Guardrails
MIN_MERCHANT_LENGTH = 3
MIN_PATTERN_TOKENS = 2
MAX_RULES_PER_USER_PER_DAY = 50  # Throttle to prevent abuse


def _pattern_hash(pattern: str) -> str:
    """Generate SHA1 hash of pattern for deduplication"""
    return hashlib.sha1(pattern.encode('utf-8')).hexdigest()


def merchant_pattern(name: str) -> Optional[str]:
    """
    Build robust merchant pattern that matches words, allows spacing/punctuation,
    and is case-insensitive—without overfitting.
    
    Example: "Amazon Pay India" → "(?i)\\bAMAZON.*PAY.*INDIA\\b"
    """
    if not name or len(name.strip()) < MIN_MERCHANT_LENGTH:
        return None
    
    # Normalize & escape; allow flexible spaces/punct between tokens
    tokens = re.sub(r'[^A-Za-z0-9]+', ' ', name.strip(), flags=re.I).split()
    if not tokens or len(tokens) < 1:
        return None
    
    # Use word boundaries to avoid substrings like "AMAZONIA" matching "AMAZON"
    body = r'.*'.join(map(re.escape, tokens))
    pattern = rf'(?i)\b{body}\b'
    
    return pattern


def desc_pattern(description: str) -> Optional[str]:
    """
    Extract description pattern from strongest alnum tokens, dropping stopwords.
    Avoids just taking "first 2-3 words" by filtering UPI/NEFT/IMPS boilerplate.
    
    Example: "UPI-AMAZON PAY INDIA-..." → "(?i).*AMAZON.*PAY.*INDIA.*"
    """
    if not description:
        return None
    
    # Extract alphanumeric tokens, uppercase
    tokens = re.sub(r'[^A-Za-z0-9]+', ' ', description.upper()).split()
    
    # Filter stopwords
    tokens = [t for t in tokens if t not in STOPWORDS and len(t) >= 2]
    
    if len(tokens) < MIN_PATTERN_TOKENS:
        return None
    
    # Take top few meaningful tokens
    tokens = tokens[:3]
    
    # Build pattern with flexible spacing
    body = r'.*'.join(map(re.escape, tokens))
    pattern = rf'(?i).*{body}.*'
    
    return pattern


def _check_rate_limit(user_id: str, tenant_id: Optional[str] = None) -> bool:
    """
    Check if user has exceeded daily rate limit for rule creation.
    Returns True if under limit, False if exceeded.
    """
    session = SessionLocal()
    try:
        from datetime import datetime, timedelta
        today_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
        
        # Count rules created today by this user
        query = session.query(MerchantRule).filter(
            MerchantRule.created_by == _uuid.UUID(user_id) if isinstance(user_id, str) else user_id,
            MerchantRule.source == 'learned',
            MerchantRule.created_at >= today_start
        )
        
        if tenant_id:
            query = query.filter(MerchantRule.tenant_id == (_uuid.UUID(tenant_id) if isinstance(tenant_id, str) else tenant_id))
        
        count = query.count()
        
        return count < MAX_RULES_PER_USER_PER_DAY
        
    except Exception as e:
        print(f"⚠️  Error checking rate limit: {e}")
        # Allow on error (fail open)
        return True
    finally:
        session.close()


def upsert_rule(
    session,
    applies_to: str,
    pattern_regex: str,
    category_code: str,
    subcategory_code: Optional[str],
    priority: int,
    created_by: _uuid.UUID,
    tenant_id: Optional[_uuid.UUID] = None,
    source: str = 'learned'
) -> Optional[_uuid.UUID]:
    """
    Idempotent upsert of merchant rule using ON CONFLICT.
    Uses pattern_hash for efficient deduplication.
    """
    pattern_hash_value = _pattern_hash(pattern_regex)
    
    # Use NULL tenant_id as '00000000-0000-0000-0000-000000000000' for uniqueness
    tenant_uuid = tenant_id or _uuid.UUID('00000000-0000-0000-0000-000000000000')
    
    stmt = pg_insert(MerchantRule.__table__).values(
        rule_id=_uuid.uuid4(),
        applies_to=applies_to,
        pattern_regex=pattern_regex,
        pattern_hash=pattern_hash_value,
        category_code=category_code,
        subcategory_code=subcategory_code,
        priority=priority,
        active=True,
        created_by=created_by,
        tenant_id=tenant_id,  # Keep actual tenant_id (can be NULL for global)
        source=source,
    ).on_conflict_do_update(
        # Conflict on (tenant_id, applies_to, pattern_hash) unique index
        index_elements=['tenant_id', 'applies_to', 'pattern_hash'],
        set_={
            'category_code': category_code,
            'subcategory_code': subcategory_code,
            'priority': priority,
            'active': True,
            'created_by': created_by,  # Update creator if changed
            'source': source,
        }
    ).returning(MerchantRule.rule_id)
    
    result = session.execute(stmt).scalar_one_or_none()
    return result


def learn_from_edit(
    user_id: str,
    merchant_name: Optional[str],
    description: Optional[str],
    category_code: Optional[str],
    subcategory_code: Optional[str],
    txn_id: Optional[str] = None,
    tenant_id: Optional[str] = None
) -> Optional[str]:
    """
    Learn from a user edit by creating/updating merchant_rules.
    
    When a user edits a transaction and sets:
    - merchant_name + category_code + subcategory_code
    → Create a merchant rule that matches this merchant to this category/subcategory
    
    Args:
        user_id: User who made the edit
        merchant_name: Merchant name from the edit
        description: Transaction description (fallback for pattern matching)
        category_code: Category assigned by user
        subcategory_code: Subcategory assigned by user
        txn_id: Optional transaction ID for logging
        tenant_id: Optional tenant ID for multi-tenant isolation
    
    Returns:
        rule_id if a rule was created/updated, None otherwise
    """
    session = SessionLocal()
    try:
        # Only learn if merchant_name and category_code are provided
        if not category_code:
            return None
        
        # Check rate limit
        if not _check_rate_limit(user_id, tenant_id):
            print(f"⚠️  Rate limit exceeded for user {user_id}")
            return None
        
        # Check if category exists
        category = session.query(DimCategory).filter(
            DimCategory.category_code == category_code,
            DimCategory.active == True
        ).first()
        
        if not category:
            # Category doesn't exist - could create it, but for now just return
            return None
        
        # Check subcategory if provided
        subcategory = None
        if subcategory_code:
            subcategory = session.query(DimSubcategory).filter(
                DimSubcategory.subcategory_code == subcategory_code,
                DimSubcategory.category_code == category_code,
                DimSubcategory.active == True
            ).first()
        
        user_uuid = _uuid.UUID(user_id) if isinstance(user_id, str) else user_id
        tenant_uuid = _uuid.UUID(tenant_id) if tenant_id and isinstance(tenant_id, str) else tenant_id
        
        # Prefer merchant_name if available
        if merchant_name:
            pattern = merchant_pattern(merchant_name)
            if pattern:
                rule_id = upsert_rule(
                    session,
                    applies_to='merchant',
                    pattern_regex=pattern,
                    category_code=category_code,
                    subcategory_code=subcategory_code if subcategory else None,
                    priority=USER_RULE_PRIORITY,
                    created_by=user_uuid,
                    tenant_id=tenant_uuid,
                    source='learned'
                )
                
                session.commit()
                
                # Clear cache so new rule is picked up immediately
                from app.services.pg_rules_client import clear_cache
                clear_cache()
                
                return str(rule_id) if rule_id else None
        
        # Fallback to description pattern if merchant_name not available
        if description:
            pattern = desc_pattern(description)
            if pattern:
                rule_id = upsert_rule(
                    session,
                    applies_to='description',
                    pattern_regex=pattern,
                    category_code=category_code,
                    subcategory_code=subcategory_code if subcategory else None,
                    priority=DESC_RULE_PRIORITY,
                    created_by=user_uuid,
                    tenant_id=tenant_uuid,
                    source='learned'
                )
                
                session.commit()
                
                # Clear cache
                from app.services.pg_rules_client import clear_cache
                clear_cache()
                
                return str(rule_id) if rule_id else None
        
        return None
        
    except Exception as e:
        session.rollback()
        print(f"⚠️  Error learning from edit: {e}")
        import traceback
        traceback.print_exc()
        return None
    finally:
        session.close()


def learn_from_description_pattern(
    user_id: str,
    description: str,
    category_code: str,
    subcategory_code: Optional[str] = None,
    tenant_id: Optional[str] = None
) -> Optional[str]:
    """
    Learn from description patterns when merchant_name is not available.
    Creates a rule that matches description patterns.
    
    Args:
        user_id: User who made the edit
        description: Transaction description to learn from
        category_code: Category assigned by user
        subcategory_code: Subcategory assigned by user
        tenant_id: Optional tenant ID for multi-tenant isolation
    
    Returns:
        rule_id if a rule was created, None otherwise
    """
    session = SessionLocal()
    try:
        if not description or not category_code:
            return None
        
        # Check rate limit
        if not _check_rate_limit(user_id, tenant_id):
            return None
        
        # Check if category exists
        category = session.query(DimCategory).filter(
            DimCategory.category_code == category_code,
            DimCategory.active == True
        ).first()
        
        if not category:
            return None
        
        # Check subcategory if provided
        subcategory = None
        if subcategory_code:
            subcategory = session.query(DimSubcategory).filter(
                DimSubcategory.subcategory_code == subcategory_code,
                DimSubcategory.category_code == category_code,
                DimSubcategory.active == True
            ).first()
        
        pattern = desc_pattern(description)
        if not pattern:
            return None
        
        user_uuid = _uuid.UUID(user_id) if isinstance(user_id, str) else user_id
        tenant_uuid = _uuid.UUID(tenant_id) if tenant_id and isinstance(tenant_id, str) else tenant_id
        
        rule_id = upsert_rule(
            session,
            applies_to='description',
            pattern_regex=pattern,
            category_code=category_code,
            subcategory_code=subcategory_code if subcategory else None,
            priority=DESC_RULE_PRIORITY,
            created_by=user_uuid,
            tenant_id=tenant_uuid,
            source='learned'
        )
        
        session.commit()
        
        # Clear cache
        from app.services.pg_rules_client import clear_cache
        clear_cache()
        
        return str(rule_id) if rule_id else None
        
    except Exception as e:
        session.rollback()
        print(f"⚠️  Error learning from description: {e}")
        import traceback
        traceback.print_exc()
        return None
    finally:
        session.close()
