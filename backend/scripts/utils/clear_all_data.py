#!/usr/bin/env python3
"""
Script to clear all data from PostgreSQL, MongoDB, and Redis databases.
WARNING: This will delete ALL data from all databases. Use with caution!
"""
import sys
import os
from pathlib import Path

# Add parent directory to path to import config
sys.path.insert(0, str(Path(__file__).parent.parent))

from config import settings
from sqlalchemy import text, inspect
from app.database.postgresql import sync_engine
from app.database.mongodb import get_mongo_db, get_async_mongo_db
import redis
import asyncio


def clear_postgresql():
    """Clear all data from PostgreSQL tables"""
    print("\n🗄️  Clearing PostgreSQL data...")
    
    with sync_engine.connect() as conn:
        # Get all tables from all schemas
        inspector = inspect(sync_engine)
        
        # Get tables from default schema (production models)
        default_tables = inspector.get_table_names()
        
        # Get tables from spendsense schema
        spendsense_tables = inspector.get_table_names(schema='spendsense')
        
        # Disable foreign key checks temporarily (PostgreSQL doesn't have this, but we'll handle CASCADE)
        # Clear tables in reverse dependency order
        
        # 1. Clear spendsense schema tables (in dependency order)
        if spendsense_tables:
            print(f"  Clearing {len(spendsense_tables)} tables from spendsense schema...")
            
            # Order matters - clear dependent tables first
            clear_order = [
                'kpi_recurring_merchants_monthly',
                'kpi_spending_leaks_monthly',
                'kpi_category_monthly',
                'kpi_type_split_monthly',
                'kpi_type_split_daily',
                'txn_override',
                'txn_enriched',
                'txn_fact',
                'txn_staging',
                'upload_batch',
                'merchant_rules',
                'integration_events',
                'api_request_log',
                'app_events',
                'dim_merchant',
                'dim_subcategory',
                'dim_category',
            ]
            
            # Clear tables in order
            for table in clear_order:
                if table in spendsense_tables:
                    try:
                        conn.execute(text(f'TRUNCATE TABLE spendsense."{table}" CASCADE'))
                        conn.commit()
                        print(f"    ✓ Cleared spendsense.{table}")
                    except Exception as e:
                        print(f"    ⚠ Error clearing spendsense.{table}: {e}")
            
            # Clear any remaining tables
            for table in spendsense_tables:
                if table not in clear_order:
                    try:
                        conn.execute(text(f'TRUNCATE TABLE spendsense."{table}" CASCADE'))
                        conn.commit()
                        print(f"    ✓ Cleared spendsense.{table}")
                    except Exception as e:
                        print(f"    ⚠ Error clearing spendsense.{table}: {e}")
        
        # 2. Clear default schema tables (production and staging models)
        if default_tables:
            print(f"  Clearing {len(default_tables)} tables from default schema...")
            
            # Order matters - clear dependent tables first
            clear_order_default = [
                'budget_transactions',
                'budgets',
                'enrichment_tags',
                'txn_override',
                'txn_enriched',
                'enrichment_rules',
                'transactions',
                'goals',
                'insights',
                'categories',
                'email_transactions',
                'bill_reminders',
                'gmail_connections',
                'txn_staging',
                'upload_batches',
            ]
            
            # Clear tables in order
            for table in clear_order_default:
                if table in default_tables:
                    try:
                        conn.execute(text(f'TRUNCATE TABLE "{table}" CASCADE'))
                        conn.commit()
                        print(f"    ✓ Cleared {table}")
                    except Exception as e:
                        print(f"    ⚠ Error clearing {table}: {e}")
            
            # Clear any remaining tables
            for table in default_tables:
                if table not in clear_order_default:
                    try:
                        conn.execute(text(f'TRUNCATE TABLE "{table}" CASCADE'))
                        conn.commit()
                        print(f"    ✓ Cleared {table}")
                    except Exception as e:
                        print(f"    ⚠ Error clearing {table}: {e}")
    
    print("  ✅ PostgreSQL data cleared")


async def clear_mongodb():
    """Clear all data from MongoDB collections"""
    print("\n🍃 Clearing MongoDB data...")
    
    try:
        db = await get_async_mongo_db()
        
        # Get all collection names
        collections = await db.list_collection_names()
        
        if not collections:
            print("  ℹ️  No collections found in MongoDB")
            return
        
        print(f"  Clearing {len(collections)} collections...")
        
        for collection_name in collections:
            try:
                collection = db[collection_name]
                result = await collection.delete_many({})
                print(f"    ✓ Cleared {collection_name} ({result.deleted_count} documents)")
            except Exception as e:
                print(f"    ⚠ Error clearing {collection_name}: {e}")
        
        print("  ✅ MongoDB data cleared")
    except Exception as e:
        print(f"  ⚠️  Error connecting to MongoDB: {e}")
        print("  ℹ️  Continuing with other databases...")


def clear_redis():
    """Clear all data from Redis"""
    print("\n🔴 Clearing Redis data...")
    
    try:
        # Parse Redis URL
        redis_url = settings.redis_url
        if redis_url.startswith('redis://'):
            # Parse redis://localhost:6379/0
            parts = redis_url.replace('redis://', '').split('/')
            host_port = parts[0]
            db_num = int(parts[1]) if len(parts) > 1 else 0
            
            if ':' in host_port:
                host, port = host_port.split(':')
                port = int(port)
            else:
                host = host_port
                port = 6379
        else:
            host = 'localhost'
            port = 6379
            db_num = 0
        
        r = redis.Redis(host=host, port=port, db=db_num, decode_responses=True)
        
        # Test connection
        r.ping()
        
        # Flush current database
        r.flushdb()
        print(f"    ✓ Flushed Redis database {db_num}")
        
        # Also try to flush all databases (if we have access)
        try:
            r.flushall()
            print("    ✓ Flushed all Redis databases")
        except:
            pass
        
        print("  ✅ Redis data cleared")
    except Exception as e:
        print(f"  ⚠️  Error connecting to Redis: {e}")
        print("  ℹ️  Continuing...")


def remove_redis_dump():
    """Remove Redis dump file if it exists"""
    dump_file = Path(__file__).parent.parent / "dump.rdb"
    if dump_file.exists():
        try:
            dump_file.unlink()
            print(f"  ✓ Removed Redis dump file: {dump_file}")
        except Exception as e:
            print(f"  ⚠️  Error removing dump file: {e}")


def main():
    """Main function to clear all data"""
    print("=" * 60)
    print("⚠️  WARNING: This will delete ALL data from:")
    print("   - PostgreSQL (all schemas)")
    print("   - MongoDB (all collections)")
    print("   - Redis (all databases)")
    print("=" * 60)
    
    response = input("\nAre you sure you want to continue? (yes/no): ")
    if response.lower() != 'yes':
        print("❌ Operation cancelled.")
        return
    
    print("\n🚀 Starting data cleanup...")
    
    # Clear PostgreSQL
    try:
        clear_postgresql()
    except Exception as e:
        print(f"❌ Error clearing PostgreSQL: {e}")
    
    # Clear MongoDB
    try:
        asyncio.run(clear_mongodb())
    except Exception as e:
        print(f"❌ Error clearing MongoDB: {e}")
    
    # Clear Redis
    try:
        clear_redis()
        remove_redis_dump()
    except Exception as e:
        print(f"❌ Error clearing Redis: {e}")
    
    print("\n" + "=" * 60)
    print("✅ Data cleanup completed!")
    print("=" * 60)


if __name__ == "__main__":
    main()

