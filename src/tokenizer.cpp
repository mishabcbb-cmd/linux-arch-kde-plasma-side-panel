/**
 * src/tokenizer.cpp — Fast UTF-8 token counting and text chunking.
 *
 * Provides approximate token counting (no model dependency) and
 * sentence-boundary-aware text chunking for the RAG pipeline.
 */

#include "rag_native.h"
#include <algorithm>
#include <cstring>
#include <vector>

namespace rag_native {

size_t count_tokens(const std::string& text) {
    size_t count = 0;
    const unsigned char* str = reinterpret_cast<const unsigned char*>(text.data());
    size_t len = text.length();

    for (size_t i = 0; i < len; ++count) {
        unsigned char c = str[i];
        if (c < 0x80) {
            // ASCII: ~4 chars per token
            i += 1;
        } else if (c < 0xC0) {
            // Continuation byte — skip
            i += 1;
        } else if (c < 0xE0) {
            // 2-byte UTF-8: ~2 chars per token
            i += 2;
        } else if (c < 0xF0) {
            // 3-byte UTF-8: ~1 char per token (CJK)
            i += 3;
        } else {
            // 4-byte UTF-8
            i += 4;
        }
    }

    // Heuristic: ASCII ~4 chars/token, CJK ~1.5 chars/token
    // For mixed text, use weighted average
    return std::max(size_t(1), count / 4 + 1);
}

std::vector<std::string> chunk_text(
    const std::string& text,
    size_t chunk_size,
    size_t overlap
) {
    std::vector<std::string> chunks;
    if (text.empty()) return chunks;

    // Split by paragraphs first
    std::vector<std::string> paragraphs;
    size_t start = 0;
    while (start < text.length()) {
        size_t end = text.find("\n\n", start);
        if (end == std::string::npos) {
            paragraphs.push_back(text.substr(start));
            break;
        }
        paragraphs.push_back(text.substr(start, end - start));
        start = end + 2;
    }

    std::string current;
    for (const auto& para : paragraphs) {
        if (para.empty()) continue;

        if (current.length() + para.length() + 2 <= chunk_size) {
            if (!current.empty()) current += "\n\n";
            current += para;
        } else {
            if (!current.empty()) {
                chunks.push_back(current);
            }

            // Long paragraph — split at sentence boundaries
            if (para.length() > chunk_size) {
                std::string temp;
                size_t sent_start = 0;
                while (sent_start < para.length()) {
                    size_t sent_end = para.find_first_of(".!?", sent_start);
                    if (sent_end == std::string::npos) {
                        sent_end = para.length();
                    } else {
                        sent_end += 1; // Include punctuation
                    }

                    std::string sentence = para.substr(sent_start, sent_end - sent_start);
                    if (temp.length() + sentence.length() + 1 <= chunk_size) {
                        if (!temp.empty()) temp += " ";
                        temp += sentence;
                    } else {
                        if (!temp.empty()) chunks.push_back(temp);
                        temp = sentence;
                    }
                    sent_start = sent_end;
                }
                if (!temp.empty()) current = temp;
                else current.clear();
            } else {
                current = para;
            }
        }
    }

    if (!current.empty()) {
        chunks.push_back(current);
    }

    // Apply overlap
    if (overlap > 0 && chunks.size() > 1) {
        for (size_t i = 1; i < chunks.size(); ++i) {
            const std::string& prev = chunks[i - 1];
            size_t overlap_start = (prev.length() > overlap)
                ? prev.length() - overlap
                : 0;
            chunks[i] = prev.substr(overlap_start) + chunks[i];
        }
    }

    return chunks;
}

} // namespace rag_native
