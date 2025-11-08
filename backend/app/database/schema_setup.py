"""
Setup PostgreSQL Schemas
Creates feature-based schemas and organizes tables
"""
from sqlalchemy import text, create_engine, MetaData
from config import settings


def create_schemas():
    """
    Create all feature schemas in PostgreSQL
    """
    engine = create_engine(settings.postgres_url)
    
    schemas_to_create = [
        "core",
        "etl",
        "enrichment",
        "analytics",
        "integrations",
        "user",
        "goal"
    ]
    
    with engine.connect() as conn:
        for schema_name in schemas_to_create:
            try:
                conn.execute(text(f"CREATE SCHEMA IF NOT EXISTS {schema_name}"))
                print(f"✅ Schema '{schema_name}' created")
            except Exception as e:
                print(f"⚠️  Could not create schema '{schema_name}': {e}")
        
        conn.commit()
    
    print("✅ All schemas created successfully")


def list_all_tables_by_schema():
    """
    List all tables organized by schema
    """
    engine = create_engine(settings.postgres_url)
    
    query = text("""
        SELECT 
            table_schema,
            table_name,
            table_type
        FROM information_schema.tables
        WHERE table_schema IN ('public', 'core', 'etl', 'enrichment', 'analytics', 'integrations', 'user', 'goal')
        ORDER BY table_schema, table_name
    """)
    
    with engine.connect() as conn:
        result = conn.execute(query)
        rows = result.fetchall()
        
        organized = {}
        for row in rows:
            schema_name = row[0] if row[0] != 'public' else 'core'
            table_name = row[1]
            
            if schema_name not in organized:
                organized[schema_name] = []
            organized[schema_name].append(table_name)
        
        print("\n📊 Tables organized by feature schema:")
        print("=" * 60)
        for schema, tables in organized.items():
            print(f"\n{schema.upper()} ({len(tables)} tables):")
            for table in tables:
                print(f"  - {table}")
        
        return organized


if __name__ == "__main__":
    # Create schemas
    create_schemas()
    
    # List tables
    list_all_tables_by_schema()

