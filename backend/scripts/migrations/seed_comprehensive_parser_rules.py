#!/usr/bin/env python3
"""
Seed comprehensive parser rules for full-spectrum financial ingestor
Covers: UPI, wallets, credit/debit cards, IMPS/NEFT/RTGS, ATM, charges, salary, loans, MFs, bills
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.database.postgresql import SessionLocal
from sqlalchemy import text
import json

RULES = [
    # UPI & Wallets
    {"bank": "ANY", "channel": "email", "priority": 10, "pattern": r'(?:UPI|VPA).{0,50}?(?:debited|paid|payment|spent).{0,30}?(?:Rs\.?|₹|INR)\s*([\d,]+\.?\d*).{0,50}?(?:to|at)\s+([A-Za-z0-9._\- ]+)', "groups": {"amount_str": 1, "merchant": 2, "dc": "debit"}},
    {"bank": "ANY", "channel": "email", "priority": 12, "pattern": r'(?:UPI|VPA).{0,50}?(?:received|credited).{0,30}?(?:Rs\.?|₹|INR)\s*([\d,]+\.?\d*)\s+from\s+([A-Za-z0-9._\- ]+)', "groups": {"amount_str": 1, "merchant": 2, "dc": "credit"}},
    {"bank": "ANY", "channel": "email", "priority": 8, "pattern": r'Google\s+Pay.*?(?:paid|payment).{0,20}(?:Rs\.?|₹|INR)\s*([\d,]+\.?\d*).{0,40}?(?:to|at)\s+([A-Za-z0-9 .&_\'\-]+)', "groups": {"amount_str": 1, "merchant": 2, "dc": "debit", "source": "gpay"}},
    {"bank": "ANY", "channel": "email", "priority": 8, "pattern": r'PhonePe.*?(?:paid|payment|debit).{0,20}(?:Rs\.?|₹|INR)\s*([\d,]+\.?\d*).{0,40}?(?:to|at)\s+([A-Za-z0-9 .&_\'\-]+)', "groups": {"amount_str": 1, "merchant": 2, "dc": "debit", "source": "phonepe"}},
    {"bank": "ANY", "channel": "email", "priority": 8, "pattern": r'Paytm.*?(?:paid|payment|spent).{0,20}(?:Rs\.?|₹|INR)\s*([\d,]+\.?\d*).{0,40}?(?:to|at)\s+([A-Za-z0-9 .&_\'\-]+)', "groups": {"amount_str": 1, "merchant": 2, "dc": "debit", "source": "paytm"}},
    
    # Credit/Debit Cards
    {"bank": "ANY", "channel": "email", "priority": 15, "pattern": r'(?:spent|purchase|payment|debited).{0,10}(?:of\s*)?(?:Rs\.?|₹|INR)\s*([\d,]+\.?\d*)\s+(?:at|towards)\s+([A-Za-z0-9&.\- ]+)', "groups": {"amount_str": 1, "merchant": 2, "dc": "debit"}},
    {"bank": "HDFC", "channel": "email", "priority": 14, "pattern": r'Rs\.?\s*([\d,]+\.?\d*)\s+(?:is|has been)\s+debited.*?Credit\s+Card(?:\s+ending\s+(\d{3,4}))?.*?(?:towards|at)\s+([A-Za-z0-9&.\- ]+)', "groups": {"amount_str": 1, "account_hint": 2, "merchant": 3, "dc": "debit"}},
    {"bank": "ICICI", "channel": "email", "priority": 14, "pattern": r'(?:Transaction of|spent).{0,10}(?:Rs\.?|₹|INR)\s*([\d,]+\.?\d*).{0,30}(?:at|towards)\s+([A-Za-z0-9&.\- ]+)', "groups": {"amount_str": 1, "merchant": 2, "dc": "debit"}},
    
    # IMPS/NEFT/RTGS
    {"bank": "ANY", "channel": "email", "priority": 20, "pattern": r'(IMPS|NEFT|RTGS).{0,30}(?:debit|paid|transferred).{0,20}(?:Rs\.?|₹|INR)\s*([\d,]+\.?\d*)\s+(?:to|beneficiary)\s+([A-Za-z0-9 .&_\'\-]+)', "groups": {"method": 1, "amount_str": 2, "merchant": 3, "dc": "debit"}},
    {"bank": "ANY", "channel": "email", "priority": 21, "pattern": r'(IMPS|NEFT|RTGS).{0,30}(?:credit|received).{0,20}(?:Rs\.?|₹|INR)\s*([\d,]+\.?\d*)\s+from\s+([A-Za-z0-9 .&_\'\-]+)', "groups": {"method": 1, "amount_str": 2, "merchant": 3, "dc": "credit"}},
    
    # ATM
    {"bank": "ANY", "channel": "email", "priority": 30, "pattern": r'ATM\s+(?:cash\s+)?withdrawal.*?(?:Rs\.?|₹|INR)\s*([\d,]+\.?\d*)', "groups": {"amount_str": 1, "merchant": "ATM Withdrawal", "dc": "debit"}},
    
    # Bank charges / Interest / Salary
    {"bank": "ANY", "channel": "email", "priority": 40, "pattern": r'(?:charges?|fee|penalty).{0,20}(?:Rs\.?|₹|INR)\s*([\d,]+\.?\d*)', "groups": {"amount_str": 1, "merchant": "Bank Charges", "dc": "debit", "category_hint": "banks"}},
    {"bank": "ANY", "channel": "email", "priority": 40, "pattern": r'(?:interest\s+credited|interest\s+payment).*?(?:Rs\.?|₹|INR)\s*([\d,]+\.?\d*)', "groups": {"amount_str": 1, "merchant": "Interest", "dc": "credit", "category_hint": "banks"}},
    {"bank": "ANY", "channel": "email", "priority": 35, "pattern": r'(?:salary|payroll|salary\s+credited).*?(?:Rs\.?|₹|INR)\s*([\d,]+\.?\d*)\s+from\s+([A-Za-z0-9 .&_\'\-]+)', "groups": {"amount_str": 1, "merchant": 2, "dc": "credit", "category_hint": "income"}},
    
    # Loans
    {"bank": "ANY", "channel": "email", "priority": 25, "pattern": r'(?:EMI|loan).*?(?:due|payable).{0,20}(?:Rs\.?|₹|INR)\s*([\d,]+\.?\d*).{0,40}?(?:due\s*on|by)\s*(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})', "groups": {"amount_str": 1, "date_str": 2, "merchant": "Loan EMI Due", "dc": "debit", "category_hint": "loans"}},
    {"bank": "ANY", "channel": "email", "priority": 26, "pattern": r'(?:EMI|loan).{0,20}(?:paid|debited).{0,20}(?:Rs\.?|₹|INR)\s*([\d,]+\.?\d*)', "groups": {"amount_str": 1, "merchant": "Loan EMI", "dc": "debit", "category_hint": "loans"}},
    
    # Mutual Funds
    {"bank": "ANY", "channel": "email", "priority": 18, "pattern": r'(?:SIP|mutual\s+fund).{0,25}(?:debit|paid|contribution).{0,25}(?:Rs\.?|₹|INR)\s*([\d,]+\.?\d*)', "groups": {"amount_str": 1, "merchant": "Mutual Fund SIP", "dc": "debit", "category_hint": "investments"}},
    {"bank": "ANY", "channel": "email", "priority": 19, "pattern": r'(?:purchase|order\s+executed|units\s+allotted).{0,30}(?:Rs\.?|₹|INR)\s*([\d,]+\.?\d*)\s+(?:in|for)\s+([A-Za-z0-9&(). \-]+)', "groups": {"amount_str": 1, "merchant": 2, "dc": "debit", "category_hint": "investments"}},
    
    # Bills
    {"bank": "ANY", "channel": "email", "priority": 22, "pattern": r'(?:bill|invoice).{0,30}(?:due|payable).{0,20}(?:Rs\.?|₹|INR)\s*([\d,]+\.?\d*).{0,30}(?:due\s*date|by)\s*(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})\s*(?:for\s+([A-Za-z0-9 .&_\'\-]+))?', "groups": {"amount_str": 1, "date_str": 2, "merchant": 3, "dc": "debit", "category_hint": "bills"}},
]

def main():
    session = SessionLocal()
    try:
        inserted = 0
        for rule in RULES:
            # Check if similar rule exists
            existing = session.execute(text("""
                SELECT COUNT(*) FROM spendsense.parser_rules
                WHERE pattern_regex = :pattern
                  AND bank = :bank
                  AND channel = :channel
                  AND active = TRUE
            """), {
                "pattern": rule["pattern"],
                "bank": rule["bank"],
                "channel": rule["channel"]
            }).scalar()
            
            if existing == 0:
                session.execute(text("""
                    INSERT INTO spendsense.parser_rules(
                        rule_id, bank, channel, priority, active, pattern_regex, groups, created_at
                    ) VALUES (
                        gen_random_uuid(), :bank, :channel, :priority, TRUE, :pattern, CAST(:groups AS jsonb), NOW()
                    )
                """), {
                    "bank": rule["bank"],
                    "channel": rule["channel"],
                    "priority": rule["priority"],
                    "pattern": rule["pattern"],
                    "groups": json.dumps(rule["groups"])
                })
                inserted += 1
                print(f"✅ Added: {rule['bank']}/{rule['channel']} (priority {rule['priority']})")
        
        session.commit()
        print(f"\n✅ Added {inserted} new parser rules (total: {len(RULES)})")
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        session.rollback()
    finally:
        session.close()

if __name__ == '__main__':
    main()

