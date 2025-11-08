#!/bin/bash
# Quick ETL Validation Script
# Tests deduplication, categorization, and KPI exclusion

echo "🔍 Quick ETL Validation"
echo "=" * 60

# Run Python validation
python3 scripts/validate_etl_pipeline.py

echo ""
echo "🔍 SQL Spot Checks"
echo "=" * 60

# Test dedupe fingerprint uniqueness
python3 << 'PYEOF'
from app.database.postgresql import SessionLocal
from sqlalchemy import text

session = SessionLocal()
try:
    result = session.execute(text("""
        SELECT 
            COUNT(*) as c, 
            COUNT(DISTINCT dedupe_fp) as d 
        FROM spendsense.txn_fact
        WHERE dedupe_fp IS NOT NULL
    """)).fetchone()
    
    if result:
        total, distinct = result
        print(f"✅ Dedupe Fingerprint: {total} total, {distinct} distinct")
        if total == distinct:
            print("   ✅ All fingerprints unique (c == d)")
        else:
            print(f"   ⚠️  {total - distinct} potential duplicates")
except Exception as e:
    print(f"❌ Error: {e}")
finally:
    session.close()
PYEOF

# Test transfers exclusion
python3 << 'PYEOF'
from app.database.postgresql import SessionLocal
from sqlalchemy import text

session = SessionLocal()
try:
    # Check transfers in fact vs KPI view
    transfers_fact = session.execute(text("""
        SELECT COUNT(*) 
        FROM spendsense.txn_fact tf
        JOIN spendsense.txn_enriched te ON te.txn_id = tf.txn_id
        WHERE te.category_code = 'transfers'
    """)).scalar()
    
    transfers_kpi = session.execute(text("""
        SELECT COUNT(*) 
        FROM spendsense.v_txn_for_kpi
        WHERE category_code = 'transfers'
    """)).scalar()
    
    print(f"\n✅ Transfers Exclusion:")
    print(f"   Transfers in fact: {transfers_fact}")
    print(f"   Transfers in KPI view: {transfers_kpi}")
    if transfers_kpi == 0:
        print("   ✅ KPI view correctly excludes transfers")
    else:
        print(f"   ⚠️  KPI view contains {transfers_kpi} transfers")
        
except Exception as e:
    print(f"❌ Error: {e}")
finally:
    session.close()
PYEOF

echo ""
echo "✅ Validation complete!"

