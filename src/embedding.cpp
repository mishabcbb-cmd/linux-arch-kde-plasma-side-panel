/**
 * src/embedding.cpp — Fast embedding operations (cosine similarity, normalization).
 *
 * Optimized with GCC 16: -march=native, -O3, LTO thin, auto-vectorization.
 */

#include "rag_native.h"
#include <cstring>
#include <algorithm>
#include <stdexcept>

namespace rag_native {

float cosine_similarity(const float* a, const float* b, size_t dim) {
    if (dim == 0) return 0.0f;

    float dot = 0.0f, norm_a = 0.0f, norm_b = 0.0f;

    // Manual loop — GCC 16 auto-vectorizes with -march=native -O3
    for (size_t i = 0; i < dim; ++i) {
        dot += a[i] * b[i];
        norm_a += a[i] * a[i];
        norm_b += b[i] * b[i];
    }

    const float denom = std::sqrt(norm_a) * std::sqrt(norm_b);
    if (denom < 1e-10f) return 0.0f;

    return dot / denom;
}

void normalize_embedding(float* vec, size_t dim) {
    if (dim == 0) return;

    float norm = 0.0f;
    for (size_t i = 0; i < dim; ++i) {
        norm += vec[i] * vec[i];
    }

    norm = std::sqrt(norm);
    if (norm < 1e-10f) return;

    const float inv_norm = 1.0f / norm;
    for (size_t i = 0; i < dim; ++i) {
        vec[i] *= inv_norm;
    }
}

void batch_normalize(float* data, size_t num_vectors, size_t dim) {
    if (!data || num_vectors == 0 || dim == 0) return;

    for (size_t v = 0; v < num_vectors; ++v) {
        normalize_embedding(data + v * dim, dim);
    }
}

void similarity_matrix(
    const float* a, size_t num_a,
    const float* b, size_t num_b,
    size_t dim,
    float* result
) {
    if (!a || !b || !result || num_a == 0 || num_b == 0 || dim == 0) {
        return;
    }

    for (size_t i = 0; i < num_a; ++i) {
        for (size_t j = 0; j < num_b; ++j) {
            result[i * num_b + j] = cosine_similarity(
                a + i * dim,
                b + j * dim,
                dim
            );
        }
    }
}

} // namespace rag_native
