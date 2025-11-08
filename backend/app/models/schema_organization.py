"""
Database Schema Organization
Groups tables by feature/domain using PostgreSQL schemas
"""
from sqlalchemy import schema
from sqlalchemy.orm import relationship

# Define feature schemas
SCHEMAS = {
    "core": "Core transaction data and production tables",
    "etl": "ETL staging and batch tracking",
    "enrichment": "Rule-based enrichment and user overrides",
    "analytics": "Analytics, insights, and reporting",
    "integrations": "External integrations (Gmail, etc.)",
    "user": "User preferences and settings",
    "goal": "Financial goals (catalog, user goals, tracking)"
}

# Table organization by schema
TABLE_GROUPS = {
    "core": [
        "transactions",
        "categories",
        "budgets",
        "budget_transactions"
    ],
    
    "etl": [
        "upload_batches",
        "txn_staging"
    ],
    
    "enrichment": [
        "txn_enriched",
        "txn_override",
        "enrichment_rules",
        "enrichment_tags"
    ],
    
    "analytics": [
        "insights",
        "goals"
    ],
    
    "integrations": [
        "gmail_connections",
        "email_transactions",
        "bill_reminders"
    ],
    
    "user": [
        "user_preferences",
        "user_settings"
    ],
    "goal": [
        # Master catalog and user-specific goals
        "goal_category_master",
        "user_goals_master"
    ]
}

# Views organization
VIEWS = {
    "core": [
        "vw_transactions_monthly",
        "vw_transactions_by_category"
    ],
    
    "enrichment": [
        "vw_txn_effective"
    ],
    
    "analytics": [
        "vw_spending_trends",
        "vw_category_breakdown"
    ]
}

