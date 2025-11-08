#!/usr/bin/env python3
"""
Refresh SpendSense KPI materialized views.

Usage:
  From project root:
    python backend/scripts/refresh_kpis.py
  Or from backend/ directory:
    python scripts/refresh_kpis.py
"""
import os
import sys
from sqlalchemy import text


def main() -> int:
    # Ensure backend/ is on sys.path so `app.*` imports work from any cwd
    backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if backend_dir not in sys.path:
        sys.path.insert(0, backend_dir)

    try:
        from app.database.postgresql import SessionLocal
    except Exception as e:
        print(f"❌ Failed to import app modules: {e}")
        return 1

    session = SessionLocal()
    try:
        # Check if views exist before refreshing
        result = session.execute(text("""
            SELECT EXISTS (
                SELECT 1 FROM pg_matviews 
                WHERE schemaname = 'spendsense' 
                AND matviewname = 'mv_spendsense_dashboard_user_month'
            )
        """))
        if result.scalar():
            try:
                session.execute(text("REFRESH MATERIALIZED VIEW CONCURRENTLY spendsense.mv_spendsense_dashboard_user_month"))
            except Exception:
                session.execute(text("REFRESH MATERIALIZED VIEW spendsense.mv_spendsense_dashboard_user_month"))
        
        result = session.execute(text("""
            SELECT EXISTS (
                SELECT 1 FROM pg_matviews 
                WHERE schemaname = 'spendsense' 
                AND matviewname = 'mv_spendsense_insights_user_month'
            )
        """))
        if result.scalar():
            try:
                session.execute(text("REFRESH MATERIALIZED VIEW CONCURRENTLY spendsense.mv_spendsense_insights_user_month"))
            except Exception:
                session.execute(text("REFRESH MATERIALIZED VIEW spendsense.mv_spendsense_insights_user_month"))
        
        session.commit()
        print("✅ KPI materialized views refreshed")
        return 0
    except Exception as e:
        print(f"❌ Failed to refresh KPIs: {e}")
        return 1
    finally:
        session.close()


if __name__ == "__main__":
    sys.exit(main())


