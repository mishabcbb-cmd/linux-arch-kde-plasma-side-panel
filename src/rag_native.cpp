/**
 * src/rag_native.cpp — pybind11 module for fast RAG operations.
 *
 * Exposes C++ optimized functions to Python:
 *   - cosine_similarity(a, b) → float
 *   - normalize_embedding(vec) → list[float]
 *   - batch_normalize(vectors) → list[list[float]]
 *   - similarity_matrix(a, b) → list[list[float]]
 *   - count_tokens(text) → int
 *   - chunk_text(text, chunk_size, overlap) → list[str]
 *
 * Compiled with GCC 16 + pybind11.
 */

#include <pybind11/pybind11.h>
#include <pybind11/stl.h>
#include <pybind11/numpy.h>

#include "rag_native.h"

namespace py = pybind11;
namespace rn = rag_native;

// ── NumPy-aware wrappers ──

py::array_t<float> py_cosine_similarity(
    py::array_t<float> a,
    py::array_t<float> b
) {
    auto buf_a = a.request();
    auto buf_b = b.request();

    if (buf_a.ndim != 1 || buf_b.ndim != 1) {
        throw std::runtime_error("Both inputs must be 1-D arrays");
    }
    if (buf_a.size != buf_b.size) {
        throw std::runtime_error("Vectors must have same dimension");
    }

    float* ptr_a = static_cast<float*>(buf_a.ptr);
    float* ptr_b = static_cast<float*>(buf_b.ptr);
    size_t dim = buf_a.size;

    float result = rn::cosine_similarity(ptr_a, ptr_b, dim);
    return py::array_t<float>({1}, &result);
}

py::array_t<float> py_normalize_embedding(py::array_t<float> vec) {
    auto buf = vec.request();
    if (buf.ndim != 1) {
        throw std::runtime_error("Input must be 1-D array");
    }

    auto result = py::array_t<float>(buf.size);
    auto buf_out = result.request();

    float* ptr_in = static_cast<float*>(buf.ptr);
    float* ptr_out = static_cast<float*>(buf_out.ptr);

    std::copy(ptr_in, ptr_in + buf.size, ptr_out);
    rn::normalize_embedding(ptr_out, buf.size);

    return result;
}

py::array_t<float> py_batch_normalize(py::array_t<float> data, size_t dim) {
    auto buf = data.request();
    if (buf.size % dim != 0) {
        throw std::runtime_error("Data size must be divisible by dim");
    }

    size_t num_vectors = buf.size / dim;
    auto result = py::array_t<float>(buf.size);
    auto buf_out = result.request();

    float* ptr_in = static_cast<float*>(buf.ptr);
    float* ptr_out = static_cast<float*>(buf_out.ptr);

    std::copy(ptr_in, ptr_in + buf.size, ptr_out);
    rn::batch_normalize(ptr_out, num_vectors, dim);

    return result;
}

py::array_t<float> py_similarity_matrix(
    py::array_t<float> a,
    py::array_t<float> b,
    size_t dim
) {
    auto buf_a = a.request();
    auto buf_b = b.request();

    if (buf_a.size % dim != 0 || buf_b.size % dim != 0) {
        throw std::runtime_error("Data sizes must be divisible by dim");
    }

    size_t num_a = buf_a.size / dim;
    size_t num_b = buf_b.size / dim;

    auto result = py::array_t<float>({num_a, num_b});
    auto buf_out = result.request();

    rn::similarity_matrix(
        static_cast<float*>(buf_a.ptr), num_a,
        static_cast<float*>(buf_b.ptr), num_b,
        dim,
        static_cast<float*>(buf_out.ptr)
    );

    return result;
}


// ── Module definition ──

PYBIND11_MODULE(rag_native, m) {
    m.doc() = "KDE AI Agent — Native RAG operations (GCC 16 optimized)";

    // Embedding operations
    m.def("cosine_similarity", &py_cosine_similarity,
        py::arg("a"), py::arg("b"),
        "Compute cosine similarity between two embedding vectors");

    m.def("normalize_embedding", &py_normalize_embedding,
        py::arg("vec"),
        "L2-normalize an embedding vector");

    m.def("batch_normalize", &py_batch_normalize,
        py::arg("data"), py::arg("dim"),
        "Batch normalize multiple embeddings");

    m.def("similarity_matrix", &py_similarity_matrix,
        py::arg("a"), py::arg("b"), py::arg("dim"),
        "Compute cosine similarity matrix between two sets of embeddings");

    // Text operations
    m.def("count_tokens", &rn::count_tokens,
        py::arg("text"),
        "Approximate UTF-8 token count (~4 chars/token for ASCII)");

    m.def("chunk_text", &rn::chunk_text,
        py::arg("text"),
        py::arg("chunk_size") = 512,
        py::arg("overlap") = 64,
        "Split text into overlapping chunks at sentence boundaries");

    // Version info
    m.attr("__version__") = "0.1.0";
    m.attr("__gcc_version__") = __VERSION__;
}
