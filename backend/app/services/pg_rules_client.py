"""
PostgreSQL Rules Client
Cached fetch of merchant_rules, parser_rules with TTL (5-10 min)
"""

from app.database.postgresql import SessionLocal
from app.models.spendsense_models import MerchantRule
from sqlalchemy import text
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
import functools
import time
import re


# In-memory cache with TTL
_cache: Dict[str, Dict[str, Any]] = {}
_cache_ttl_seconds = 600  # 10 minutes


def _is_cache_valid(cache_key: str) -> bool:
    """Check if cache entry is still valid"""
    if cache_key not in _cache:
        return False
    
    cached_data = _cache[cache_key]
    expires_at = cached_data.get("expires_at")
    
    if expires_at is None:
        return False
    
    return datetime.utcnow() < expires_at


def _get_from_cache(cache_key: str) -> Optional[Any]:
    """Get value from cache if valid"""
    if _is_cache_valid(cache_key):
        return _cache[cache_key].get("data")
    return None


def _set_cache(cache_key: str, data: Any, ttl_seconds: int = None):
    """Set value in cache with TTL"""
    ttl = ttl_seconds or _cache_ttl_seconds
    _cache[cache_key] = {
        "data": data,
        "expires_at": datetime.utcnow() + timedelta(seconds=ttl),
        "cached_at": datetime.utcnow(),
    }


def clear_cache(cache_key: Optional[str] = None):
    """Clear cache (all or specific key)"""
    if cache_key:
        _cache.pop(cache_key, None)
    else:
        _cache.clear()


