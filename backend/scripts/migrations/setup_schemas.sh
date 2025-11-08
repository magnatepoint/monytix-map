#!/bin/bash
# Setup PostgreSQL schemas for feature-based organization

echo "🚀 Setting up database schemas..."
echo ""

# Run the schema setup
python3 -m app.database.schema_setup

echo ""
echo "📊 Current table organization:"
python3 -m migrations.migrate_to_schemas

echo ""
echo "✅ Schema setup complete!"

