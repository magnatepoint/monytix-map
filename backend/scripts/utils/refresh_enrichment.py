#!/usr/bin/env python3
"""
Re-enrichment script with normalization + fuzzy fallback
Normalizes merchant names, tries regex rules first, falls back to fuzzy matching
"""

import argparse
import re
import sys
import uuid
from pathlib import Path
from difflib import SequenceMatcher
from typing import Optional, Iterable, Tuple, Dict

sys.path.insert(0, str(Path(__file__).parent.parent))

from app.database.postgresql import SessionLocal
from app.models.spendsense_models import TxnFact, TxnEnriched, MerchantRule
from sqlalchemy import and_
from sqlalchemy.orm import Session

# ---------- Normalization ----------
MERCHANT_KEEP = re.compile(r'[^A-Z0-9\s]+')

def normalize_merchant(name: Optional[str]) -> Optional[str]:
    """Normalize merchant name for matching (uppercase, strip punctuation)"""
    if not name:
        return None
    s = name.upper().strip()
    s = MERCHANT_KEEP.sub('', s)  # Remove punctuation
    s = re.sub(r'\s+', ' ', s)   # Normalize spaces
    return s.strip()

# ---------- Fuzzy ----------
def fuzzy_ratio(a: str, b: str) -> float:
    """Calculate string similarity ratio"""
    return SequenceMatcher(None, a, b).ratio()

# ---------- Core matching ----------
def fetch_rules(session: Session) -> Iterable[MerchantRule]:
    """Fetch all active merchant rules ordered by priority"""
    return session.query(MerchantRule).filter(MerchantRule.active == True)\
           .order_by(MerchantRule.priority.asc()).all()

