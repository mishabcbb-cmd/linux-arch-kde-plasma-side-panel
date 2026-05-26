#!/usr/bin/env bash
# scripts/pgo-generate.sh — Generate PGO profile data for GCC 16
#
# Builds with -fprofile-generate, runs training workload,
# produces .gcda files for PGO optimization.
#
# Usage: ./scripts/pgo-generate.sh

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$SCRIPT_DIR/.."
BUILD_DIR="$PROJECT_DIR/build-pgo-gen"

echo "=== PGO Generate ==="
echo "Building with -fprofile-generate..."

# Clean build directory
rm -rf "$BUILD_DIR"
mkdir -p "$BUILD_DIR"

# Configure with profile generation
cmake -B "$BUILD_DIR" \
    -DCMAKE_BUILD_TYPE=Release \
    -DCMAKE_CXX_FLAGS="-fprofile-generate -fprofile-dir=$BUILD_DIR/pgo-data" \
    -DCMAKE_EXE_LINKER_FLAGS="-fprofile-generate" \
    "$PROJECT_DIR"

# Build
cmake --build "$BUILD_DIR" -j"$(nproc)"

echo "=== Running training workload ==="

# Run training workload to generate profile data
export LLAMA_PROFILE_DIR="$BUILD_DIR/pgo-data"
mkdir -p "$LLAMA_PROFILE_DIR"

# Training: run the native module through typical RAG operations
python3 -c "
import sys
sys.path.insert(0, '$BUILD_DIR')
try:
    import rag_native
    import numpy as np

    # Generate test embeddings
    dim = 768
    num = 100
    a = np.random.randn(num, dim).astype(np.float32)
    b = np.random.randn(num, dim).astype(np.float32)

    # Run typical operations
    for _ in range(50):
        rag_native.batch_normalize(a, dim)
        rag_native.batch_normalize(b, dim)
        rag_native.similarity_matrix(a, b, dim)

    # Token counting
    texts = ['Hello world'] * 1000
    for t in texts:
        rag_native.count_tokens(t)

    # Chunking
    long_text = 'Paragraph one. ' * 500
    rag_native.chunk_text(long_text, 512, 64)

    print('Training workload completed')
except ImportError:
    print('rag_native not built yet, skipping training')
"

echo "=== Profile data generated ==="
echo "Data directory: $BUILD_DIR/pgo-data"
ls -la "$BUILD_DIR/pgo-data/" 2>/dev/null || echo "(no data yet — run after first build)"
