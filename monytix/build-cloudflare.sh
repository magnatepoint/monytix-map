#!/bin/bash
# Build script for Cloudflare Pages
# This script installs Flutter and builds the web app

set -e

echo "🚀 Starting Flutter web build for Cloudflare Pages..."

# Get the directory where this script is located
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
echo "📁 Script directory: $SCRIPT_DIR"
echo "📁 Current directory: $(pwd)"

# The script is in monytix/build-cloudflare.sh, so monytix is the parent
PROJECT_DIR="$SCRIPT_DIR"

# Check if we're in the monytix directory (script is in monytix/build-cloudflare.sh)
if [ ! -f "$PROJECT_DIR/pubspec.yaml" ]; then
  # Try parent directory (if script is in monytix/scripts/)
  if [ -f "$SCRIPT_DIR/../pubspec.yaml" ]; then
    PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
  # Try finding monytix from current directory
  elif [ -d "$(pwd)/monytix" ] && [ -f "$(pwd)/monytix/pubspec.yaml" ]; then
    PROJECT_DIR="$(cd "$(pwd)/monytix" && pwd)"
  else
    echo "❌ Error: Cannot find monytix directory with pubspec.yaml"
    echo "Current directory: $(pwd)"
    echo "Script directory: $SCRIPT_DIR"
    echo "Listing current directory:"
    ls -la
    echo "Listing script directory:"
    ls -la "$SCRIPT_DIR"
    exit 1
  fi
fi

echo "📁 Project directory: $PROJECT_DIR"

# Install Flutter
echo "📦 Installing Flutter..."
FLUTTER_VERSION="3.24.0"
FLUTTER_SDK_PATH="/opt/buildhome/flutter"

if [ ! -d "$FLUTTER_SDK_PATH" ]; then
  echo "Downloading Flutter SDK..."
  cd /opt/buildhome
  wget -q https://storage.googleapis.com/flutter_infra_release/releases/stable/linux/flutter_linux_${FLUTTER_VERSION}-stable.tar.xz
  tar xf flutter_linux_${FLUTTER_VERSION}-stable.tar.xz
  rm flutter_linux_${FLUTTER_VERSION}-stable.tar.xz
fi

export PATH="$FLUTTER_SDK_PATH/bin:$PATH"

# Verify Flutter installation
flutter --version

# Navigate to project directory
cd "$PROJECT_DIR"
echo "📁 Working directory: $(pwd)"

# Get Flutter dependencies
echo "📦 Getting Flutter dependencies..."
flutter pub get

# Build web app
echo "🔨 Building Flutter web app..."
flutter build web --release

# Add Cloudflare Pages _redirects file
echo "📝 Adding _redirects file for SPA routing..."
echo "/*    /index.html   200" > build/web/_redirects

echo "✅ Build complete! Output in monytix/build/web"

