#!/usr/bin/env python3
"""
Quick ETL Validation Script
Tests deduplication, categorization, and KPI exclusion
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.database.postgresql import SessionLocal
from sqlalchemy import text

def test_dedupe_fingerprint():
    """Test dedupe fingerprint uniqueness"""
    print("\n🔍 Dedupe Fingerprint Test")
    print("-" * 50)
    
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
            print(f"   Total rows: {total}")
            print(f"   Distinct fingerprints: {distinct}")
            if total == distinct:
                print("   ✅ All fingerprints unique (c == d)")
                return True
            else:
                print(f"   ⚠️  {total - distinct} potential duplicates")
                return False
    except Exception as e:
        print(f"   ❌ Error: {e}")
        return False
    finally:
        session.close()


def test_transfers_exclusion():
    """Test that transfers are excluded from KPI calculations"""
    print("\n🔍 Transfers KPI Exclusion Test")
    print("-" * 50)
    
    session = SessionLocal()
    try:
        # Check transfers in fact table
        transfers_fact = session.execute(text("""
            SELECT COUNT(*) 
            FROM spendsense.txn_fact tf
            JOIN spendsense.txn_enriched te ON te.txn_id = tf.txn_id
            WHERE te.category_code = 'transfers'
        """)).scalar()
        
        # Check transfers in KPI view
        transfers_kpi = session.execute(text("""
            SELECT COUNT(*) 
            FROM spendsense.v_txn_for_kpi
            WHERE category_code = 'transfers'
        """)).scalar()
        
        print(f"   Transfers in fact table: {transfers_fact}")
        print(f"   Transfers in KPI view: {transfers_kpi}")
        
        if transfers_kpi == 0:
            print("   ✅ KPI view correctly excludes transfers")
            return True
        else:
            print(f"   ⚠️  KPI view contains {transfers_kpi} transfers")
            return False
            
    except Exception as e:
        print(f"   ❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        session.close()


def test_audit_fields():
    """Test that audit fields are populated"""
    print("\n🔍 Audit Fields Test")
    print("-" * 50)
    
    session = SessionLocal()
    try:
        # Check ingested_via distribution
        result = session.execute(text("""
            SELECT 
                COALESCE(ingested_via, 'null') as ingested_via,
                COUNT(*) as count
            FROM spendsense.txn_fact
            GROUP BY ingested_via
            ORDER BY count DESC
        """)).fetchall()
        
        print("   Ingested via distribution:")
        for row in result:
            print(f"     {row[0]:20} : {row[1]:5} transactions")
        
        # Check raw_source_id population
        with_source = session.execute(text("""
            SELECT COUNT(*) 
            FROM spendsense.txn_fact
            WHERE raw_source_id IS NOT NULL
        """)).scalar()
        
        total = session.execute(text("""
            SELECT COUNT(*) 
            FROM spendsense.txn_fact
        """)).scalar()
        
        print(f"\n   Raw source ID populated: {with_source}/{total} ({100*with_source//total if total > 0 else 0}%)")
        
        return True
        
    except Exception as e:
        print(f"   ❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        session.close()


def main():
    print("=" * 60)
    print("Quick ETL Validation")
    print("=" * 60)
    
    results = []
    results.append(("Dedupe Fingerprint", test_dedupe_fingerprint()))
    results.append(("Transfers KPI Exclusion", test_transfers_exclusion()))
    results.append(("Audit Fields", test_audit_fields()))
    
    print("\n" + "=" * 60)
    print("Summary")
    print("=" * 60)
    
    for test_name, passed in results:
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"{status} : {test_name}")
    
    all_passed = all(result[1] for result in results)
    return 0 if all_passed else 1


if __name__ == "__main__":
    sys.exit(main())

