#!/usr/bin/env python3
"""
Backfill merchant_raw in txn_staging by extracting merchant names from descriptions.

This script processes all staging records where merchant_raw is NULL
and extracts merchant names from UPI transaction descriptions.
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.database.postgresql import SessionLocal
from app.services.merchant_extractor import extract_merchant_from_description
from sqlalchemy import text
from sqlalchemy.orm import Session

def backfill_merchant_names(session: Session, dry_run: bool = True, limit: int = None):
    """
    Backfill merchant_raw for staging records where it's NULL.
    
    Args:
        session: SQLAlchemy session
        dry_run: If True, only show what would be updated without actually updating
        limit: Optional limit on number of records to process
    """
    # Get records with NULL merchant_raw
    query = """
        SELECT 
            staging_id,
            description_raw
        FROM spendsense.txn_staging
        WHERE merchant_raw IS NULL
        AND description_raw IS NOT NULL
        ORDER BY created_at DESC
    """
    
    if limit:
        query += f" LIMIT {limit}"
    
    records = session.execute(text(query)).fetchall()
    
    if not records:
        print("✅ No records found with NULL merchant_raw")
        return 0
    
    print(f"📋 Found {len(records)} records with NULL merchant_raw")
    print("=" * 80)
    
    updated_count = 0
    extracted_count = 0
    
    for rec in records:
        staging_id = rec.staging_id
        description = rec.description_raw or ""
        
        # Extract merchant name
        merchant_name = extract_merchant_from_description(description)
        
        if merchant_name:
            extracted_count += 1
            if dry_run:
                print(f"  Would update: {merchant_name[:40]:<40} | {description[:50]}")
            else:
                # Update the record
                session.execute(
                    text("""
                        UPDATE spendsense.txn_staging
                        SET merchant_raw = :merchant
                        WHERE staging_id = :staging_id
                    """),
                    {"merchant": merchant_name, "staging_id": staging_id}
                )
                updated_count += 1
    
    if not dry_run:
        session.commit()
        print(f"\n✅ Updated {updated_count} records")
    else:
        print(f"\n📊 Would update {extracted_count} records (DRY RUN)")
    
    return extracted_count

def main():
    """Main entry point"""
    import argparse
    
    parser = argparse.ArgumentParser(description="Backfill merchant names in txn_staging")
    parser.add_argument("--dry-run", action="store_true", default=True,
                       help="Show what would be updated without actually updating")
    parser.add_argument("--execute", action="store_true",
                       help="Actually update the records (overrides --dry-run)")
    parser.add_argument("--limit", type=int, default=None,
                       help="Limit number of records to process (for testing)")
    
    args = parser.parse_args()
    
    dry_run = not args.execute
    
    session = SessionLocal()
    try:
        if dry_run:
            print("🔍 DRY RUN MODE - No changes will be made")
            print("   Use --execute to actually update records\n")
        else:
            print("⚠️  EXECUTE MODE - Records will be updated!\n")
        
        count = backfill_merchant_names(session, dry_run=dry_run, limit=args.limit)
        
        if count > 0 and dry_run:
            print(f"\n💡 Run with --execute to update {count} records")
        
    except Exception as e:
        session.rollback()
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
    finally:
        session.close()

if __name__ == "__main__":
    main()

