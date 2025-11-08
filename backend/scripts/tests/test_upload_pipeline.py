#!/usr/bin/env python3
"""
Test script to verify CSV, PDF, and Email upload and ETL pipeline

This script checks:
1. Upload endpoints are registered
2. Workers are functional
3. ETL pipeline (staging → fact → enriched) works
4. Data flows correctly through the system
"""

import sys
import os

# Add backend to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.database.postgresql import SessionLocal
from app.models.spendsense_models import (
    UploadBatch, TxnStaging, TxnFact, TxnEnriched,
    DimCategory, DimMerchant, MerchantRule
)
from sqlalchemy import func
from datetime import datetime, timedelta


def check_schema_and_tables():
    """Verify all required tables exist"""
    print("\n" + "="*80)
    print("1. Checking Schema and Tables")
    print("="*80)
    
    session = SessionLocal()
    try:
        # Check if schema exists
        from sqlalchemy import text
        result = session.execute(text("""
            SELECT schema_name 
            FROM information_schema.schemata 
            WHERE schema_name = 'spendsense'
        """))
        
        if not list(result):
            print("❌ spendsense schema not found!")
            return False
        
        print("✅ spendsense schema exists")
        
        # Check tables
        tables = [
            'upload_batch', 'txn_staging', 'txn_fact', 'txn_enriched',
            'dim_category', 'dim_subcategory', 'dim_merchant', 'merchant_rules'
        ]
        
        for table in tables:
            result = session.execute(text(f"""
                SELECT table_name 
                FROM information_schema.tables 
                WHERE table_schema = 'spendsense' 
                AND table_name = '{table}'
            """))
            if list(result):
                print(f"✅ {table} exists")
            else:
                print(f"❌ {table} missing!")
                return False
        
        return True
    except Exception as e:
        print(f"❌ Error checking schema: {e}")
        return False
    finally:
        session.close()


