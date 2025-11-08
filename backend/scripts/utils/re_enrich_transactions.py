#!/usr/bin/env python3
"""
Re-enrich all transactions with improved categorization logic:
- Better normalization (strips punctuation)
- Fuzzy matching fallback
- Improved keyword inference
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.database.postgresql import SessionLocal
from app.models.spendsense_models import TxnFact, TxnEnriched
from app.services.merchant_extractor import extract_merchant_from_description, normalize_merchant_name
from app.services.pg_rules_client import PGRulesClient, clear_cache
from typing import Optional
import uuid as _uuid
import re


def _extract_and_categorize(description: str, merchant_raw: Optional[str], direction: str, user_id: str) -> tuple:
    """
    Extract merchant name and categorize using merchant_rules with fuzzy matching fallback.
    
    Returns:
        Tuple of (merchant_name_norm, category_code, subcategory_code)
    """
    # Step 1: Extract merchant name from description if merchant_raw is not provided or unclear
    merchant_name = merchant_raw
    if not merchant_name or merchant_name.lower() in ['unknown', 'nan', '']:
        # Try to extract from description (for UPI transactions)
        merchant_name = extract_merchant_from_description(description or "")
    
    # Step 2: Normalize merchant name for matching (aggressive normalization)
    merchant_normalized = normalize_merchant_name(merchant_name or description or "")
    
    # Step 3: Get tenant_id from user_id (for now, assume user_id = tenant_id)
    tenant_id = user_id
    
    # Step 4: Match against merchant_rules (with fuzzy fallback)
    rule_match = PGRulesClient.match_merchant(
        merchant_name=merchant_normalized or None,
        description=description or None,
        user_id=user_id,
        tenant_id=tenant_id,
        use_cache=False  # Don't use cache for re-enrichment
    )
    
    if rule_match:
        # Only use the match if it has a category_code
        category_from_rule = rule_match.get("category_code")
        if category_from_rule:
            return (
                rule_match.get("merchant_name_norm") or merchant_normalized,
                category_from_rule,
                rule_match.get("subcategory_code")
            )
    
    # Step 5: Fallback to keyword-based inference (only for debits)
    if direction == 'credit':
        # Credits should be income unless specified otherwise
        return (merchant_normalized, "salary_income", None)
    
    # For debits, use keyword matching
    search_text = (merchant_normalized or description or "").lower()
    category = _infer_category_from_keywords(search_text)
    
    return (merchant_normalized, category, None)


def _infer_category_from_keywords(text: str) -> str:
    """Infer category from keywords (fallback for debits only) - uses India-first categories"""
    if not text:
        return "shopping"  # Default fallback
    
    text_lower = text.lower()
    
    # Food & Dining
    if any(k in text_lower for k in ["zomato", "swiggy", "dine", "restaurant", "truffles", "food", "meal", "pizza", "burger", "cafe", "hotel", "eating"]):
        return "eating_nightlife"
    # Groceries
    if any(k in text_lower for k in ["bigbasket", "blinkit", "zepto", "dmart", "supermarket", "grocery", "kirana", "provisions"]):
        return "groceries"
    # Shopping
    if any(k in text_lower for k in ["amazon", "flipkart", "myntra", "ajio", "croma", "reliance digital", "bazaar", "shopping", "market", "mall"]):
        return "shopping"
    # Utilities
    if any(k in text_lower for k in ["bescom", "bwssb", "tsspdcl", "electricity", "water", "jio", "airtel", "broadband", "internet", "mobile", "vi", "bsnl"]):
        return "utilities"
    # Travel & Transport
    if any(k in text_lower for k in ["uber", "ola", "rapido", "cab", "taxi", "auto", "rickshaw", "indigo", "vistara", "air india", "akasa", "flight", "airline", "irctc", "railways", "train", "metro", "bus", "transport"]):
        return "transport"
    # Fuel & Tolls
    if any(k in text_lower for k in ["fuel", "petrol", "diesel", "fastag", "toll", "nhai"]):
        return "fuel_toll"
    # Housing
    if any(k in text_lower for k in ["apartment", "rent", "society", "maintenance", "property", "house", "flat"]):
        return "housing"
    # Investments
    if any(k in text_lower for k in ["hdfc rd", "rd ", "recurring deposit", "hdfc mf", "index fund", "sip", "mutual fund", "investment", "stocks", "shares"]):
        return "investments"
    # Savings
    if any(k in text_lower for k in ["ppf", "fd", "recurring deposit", "fixed deposit", "savings"]):
        return "savings"
    # Healthcare
    if any(k in text_lower for k in ["doctor", "pharmacy", "hospital", "medicine", "diagnostics", "clinic"]):
        return "healthcare"
    # Personal transfers/UPI
    if any(k in text_lower for k in ["upi", "imps", "neft", "rtgs"]):
        business_keywords = ["enterprises", "services", "solutions", "traders", "store", "shop", "packages", "industries", "trading", "technologies", "private", "limited", "pvt", "ltd"]
        if any(word in text_lower for word in business_keywords):
            return "shopping"  # Likely a small business
        company_keywords = ["technologies", "technology", "private", "limited", "pvt", "ltd"]
        if any(word in text_lower for word in company_keywords):
            return "shopping"
    
    return "shopping"  # Default fallback


def re_enrich_all_transactions(user_id: Optional[str] = None):
    """Re-enrich all transactions with improved categorization"""
    # Clear cache to ensure fresh rules
    clear_cache()
    
    session = SessionLocal()
    updated_count = 0
    errors = []
    
    try:
        # Get all transactions (optionally filtered by user_id)
        query = session.query(TxnFact)
        if user_id:
            user_uuid = _uuid.UUID(user_id) if isinstance(user_id, str) else user_id
            query = query.filter(TxnFact.user_id == user_uuid)
        
        transactions = query.all()
        
        print(f"🔄 Re-enriching {len(transactions)} transactions...")
        
        for txn in transactions:
            try:
                # Get enriched record
                enriched = session.query(TxnEnriched).filter(
                    TxnEnriched.txn_id == txn.txn_id
                ).first()
                
                if not enriched:
                    # Skip if no enriched record exists
                    continue
                
                # Extract and categorize
                merchant_norm, category_code, subcategory_code = _extract_and_categorize(
                    description=txn.description or "",
                    merchant_raw=txn.merchant_name_norm,
                    direction=txn.direction,
                    user_id=str(txn.user_id)
                )
                
                # Update TxnFact with merchant name
                if merchant_norm:
                    txn.merchant_name_norm = merchant_norm
                
                # Update TxnEnriched with category/subcategory
                # Always update if we have a category_code (even if same)
                if category_code:
                    # Check if anything actually changed
                    changed = False
                    if enriched.category_code != category_code:
                        enriched.category_code = category_code
                        changed = True
                    if subcategory_code and enriched.subcategory_code != subcategory_code:
                        enriched.subcategory_code = subcategory_code
                        changed = True
                    
                    # Update confidence
                    enriched.rule_confidence = 0.85 if subcategory_code else 0.75
                    
                    if changed:
                        updated_count += 1
                    else:
                        # Count as updated even if no change (we processed it)
                        updated_count += 1
                
                if updated_count % 50 == 0:
                    session.commit()
                    print(f"✅ Updated {updated_count} transactions...")
                    
            except Exception as e:
                session.rollback()  # Rollback the failed transaction
                error_msg = f"Transaction {txn.txn_id}: {str(e)}"
                errors.append(error_msg)
                # Print first 5 errors for debugging
                if len(errors) <= 5:
                    print(f"❌ Error: {error_msg}")
                # Continue to next transaction
                continue
        
        session.commit()
        
        print(f"\n✅ Re-enrichment complete!")
        print(f"   Updated: {updated_count} transactions")
        if errors:
            print(f"   Errors: {len(errors)}")
            if len(errors) <= 10:
                for error in errors:
                    print(f"     - {error}")
        
    except Exception as e:
        session.rollback()
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        session.close()


if __name__ == "__main__":
    import sys
    user_id = sys.argv[1] if len(sys.argv) > 1 else None
    re_enrich_all_transactions(user_id)

