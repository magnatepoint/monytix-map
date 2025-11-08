#!/usr/bin/env python3
"""
Refresh SpendSense Materialized Views
This script refreshes the materialized views for dashboard and insights.
"""
import os
import sys
import psycopg2
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT
from config import settings


def refresh_views():
    """Refresh SpendSense materialized views"""
    # Get database URL from environment or config
    postgres_url = os.getenv("POSTGRES_URL") or os.getenv("SUPABASE_DB_URL") or settings.postgres_url
    
    if not postgres_url:
        print("❌ Error: POSTGRES_URL or SUPABASE_DB_URL environment variable not set")
        return False
    
    # Parse connection string
    from urllib.parse import urlparse
    parsed = urlparse(postgres_url)
    
    try:
        print("🔌 Connecting to database...")
        conn = psycopg2.connect(
            host=parsed.hostname or "localhost",
            port=parsed.port or 5432,
            database=parsed.path.lstrip('/') or "postgres",
            user=parsed.username or "postgres",
            password=parsed.password
        )
        
        conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
        cursor = conn.cursor()
        
        print("✅ Connected!")
        
        # Refresh dashboard view
        print("🔄 Refreshing mv_spendsense_dashboard_user_month...")
        cursor.execute("REFRESH MATERIALIZED VIEW CONCURRENTLY spendsense.mv_spendsense_dashboard_user_month;")
        print("   ✅ Dashboard view refreshed")
        
        # Refresh insights view
        print("🔄 Refreshing mv_spendsense_insights_user_month...")
        cursor.execute("REFRESH MATERIALIZED VIEW CONCURRENTLY spendsense.mv_spendsense_insights_user_month;")
        print("   ✅ Insights view refreshed")
        
        print("\n✅ All materialized views refreshed successfully!")
        
        cursor.close()
        conn.close()
        
        return True
        
    except psycopg2.Error as e:
        print(f"❌ Database error: {e}")
        return False
    except Exception as e:
        print(f"❌ Error: {e}")
        return False


if __name__ == "__main__":
    success = refresh_views()
    sys.exit(0 if success else 1)

