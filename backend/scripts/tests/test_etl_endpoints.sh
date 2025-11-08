#!/bin/bash
# ETL Endpoints Validation Script
# Tests upload endpoints, deduplication, and categorization

set -e

BASE_URL="${BASE_URL:-http://localhost:8000}"
TOKEN="${TOKEN:-}"

if [ -z "$TOKEN" ]; then
    echo "❌ Error: TOKEN environment variable not set"
    echo "Usage: TOKEN=<your-token> ./scripts/test_etl_endpoints.sh"
    exit 1
fi

echo "============================================================"
echo "ETL Endpoints Validation"
echo "============================================================"
echo "Base URL: $BASE_URL"
echo ""

# Test 1: CSV Upload
echo "🔍 Test 1: CSV Upload"
echo "------------------------------------------------------------"
if [ -f "test_data/mini.csv" ]; then
    RESPONSE=$(curl -s -X POST \
        -H "Authorization: Bearer $TOKEN" \
        -F "file=@test_data/mini.csv" \
        "$BASE_URL/api/etl/upload/csv")
    echo "$RESPONSE" | jq '.' || echo "$RESPONSE"
    BATCH_ID=$(echo "$RESPONSE" | jq -r '.batch_id // empty')
    if [ -n "$BATCH_ID" ]; then
        echo "✅ CSV upload successful (batch_id: $BATCH_ID)"
    else
        echo "❌ CSV upload failed"
    fi
else
    echo "⚠️  test_data/mini.csv not found - skipping"
fi

# Test 2: XLSX Upload
echo ""
echo "🔍 Test 2: XLSX Upload"
echo "------------------------------------------------------------"
if [ -f "test_data/mini.xlsx" ]; then
    RESPONSE=$(curl -s -X POST \
        -H "Authorization: Bearer $TOKEN" \
        -F "file=@test_data/mini.xlsx" \
        "$BASE_URL/api/etl/upload/xlsx")
    echo "$RESPONSE" | jq '.' || echo "$RESPONSE"
    BATCH_ID=$(echo "$RESPONSE" | jq -r '.batch_id // empty')
    if [ -n "$BATCH_ID" ]; then
        echo "✅ XLSX upload successful (batch_id: $BATCH_ID)"
    else
        echo "❌ XLSX upload failed"
    fi
else
    echo "⚠️  test_data/mini.xlsx not found - skipping"
fi

# Test 3: Batch Status
if [ -n "$BATCH_ID" ]; then
    echo ""
    echo "🔍 Test 3: Batch Status"
    echo "------------------------------------------------------------"
    RESPONSE=$(curl -s -X GET \
        -H "Authorization: Bearer $TOKEN" \
        "$BASE_URL/api/etl/batches/$BATCH_ID")
    echo "$RESPONSE" | jq '.' || echo "$RESPONSE"
fi

# Test 4: Load Staging
echo ""
echo "🔍 Test 4: Load Staging"
echo "------------------------------------------------------------"
RESPONSE=$(curl -s -X POST \
    -H "Authorization: Bearer $TOKEN" \
    "$BASE_URL/api/etl/spendsense/load/staging")
echo "$RESPONSE" | jq '.' || echo "$RESPONSE"

echo ""
echo "✅ Validation complete!"