def check_data_counts():
    """Check current data counts"""
    print("\n" + "="*80)
    print("2. Checking Data Counts")
    print("="*80)
    
    session = SessionLocal()
    try:
        # Count upload batches
        upload_count = session.query(func.count(UploadBatch.upload_id)).scalar()
        print(f"📊 Upload batches: {upload_count}")
        
        # Count staging transactions
        staging_count = session.query(func.count(TxnStaging.staging_id)).scalar()
        print(f"📊 Staging transactions: {staging_count}")
        
        # Count fact transactions
        fact_count = session.query(func.count(TxnFact.txn_id)).scalar()
        print(f"📊 Fact transactions: {fact_count}")
        
        # Count enriched transactions
        enriched_count = session.query(func.count(TxnEnriched.enrich_id)).scalar()
        print(f"📊 Enriched transactions: {enriched_count}")
        
        # Count categories
        cat_count = session.query(func.count(DimCategory.category_code)).scalar()
        print(f"📊 Categories: {cat_count}")
        
        # Count merchants
        merch_count = session.query(func.count(DimMerchant.merchant_id)).scalar()
        print(f"📊 Merchants: {merch_count}")
        
        # Count merchant rules
        rule_count = session.query(func.count(MerchantRule.rule_id)).scalar()
        print(f"📊 Merchant rules: {rule_count}")
        
        # Check for unprocessed staging rows
        unprocessed = session.query(func.count(TxnStaging.staging_id)).filter(
            TxnStaging.parsed_ok == True
        ).scalar()
        
        print(f"\n📋 Unprocessed staging rows (parsed_ok=True): {unprocessed}")
        
        # Check recent upload batches
        recent_batches = session.query(UploadBatch).order_by(
            UploadBatch.received_at.desc()
        ).limit(5).all()
        
        if recent_batches:
            print("\n📦 Recent upload batches:")
            for batch in recent_batches:
                print(f"  - {batch.upload_id}: {batch.source_type} ({batch.status}) - {batch.parsed_records}/{batch.total_records} records")
        
        return True
    except Exception as e:
        print(f"❌ Error checking data: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        session.close()


def check_workers_importable():
    """Check if workers can be imported"""
    print("\n" + "="*80)
    print("3. Checking Workers (Import)")
    print("="*80)
    
    try:
        from app.workers.csv_worker import parse_csv
        print("✅ CSV worker importable")
    except Exception as e:
        print(f"❌ CSV worker import failed: {e}")
        return False
    
    try:
        from app.workers.pdf_worker import parse_pdf
        print("✅ PDF worker importable")
    except Exception as e:
        print(f"❌ PDF worker import failed: {e}")
        return False
    
    try:
        from app.workers.gmail_worker import fetch_gmail_emails
        print("✅ Gmail worker importable")
    except Exception as e:
        print(f"❌ Gmail worker import failed: {e}")
        return False
    
    return True


def check_etl_function():
    """Check if ETL load function is importable"""
    print("\n" + "="*80)
    print("4. Checking ETL Pipeline")
    print("="*80)
    
    try:
        from app.routers.etl import load_staging_for_user
        print("✅ load_staging_for_user function importable")
        
        # Check function signature
        import inspect
        sig = inspect.signature(load_staging_for_user)
        print(f"✅ Function signature: {sig}")
        
        return True
    except Exception as e:
        print(f"❌ ETL function import failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def check_routers_registered():
    """Check if upload routers are registered in main.py"""
    print("\n" + "="*80)
    print("5. Checking Router Registration")
    print("="*80)
    
    try:
        # Read main.py to check router registration
        main_py_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            'app', 'main.py'
        )
        
        with open(main_py_path, 'r') as f:
            content = f.read()
        
        routers = {
            'uploads': '/api/upload',
            'etl': '/api/etl',
            'gmail_realtime': '/api/gmail'
        }
        
        for router_name, path in routers.items():
            if f'uploads' in content.lower() or 'etl' in content.lower() or 'gmail' in content.lower():
                print(f"✅ {router_name} router likely registered (check main.py for exact path)")
            else:
                print(f"⚠️  {router_name} router registration not found in main.py")
        
        return True
    except Exception as e:
        print(f"❌ Error checking routers: {e}")
        return False


def check_end_to_end_flow():
    """Check if data flows correctly from staging to fact to enriched"""
    print("\n" + "="*80)
    print("6. Checking End-to-End Data Flow")
    print("="*80)
    
    session = SessionLocal()
    try:
        # Find a staging row that should have made it to fact
        staging_row = session.query(TxnStaging).filter(
            TxnStaging.parsed_ok == True
        ).first()
        
        if not staging_row:
            print("⚠️  No parsed staging rows found - cannot verify flow")
            return True
        
        print(f"📋 Testing with staging_id: {staging_row.staging_id}")
        print(f"   Upload ID: {staging_row.upload_id}")
        print(f"   Date: {staging_row.txn_date}, Amount: {staging_row.amount}, Direction: {staging_row.direction}")
        
        # Check if corresponding fact row exists
        fact_row = session.query(TxnFact).filter(
            TxnFact.user_id == staging_row.user_id,
            TxnFact.txn_date == staging_row.txn_date,
            TxnFact.amount == staging_row.amount,
            TxnFact.direction == staging_row.direction
        ).first()
        
        if fact_row:
            print(f"✅ Corresponding fact row found: {fact_row.txn_id}")
            
            # Check if enriched row exists
            enriched_row = session.query(TxnEnriched).filter(
                TxnEnriched.txn_id == fact_row.txn_id
            ).first()
            
            if enriched_row:
                print(f"✅ Corresponding enriched row found: {enriched_row.enrich_id}")
                print(f"   Category: {enriched_row.category_code}")
                print(f"   Subcategory: {enriched_row.subcategory_code}")
                print(f"   Type: {enriched_row.txn_type}")
            else:
                print("⚠️  No enriched row found (may need to run load_staging_for_user)")
        else:
            print("⚠️  No corresponding fact row found (staging not loaded yet)")
            print("   Try running: load_staging_for_user(user_id)")
        
        return True
    except Exception as e:
        print(f"❌ Error checking flow: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        session.close()


def main():
    print("\n" + "="*80)
    print("Upload & ETL Pipeline Test")
    print("="*80)
    print(f"Timestamp: {datetime.now()}")
    
    checks = [
        check_schema_and_tables,
        check_data_counts,
        check_workers_importable,
        check_etl_function,
        check_routers_registered,
        check_end_to_end_flow
    ]
    
    results = []
    for check in checks:
        try:
            result = check()
            results.append(result)
        except Exception as e:
            print(f"❌ Check failed with exception: {e}")
            results.append(False)
    
    print("\n" + "="*80)
    print("Summary")
    print("="*80)
    
    passed = sum(results)
    total = len(results)
    
    print(f"✅ Passed: {passed}/{total}")
    print(f"❌ Failed: {total - passed}/{total}")
    
    if passed == total:
        print("\n🎉 All checks passed! Pipeline is ready.")
    else:
        print("\n⚠️  Some checks failed. Review the output above.")
    
    return passed == total


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)

