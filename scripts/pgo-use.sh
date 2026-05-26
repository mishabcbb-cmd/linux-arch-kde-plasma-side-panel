#!/usr/bin/env bash
# scripts/pgo-use.sh — Build with PGO profile data
#
# Builds with -fprofile-use, applies all GCC 16 optimizations,
# installs to build-pgo-install/.
#
# Usage: ./scripts/pgo-use.sh

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$SCRIPT_DIR/.."
BUILD_DIR="$PROJECT_DIR/build-pgo-use"
GEN_DIR="$PROJECT_DIR/build-pgo-gen"

if [ ! -d "$GEN_DIR/pgo-data" ]; then
    echo "Error: PGO data not found. Run ./scripts/pgo-generate.sh first."
    exit 1
fi

echo "=== PGO Use ==="
echo "Building with -fprofile-use..."

# Clean build directory
rm -rf "$BUILD_DIR"
mkdir -p "$BUILD_DIR"

# Merge profile data
llvm-profdata merge -output="$BUILD_DIR/pgo-merged.profdata" "$GEN_DIR/pgo-data/"*.profraw 2>/dev/null || true

# Configure with profile use
cmake -B "$BUILD_DIR" \
    -DCMAKE_BUILD_TYPE=Release \
    -DCMAKE_CXX_FLAGS="-fprofile-use=$BUILD_DIR/pgo-merged.profdata -fprofile-correction" \
    "$PROJECT_DIR"

# Build with all optimizations
cmake --build "$BUILD_DIR" -j"$(nproc)"

# Install
cmake --install "$BUILD_DIR" --prefix "$BUILD_DIR/install"

echo "=== PGO build complete ==="
echo "Installed to: $BUILD_DIR/install"
echo ""
echo "To use the optimized build:"
echo "  export PYTHONPATH=$BUILD_DIR/install/lib/python3.14/site-packages:\$PYTHONPATH"
