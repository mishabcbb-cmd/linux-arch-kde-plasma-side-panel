#pragma once
/**
 * src/rag_native.h — C++ native RAG module header.
 *
 * Provides fast cosine similarity, embedding normalization,
 * and token counting for the KDE AI Agent RAG engine.
 *
 * Compiled with GCC 16 + pybind11 for Python integration.
 */

#include <cmath>
#include <cstdint>
#include <string>
#include <vector>

namespace rag_native {

/**
 * Compute cosine similarity between two embedding vectors.
 * Returns value in [-1.0, 1.0].
 */
float cosine_similarity(const float* a, const float* b, size_t dim);

/**
 * Normalize an embedding vector in-place (L2 normalization).
 */
void normalize_embedding(float* vec, size_t dim);

/**
 * Batch normalize multiple embeddings.
 */
void batch_normalize(float* data, size_t num_vectors, size_t dim);

/**
 * Compute cosine similarity matrix between two sets of embeddings.
 * result[i * num_b + j] = cosine_similarity(a[i], b[j])
 */
void similarity_matrix(
    const float* a, size_t num_a,
    const float* b, size_t num_b,
    size_t dim,
    float* result
);

/**
 * Simple UTF-8 token counter (approximate).
 * Returns estimated token count for a text string.
 * Uses a simple heuristic: ~4 chars per token for ASCII, ~2 for CJK.
 */
size_t count_tokens(const std::string& text);

/**
 * Chunk text into overlapping segments at sentence boundaries.
 * Returns vector of chunk strings.
 */
std::vector<std::string> chunk_text(
    const std::string& text,
    size_t chunk_size = 512,
    size_t overlap = 64
);

} // namespace rag_native