def match_rule(merchant: Optional[str], description: Optional[str], direction: Optional[str], rules: Iterable[MerchantRule]) -> Optional[Dict]:
    """
    Match merchant/description against rules.
    First tries regex matching, then falls back to fuzzy matching.
    Also handles special cases: credits with company names → salary, hotels → travel
    """
    m_norm = normalize_merchant(merchant) or ''
    d_text = (description or '').upper()
    
    # 1) regex pass (best effort, ordered by priority)
    for r in rules:
        if not r.pattern_regex:
            continue
        
        try:
            pat = re.compile(r.pattern_regex, re.IGNORECASE)
            hay = m_norm if r.applies_to == 'merchant' else d_text
            
            if hay and pat.search(hay):
                return {
                    "rule_id": str(r.rule_id),
                    "category_code": r.category_code,
                    "subcategory_code": r.subcategory_code,
                    "applies_to": r.applies_to,
                    "confidence": 0.92,
                    "matched_text": hay[:120]
                }
        except re.error:
            # Invalid regex pattern, skip
            continue
    
    # Special case: Credits should NEVER be shopping/mobile_recharge/etc
    if direction == 'credit':
        # Priority 1: Check if it's a personal name (2-4 words, no business keywords)
        search_text = (merchant or description or "").lower()
        words = search_text.split()
        is_personal_name = (len(words) >= 2 and len(words) <= 4 and 
                           not any(word in search_text for word in ["enterprises", "services", "solutions", "technologies", "private", "limited", "hotel", "hotels", "resort", "lodge", "industries", "trading", "traders", "store", "shop", "pvt", "ltd", "inc", "corp", "corporation"]))
        
        # Common Indian personal names (including names from the images)
        common_names = ["abhinav", "shobha", "vasantha", "vasanthakumari", "yashwanth", "yashwant", "sriram", "kumari", "kiran", "uday", "navalga", "jatavath", "shaik", "zuber", "mohammad", "mohammed", "sameer", "shakeel", "arifa", "begum", "gurajala", "josaf", "pathlavath", "ramesh", "pittala", "yadagiri", "ippalui", "krishnaiah", "sandeep", "venkata", "hanuman", "naseer", "malla", "satya", "srinivasa", "ravi", "sri", "sai", "teja", "industr", "kiran", "kumarkvkn"]
        
        if is_personal_name or any(name in search_text for name in common_names):
            # Personal name → transfers
            transfer_rule = next((r for r in rules if r.category_code == 'transfers' and r.subcategory_code == 'p2p_transfer'), None)
            return {
                "rule_id": str(transfer_rule.rule_id) if transfer_rule else None,
                "category_code": "transfers",
                "subcategory_code": "p2p_transfer",
                "applies_to": "merchant",
                "confidence": 0.88,
                "matched_text": m_norm
            }
        
        # Priority 2: Check if merchant name looks like a company
        merchant_lower = m_norm.lower()
        company_keywords = ["technologies", "technology", "private", "limited", "pvt", "ltd", "inc", "corporation", "corp", "industries", "clearing", "nse", "bse", "nsec"]
        if any(keyword in merchant_lower for keyword in company_keywords):
            # Find a salary_income rule to use as template
            salary_rule = next((r for r in rules if r.category_code == 'salary_income'), None)
            if salary_rule:
                return {
                    "rule_id": str(salary_rule.rule_id) if salary_rule else None,
                    "category_code": "salary_income",
                    "subcategory_code": "salary",
                    "applies_to": "merchant",
                    "confidence": 0.88,
                    "matched_text": m_norm
                }
        
        # Priority 3: Check if it contains business keywords (but not personal name)
        business_keywords = ["enterprises", "services", "solutions", "traders", "store", "shop"]
        if any(word in merchant_lower for word in business_keywords):
            # Small business → transfers
            transfer_rule = next((r for r in rules if r.category_code == 'transfers' and r.subcategory_code == 'p2p_transfer'), None)
            return {
                "rule_id": str(transfer_rule.rule_id) if transfer_rule else None,
                "category_code": "transfers",
                "subcategory_code": "p2p_transfer",
                "applies_to": "merchant",
                "confidence": 0.85,
                "matched_text": m_norm
            }
        
        # Default: credits from unknown sources → transfers (not salary_income)
        transfer_rule = next((r for r in rules if r.category_code == 'transfers' and r.subcategory_code == 'p2p_transfer'), None)
        return {
            "rule_id": str(transfer_rule.rule_id) if transfer_rule else None,
            "category_code": "transfers",
            "subcategory_code": "p2p_transfer",
            "applies_to": "merchant",
            "confidence": 0.80,
            "matched_text": m_norm
        }
    
    # Special case: Credit card apps → loans_emi
    if direction == 'debit':
        text_lower = (merchant or description or "").lower()
        if any(k in text_lower for k in ["cred", "american express", "amex", "credit card", "cc payment", "card payment"]):
            # Find a credit card rule to use as template
            cc_rule = next((r for r in rules if r.category_code == 'loans_emi' and r.subcategory_code == 'credit_card_bill'), None)
            if cc_rule:
                return {
                    "rule_id": str(cc_rule.rule_id) if cc_rule else None,
                    "category_code": "loans_emi",
                    "subcategory_code": "credit_card_bill",
                    "applies_to": "merchant",
                    "confidence": 0.88,
                    "matched_text": m_norm
                }
    
    # Special case: Personal names → transfers (check before hotels)
    if direction == 'debit':
        merchant_lower = m_norm.lower()
        text_lower = (merchant or description or "").lower()
        words = text_lower.split()
        is_personal_name = (len(words) >= 2 and len(words) <= 4 and 
                           not any(word in text_lower for word in ["enterprises", "services", "solutions", "technologies", "private", "limited", "hotel", "hotels", "resort", "lodge"]))
        
        if is_personal_name:
            # Check common Indian names
            common_names = ["abhinav", "shobha", "vasantha", "vasanthakumari", "yashwanth", "yashwant", "sriram", "kumari", "kiran", "uday", "navalga", "jatavath", "shaik", "zuber", "mohammad", "mohammed", "sameer", "shakeel", "arifa", "begum", "gurajala", "josaf", "pathlavath", "ramesh", "pittala", "yadagiri", "ippalui", "krishnaiah", "sandeep", "venkata", "hanuman", "naseer", "malla"]
            if any(name in text_lower for name in common_names):
                # Find a transfers rule to use as template
                transfer_rule = next((r for r in rules if r.category_code == 'transfers' and r.subcategory_code == 'p2p_transfer'), None)
                if transfer_rule:
                    return {
                        "rule_id": str(transfer_rule.rule_id) if transfer_rule else None,
                        "category_code": "transfers",
                        "subcategory_code": "p2p_transfer",
                        "applies_to": "merchant",
                        "confidence": 0.88,
                        "matched_text": m_norm
                    }
    
    # Special case: Hotels → travel (only if not a personal name)
    if direction == 'debit':
        merchant_lower = m_norm.lower()
        text_lower = (merchant or description or "").lower()
        words = text_lower.split()
        is_personal_name = (len(words) >= 2 and len(words) <= 4 and 
                           not any(word in text_lower for word in ["enterprises", "services", "solutions", "technologies", "private", "limited", "hotel", "hotels", "resort", "lodge"]))
        
        if not is_personal_name and any(k in text_lower for k in ["hotel", "hotels", "resort", "lodge", "inn", "accommodation", "taj", "oberoi", "itc", "hilton", "marriott", "hyatt", "oyo", "booking", "stay"]):
            # Find a travel/hotels rule to use as template
            hotel_rule = next((r for r in rules if r.category_code == 'travel' and r.subcategory_code == 'hotels'), None)
            if hotel_rule:
                return {
                    "rule_id": str(hotel_rule.rule_id) if hotel_rule else None,
                    "category_code": "travel",
                    "subcategory_code": "hotels",
                    "applies_to": "merchant",
                    "confidence": 0.88,
                    "matched_text": m_norm
                }
    
    # 2) fuzzy fallback on merchant vs simple pattern_text from regex (very naive)
    # Extract a token string from regex like (?i)\bAMAZON\b -> AMAZON
    candidates: list[Tuple[float, MerchantRule]] = []
    
    for r in rules:
        if not r.pattern_regex or r.applies_to != 'merchant' or not m_norm:
            continue
        
        # naive token extraction
        token = re.sub(r'[\W_]+', ' ', r.pattern_regex, flags=re.I).strip()
        if not token:
            continue
        
        score = fuzzy_ratio(m_norm, token.upper())
        if score >= 0.78:
            candidates.append((score, r))
    
    if candidates:
        candidates.sort(key=lambda x: (-x[0], x[1].priority))
        r = candidates[0][1]
        return {
            "rule_id": str(r.rule_id),
            "category_code": r.category_code,
            "subcategory_code": r.subcategory_code,
            "applies_to": r.applies_to,
            "confidence": float(candidates[0][0]),
            "matched_text": m_norm
        }
    
    return None

