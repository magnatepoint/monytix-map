#!/bin/bash
# Post-build script for Flutter web to add Cloudflare Pages _redirects file
# This script should be run after 'flutter build web --release'

# Get the directory where this script is located
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
BUILD_DIR="$PROJECT_DIR/build/web"

# Check if build directory exists
if [ ! -d "$BUILD_DIR" ]; then
    echo "❌ Build directory not found: $BUILD_DIR"
    echo "Please run 'flutter build web --release' first"
    exit 1
fi

# Create _redirects file for Cloudflare Pages SPA routing
REDIRECTS_FILE="$BUILD_DIR/_redirects"
echo "/*    /index.html   200" > "$REDIRECTS_FILE"

echo "✅ Created _redirects file for Cloudflare Pages: $REDIRECTS_FILE"
echo "📦 Ready to deploy to Cloudflare Pages!"
