#!/usr/bin/env python3
"""
Run a specific SQL migration file on Supabase
Usage: python3 scripts/run_migration.py migrations/012_add_merchant_rules_scoping.sql
"""
import os
import sys
import psycopg2
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT
from pathlib import Path
from urllib.parse import urlparse


def run_migration(migration_file_path: str):
    """Apply a SQL migration file to Supabase"""
    # Try to load from .env file
    from dotenv import load_dotenv
    load_dotenv()
    
    # Get database URL from environment
    postgres_url = os.getenv("SUPABASE_DB_URL") or os.getenv("POSTGRES_URL")
    
    # Also try loading from config.py
    if not postgres_url:
        try:
            from config import settings
            postgres_url = settings.postgres_url
        except:
            pass
    
    if not postgres_url or postgres_url == "postgresql://localhost:5432/monytix":
        print("❌ Error: SUPABASE_DB_URL or POSTGRES_URL environment variable not set")
        print("\nTo get your Supabase connection string:")
        print("1. Go to: https://supabase.com/dashboard")
        print("2. Settings → Database → Connection string")
        print("3. Copy the connection string (use 'Direct connection' mode)")
        print("4. Add it to your .env file:")
        print("   POSTGRES_URL='postgresql://postgres:[PASSWORD]@[HOST]:[PORT]/postgres'")
        print("\nOr export it:")
        print("   export POSTGRES_URL='postgresql://postgres:[PASSWORD]@[HOST]:[PORT]/postgres'")
        return False
    
    # Parse connection string
    parsed = urlparse(postgres_url)
    
    try:
        print("🔌 Connecting to Supabase database...")
        # Connect to PostgreSQL
        conn = psycopg2.connect(
            host=parsed.hostname or "localhost",
            port=parsed.port or 5432,
            database=parsed.path.lstrip('/') or "postgres",
            user=parsed.username or "postgres",
            password=parsed.password
        )
        
        conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
        cursor = conn.cursor()
        
        print("✅ Connected to Supabase!")
        
        # Read SQL file
        migration_file = Path(migration_file_path)
        
        if not migration_file.exists():
            # Try relative to script directory
            script_dir = Path(__file__).parent.parent
            migration_file = script_dir / migration_file_path
            
            if not migration_file.exists():
                print(f"❌ Migration file not found: {migration_file}")
                return False
        
        print(f"📄 Reading migration file: {migration_file}")
        
        with open(migration_file, 'r') as f:
            sql_content = f.read()
        
        # Execute SQL
        print("🚀 Running migration on Supabase...")
        print("⏳ This may take a moment...")
        cursor.execute(sql_content)
        
        print("\n✅ Migration completed successfully!")
        print("📊 Check your Supabase dashboard: Database → Tables → merchant_rules")
        
        # Verify migration
        cursor.execute("""
            SELECT column_name, data_type 
            FROM information_schema.columns 
            WHERE table_schema = 'spendsense' 
            AND table_name = 'merchant_rules'
            AND column_name IN ('created_by', 'tenant_id', 'source', 'pattern_hash')
            ORDER BY column_name
        """)
        
        columns = cursor.fetchall()
        if columns:
            print("\n✅ Verified columns added:")
            for col_name, col_type in columns:
                print(f"   - {col_name} ({col_type})")
        
        cursor.close()
        conn.close()
        
        return True
        
    except psycopg2.Error as e:
        print(f"❌ Database error: {e}")
        print("\n💡 Tip: Make sure your connection string includes the correct password")
        return False
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python3 scripts/run_migration.py migrations/012_add_merchant_rules_scoping.sql")
        sys.exit(1)
    
    migration_file = sys.argv[1]
    success = run_migration(migration_file)
    sys.exit(0 if success else 1)