class PGRulesClient:
    """Client for fetching and caching PostgreSQL rules"""
    
    @staticmethod
    def get_merchant_rules(
        user_id: Optional[str] = None,
        tenant_id: Optional[str] = None,
        use_cache: bool = True
    ) -> List[Dict[str, Any]]:
        """
        Get merchant rules from PostgreSQL (cached), filtered by tenant.
        
        Args:
            user_id: Optional user ID (currently not used for filtering, but kept for API compatibility)
            tenant_id: Optional tenant ID for multi-tenant isolation (NULL rules are global)
            use_cache: Whether to use cache (default True)
        
        Returns:
            List of merchant rule dictionaries (global rules + tenant-specific rules)
        """
        cache_key = f"merchant_rules:{tenant_id or 'global'}"
        
        if use_cache:
            cached = _get_from_cache(cache_key)
            if cached is not None:
                return cached
        
        session = SessionLocal()
        try:
            import uuid as _uuid
            tenant_uuid = _uuid.UUID(tenant_id) if tenant_id and isinstance(tenant_id, str) else tenant_id
            
            # Get rules: global (tenant_id IS NULL) + tenant-specific
            query = session.query(MerchantRule).filter(MerchantRule.active == True)
            
            if tenant_id:
                # Return global rules (NULL tenant) + this tenant's rules
                from sqlalchemy import or_
                query = query.filter(
                    or_(
                        MerchantRule.tenant_id == tenant_uuid,
                        MerchantRule.tenant_id.is_(None)
                    )
                )
            else:
                # Only global rules if no tenant specified
                query = query.filter(MerchantRule.tenant_id.is_(None))
            
            # Order by priority (ascending = lower number wins), then by created_at (newer wins on same priority)
            rules = query.order_by(MerchantRule.priority.asc(), MerchantRule.created_at.desc()).all()
            
            result = [
                {
                    "rule_id": str(rule.rule_id),
                    "user_id": str(rule.created_by) if rule.created_by else None,
                    "tenant_id": str(rule.tenant_id) if rule.tenant_id else None,
                    "applies_to": rule.applies_to,  # 'merchant' or 'description'
                    "pattern_regex": rule.pattern_regex,  # The regex pattern to match
                    "pattern_hash": rule.pattern_hash,  # SHA1 hash for deduplication
                    "merchant_name_norm": None,  # Not used, but kept for compatibility
                    "category_code": rule.category_code,
                    "subcategory_code": rule.subcategory_code,
                    "source": rule.source,  # 'learned' | 'seed' | 'ops'
                    "confidence": 0.95 if rule.source == 'learned' else 0.85,  # Learned rules have higher confidence
                    "active": rule.active,
                    "priority": rule.priority,
                    "created_at": rule.created_at.isoformat() if rule.created_at else None,
                }
                for rule in rules
            ]
            
            if use_cache:
                _set_cache(cache_key, result)
            
            return result
            
        finally:
            session.close()
    
    @staticmethod
    def match_merchant(
        merchant_name: Optional[str],
        description: Optional[str] = None,
        user_id: Optional[str] = None,
        tenant_id: Optional[str] = None,
        use_cache: bool = True,
    ) -> Optional[Dict[str, Any]]:
        """
        Match merchant name and/or description against merchant rules.
        Falls back to fuzzy matching if no regex match is found.
        
        Args:
            merchant_name: Merchant name to match
            description: Optional description to match (for applies_to='description' rules)
            user_id: Optional user ID (for user-specific rules)
            use_cache: Whether to use cache
        
        Returns:
            Matching rule dictionary or None
        """
        # Get all active merchant rules (tenant-aware)
        rules = PGRulesClient.get_merchant_rules(user_id=None, tenant_id=tenant_id, use_cache=use_cache)
        
        # Rules are already sorted by priority ASC, created_at DESC from query
        # No need to sort again as query already handles this
        
        # Match against patterns (regex)
        for rule in rules:
            pattern = rule.get("pattern_regex")
            if not pattern:
                continue
            
            applies_to = rule.get("applies_to", "merchant")
            matched_text = None
            
            try:
                # Match against merchant if applies_to='merchant'
                if applies_to == "merchant" and merchant_name:
                    match = re.search(pattern, merchant_name, re.IGNORECASE)
                    if match:
                        matched_text = match.group(0) if match.groups() else merchant_name
                        rule["matched_text"] = matched_text
                        rule["applies_to"] = applies_to
                        return rule
                
                # Match against description if applies_to='description'
                if applies_to == "description" and description:
                    match = re.search(pattern, description, re.IGNORECASE)
                    if match:
                        matched_text = match.group(0) if match.groups() else description[:50]  # First 50 chars
                        rule["matched_text"] = matched_text
                        rule["applies_to"] = applies_to
                        return rule
                
            except re.error:
                # Invalid regex pattern, skip
                continue
        
        # Fallback: Fuzzy matching if no regex match found
        # Only try fuzzy matching for merchant_name (not description, too noisy)
        if merchant_name:
            best_match = PGRulesClient._fuzzy_match_merchant(merchant_name, rules)
            if best_match:
                return best_match
        
        return None
    
    @staticmethod
    def _fuzzy_match_merchant(merchant_name: str, rules: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        """
        Fuzzy match merchant name against rules using string similarity.
        Only matches rules that apply to 'merchant' and have a pattern_text.
        
        Args:
            merchant_name: Normalized merchant name to match
            rules: List of rule dictionaries
        
        Returns:
            Best matching rule if similarity > 0.75, else None
        """
        from difflib import SequenceMatcher
        
        merchant_upper = merchant_name.upper().strip()
        best_match = None
        best_score = 0.75  # Minimum threshold
        
        for rule in rules:
            # Only fuzzy match rules that apply to merchant
            if rule.get("applies_to") != "merchant":
                continue
            
            # Extract pattern text from regex (remove regex syntax for comparison)
            pattern_regex = rule.get("pattern_regex", "")
            if not pattern_regex:
                continue
            
            # Try to extract meaningful text from regex pattern
            # Remove common regex syntax: (?i), .*, \b, etc.
            pattern_text = pattern_regex
            pattern_text = re.sub(r'^\(\?i\)', '', pattern_text, flags=re.IGNORECASE)
            pattern_text = re.sub(r'\\b', '', pattern_text)
            pattern_text = re.sub(r'\.\*', '', pattern_text)
            pattern_text = re.sub(r'[.*+?^${}()|[\]\\]', '', pattern_text)  # Remove regex special chars
            pattern_text = pattern_text.upper().strip()
            
            if not pattern_text or len(pattern_text) < 3:
                continue
            
            # Calculate similarity
            similarity = SequenceMatcher(None, merchant_upper, pattern_text).ratio()
            
            # Also try matching against key words in pattern
            # If merchant contains significant portion of pattern words, boost score
            pattern_words = set(pattern_text.split())
            merchant_words = set(merchant_upper.split())
            if pattern_words and merchant_words:
                word_overlap = len(pattern_words.intersection(merchant_words)) / len(pattern_words.union(merchant_words))
                # Boost similarity if word overlap is high
                similarity = max(similarity, word_overlap * 0.9)
            
            if similarity > best_score:
                best_score = similarity
                best_match = rule.copy()
                best_match["matched_text"] = merchant_name
                best_match["fuzzy_score"] = similarity
                best_match["applies_to"] = "merchant"
        
        return best_match
    
    @staticmethod
    def get_parser_rules(bank: Optional[str] = None, use_cache: bool = True) -> List[Dict[str, Any]]:
        """
        Get parser rules from PostgreSQL (cached)
        
        Note: This assumes you have a parser_rules table. If not, return empty list.
        
        Args:
            bank: Optional bank filter
            use_cache: Whether to use cache
        
        Returns:
            List of parser rule dictionaries
        """
        cache_key = f"parser_rules:{bank or 'all'}"
        
        if use_cache:
            cached = _get_from_cache(cache_key)
            if cached is not None:
                return cached
        
        session = SessionLocal()
        try:
            # Check if parser_rules table exists
            result = session.execute(text("""
                SELECT EXISTS (
                    SELECT 1 FROM information_schema.tables
                    WHERE table_schema = 'spendsense'
                    AND table_name = 'parser_rules'
                )
            """))
            
            if not result.scalar():
                # Table doesn't exist yet, return empty list
                return []
            
            # Fetch parser rules
            query = text("""
                SELECT rule_id, bank, pattern, extract_fn, priority, active
                FROM spendsense.parser_rules
                WHERE active = TRUE
                AND (:bank IS NULL OR bank = :bank OR bank = 'ANY')
                ORDER BY priority DESC
            """)
            
            rows = session.execute(query, {"bank": bank}).fetchall()
            
            result = [
                {
                    "rule_id": str(row.rule_id),
                    "bank": row.bank,
                    "pattern": row.pattern,
                    "extract_fn": row.extract_fn,
                    "priority": row.priority or 0,
                    "active": row.active,
                }
                for row in rows
            ]
            
            if use_cache:
                _set_cache(cache_key, result)
            
            return result
            
        finally:
            session.close()
    
    @staticmethod
    def call_parse_txn_line(
        line_text: str,
        bank: str = "ANY",
        channel: str = "any",
    ) -> Optional[Dict[str, Any]]:
        """
        Call PostgreSQL function fn_parse_txn_line if it exists
        
        Args:
            line_text: Transaction line text to parse
            bank: Bank identifier
            channel: Channel type ("sms", "email", "pdf", etc.)
        
        Returns:
            Parsed transaction dictionary or None
        """
        session = SessionLocal()
        try:
            # Check if function exists
            result = session.execute(text("""
                SELECT EXISTS (
                    SELECT 1 FROM pg_proc p
                    JOIN pg_namespace n ON p.pronamespace = n.oid
                    WHERE n.nspname = 'spendsense'
                    AND p.proname = 'fn_parse_txn_line'
                )
            """))
            
            if not result.scalar():
                # Function doesn't exist yet
                return None
            
            # Call function
            query = text("""
                SELECT spendsense.fn_parse_txn_line(:line_text, :bank, :channel) as parsed
            """)
            
            result = session.execute(query, {
                "line_text": line_text,
                "bank": bank,
                "channel": channel,
            }).fetchone()
            
            if result and result.parsed:
                import json
                return json.loads(result.parsed) if isinstance(result.parsed, str) else result.parsed
            
            return None
            
        finally:
            session.close()

