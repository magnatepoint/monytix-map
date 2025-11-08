#!/bin/bash
# Build script for Cloudflare Pages
# This script installs Flutter and builds the web app

set -e

echo "🚀 Starting Flutter web build for Cloudflare Pages..."

# Get the directory where this script is located
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PROJECT_DIR="$SCRIPT_DIR"

# If script is in monytix/, use that. Otherwise, try to find monytix directory
if [ ! -f "$PROJECT_DIR/pubspec.yaml" ]; then
  # Script might be called from repo root
  if [ -d "monytix" ]; then
    PROJECT_DIR="$(pwd)/monytix"
  elif [ -d "$SCRIPT_DIR/../monytix" ]; then
    PROJECT_DIR="$SCRIPT_DIR/../monytix"
  else
    echo "❌ Error: Cannot find monytix directory"
    echo "Current directory: $(pwd)"
    echo "Script directory: $SCRIPT_DIR"
    ls -la
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