def upsert_enriched(session: Session, txn_id: uuid.UUID, match: Dict):
    """Update or insert enriched record"""
    existing = session.query(TxnEnriched).filter(TxnEnriched.txn_id == txn_id).first()
    
    if existing:
        existing.category_code = match.get("category_code")
        existing.subcategory_code = match.get("subcategory_code")
        existing.matched_rule_id = uuid.UUID(match["rule_id"]) if match.get("rule_id") else None
        existing.rule_confidence = match.get("confidence", 0.85)
    else:
        session.add(TxnEnriched(
            txn_id=txn_id,
            matched_rule_id=uuid.UUID(match["rule_id"]) if match.get("rule_id") else None,
            category_code=match.get("category_code"),
            subcategory_code=match.get("subcategory_code"),
            rule_confidence=match.get("confidence", 0.85)
        ))

def process_user(session: Session, user_id: uuid.UUID) -> Tuple[int, int]:
    """Process all transactions for a user"""
    rules = list(fetch_rules(session))
    updated = 0
    total = 0
    
    # Get all transactions for this user
    txns = session.query(TxnFact).filter(TxnFact.user_id == user_id).all()
    
    for txn in txns:
        total += 1
        m = match_rule(txn.merchant_name_norm, txn.description, txn.direction, rules)
        
        if not m:
            # Fallback: Credits default to transfers (not salary_income)
            if txn.direction == 'credit':
                transfer_rule = next((r for r in rules if r.category_code == 'transfers' and r.subcategory_code == 'p2p_transfer'), None)
                m = {
                    "rule_id": str(transfer_rule.rule_id) if transfer_rule else None,
                    "category_code": "transfers",
                    "subcategory_code": "p2p_transfer",
                    "applies_to": "merchant",
                    "confidence": 0.80,
                    "matched_text": normalize_merchant(txn.merchant_name_norm) or ""
                }
            if not m:
                continue
        
        upsert_enriched(session, txn.txn_id, m)
        updated += 1
        
        # Commit every 100 transactions to avoid long transactions
        if updated % 100 == 0:
            session.commit()
            print(f"✅ Updated {updated} transactions...")
    
    session.commit()
    return total, updated

def main():
    ap = argparse.ArgumentParser(description='Re-enrich transactions with normalization + fuzzy fallback')
    ap.add_argument('--user', help='User UUID (optional). If omitted, processes all users.')
    args = ap.parse_args()
    
    session = SessionLocal()
    try:
        if args.user:
            uid = uuid.UUID(args.user)
            total, updated = process_user(session, uid)
            print(f"[OK] User {uid}: scanned={total}, enriched/updated={updated}")
        else:
            users = [r[0] for r in session.query(TxnFact.user_id).distinct().all()]
            grand_total = grand_upd = 0
            
            for uid in users:
                total, updated = process_user(session, uid)
                grand_total += total
                grand_upd += updated
                print(f"[OK] User {uid}: scanned={total}, enriched/updated={updated}")
            
            print(f"[DONE] All users: scanned={grand_total}, enriched/updated={grand_upd}")
    except Exception as e:
        import traceback
        print(f"❌ Error: {e}")
        traceback.print_exc()
        session.rollback()
        return 1
    finally:
        session.close()
    
    return 0

if __name__ == '__main__':
    sys.exit(main())

