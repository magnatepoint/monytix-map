"""
Database Views
Creates effective enrichment view (vw_txn_effective)
"""
from sqlalchemy import text
from app.database.postgresql import sync_engine


def create_effective_enrichment_view():
    """
    Create view: vw_txn_effective
    
    Combines txn_enriched with txn_override
    Override fields take precedence over enrichment fields
    """
    
    view_sql = """
    CREATE OR REPLACE VIEW vw_txn_effective AS
    SELECT 
        t.id,
        t.user_id,
        t.amount,
        t.currency,
        t.transaction_date,
        t.description,
        
        -- Merchants (override takes precedence)
        COALESCE(
            o.merchant_override,
            e.merchant,
            t.merchant
        ) AS effective_merchant,
        
        -- Subcategories (override takes precedence)
        COALESCE(
            o.subcategory_override,
            e.subcategory
        ) AS effective_subcategory,
        
        -- Categories (override takes precedence)
        COALESCE(
            o.category_override,
            e.category,
            t.category
        ) AS effective_category,
        
        -- Classification (override takes precedence)
        COALESCE(
            o.classification_override,
            e.classification,
            'unlabeled'
        ) AS effective_classification,
        
        -- Confidence
        COALESCE(
            CASE WHEN o.id IS NOT NULL THEN 1.0 ELSE e.enrichment_confidence END,
            0.5
        ) AS effective_confidence,
        
        -- Metadata
        e.enrichment_timestamp,
        o.created_at AS override_at,
        CASE WHEN o.id IS NOT NULL THEN true ELSE false END AS is_overridden,
        
        -- Transaction info
        t.transaction_type,
        t.status,
        t.bank,
        t.created_at
        
    FROM transactions t
    LEFT JOIN txn_enriched e ON t.id = e.transaction_id
    LEFT JOIN txn_override o ON t.id = o.transaction_id;
    """
    
    try:
        with sync_engine.connect() as conn:
            conn.execute(text(view_sql))
            conn.commit()
        print("✅ View vw_txn_effective created successfully")
    except Exception as e:
        print(f"⚠️  View creation error: {e}")


def create_enrichment_materialized_view():
    """
    Create materialized view for faster queries
    Refreshed periodically
    """
    
    view_sql = """
    CREATE MATERIALIZED VIEW IF NOT EXISTS vw_txn_enrichment_mv AS
    SELECT 
        e.transaction_id,
        e.merchant,
        e.subcategory,
        e.category,
        e.classification,
        e.enrichment_confidence,
        e.enrichment_rules_applied,
        e.enrichment_timestamp,
        e.user_id
    FROM txn_enriched e;
    
    CREATE INDEX IF NOT EXISTS idx_enrichment_mv_user ON vw_txn_enrichment_mv(user_id);
    CREATE INDEX IF NOT EXISTS idx_enrichment_mv_category ON vw_txn_enrichment_mv(category);
    CREATE INDEX IF NOT EXISTS idx_enrichment_mv_classification ON vw_txn_enrichment_mv(classification);
    """
    
    try:
        with sync_engine.connect() as conn:
            conn.execute(text(view_sql))
            conn.commit()
        print("✅ Materialized view created successfully")
    except Exception as e:
        print(f"⚠️  Materialized view creation error: {e}")


if __name__ == "__main__":
    create_effective_enrichment_view()
    # create_enrichment_materialized_view()  # Uncomment if needed

