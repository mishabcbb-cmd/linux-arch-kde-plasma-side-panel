"""
agent/rag.py — RAG (Retrieval-Augmented Generation) engine for the KDE AI Agent.

Provides semantic search, cross-session memory, and documentation indexing
using ChromaDB with Ollama embeddings (primary) and sentence-transformers (fallback).

Collections:
  - codebase: Source code indexing (all project files, chunked by paragraph)
  - memory: Cross-session facts (agent-saved facts with tags)
  - docs: Documentation (manual uploads, markdown, PDF)

Patterns from:
  - Aider (repomap caching with SQLite)
  - OpenCode (internal/db/ for session persistence)
"""

import json
import logging
import os
import re
import threading
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# ============================================================================
# Embedding Functions
# ============================================================================


try:
    from chromadb.api.types import Documents, EmbeddingFunction, Embeddings
    HAS_CHROMADB_TYPES = True
except ImportError:
    HAS_CHROMADB_TYPES = False
    # Define fallback types for when chromadb is not installed
    Documents = List[str]
    Embeddings = List[List[float]]


class OllamaEmbeddingFunction(EmbeddingFunction[Documents]):
    """Embedding function using Ollama's nomic-embed-text model."""

    def __init__(self, host: str = "http://localhost:11434", model: str = "nomic-embed-text"):
        self.host = host.rstrip("/")
        self.model = model

    def __call__(self, input: Documents) -> Embeddings:
        """Generate embeddings for a list of texts."""
        import urllib.request

        embeddings = []
        for text in input:
            try:
                payload = json.dumps({
                    "model": self.model,
                    "prompt": text,
                }).encode("utf-8")
                req = urllib.request.Request(
                    f"{self.host}/api/embeddings",
                    data=payload,
                    headers={"Content-Type": "application/json"},
                )
                with urllib.request.urlopen(req, timeout=30) as resp:
                    result = json.loads(resp.read())
                    embeddings.append(result.get("embedding", []))
            except Exception as exc:
                logger.warning(f"Ollama embedding failed: {exc}")
                embeddings.append([0.0] * 768)  # Fallback zero vector
        return embeddings

    def name(self) -> str:
        return f"ollama-{self.model}"


class SentenceTransformerEmbeddingFunction(EmbeddingFunction[Documents]):
    """Fallback embedding function using sentence-transformers."""

    def __init__(self, model_name: str = "all-MiniLM-L6-v2"):
        self.model_name = model_name
        self._model = None

    def _lazy_load(self):
        if self._model is None:
            try:
                from sentence_transformers import SentenceTransformer
                self._model = SentenceTransformer(self.model_name)
                logger.info(f"Loaded sentence-transformers model: {self.model_name}")
            except ImportError:
                logger.error("sentence-transformers not installed")
                raise

    def __call__(self, input: Documents) -> Embeddings:
        self._lazy_load()
        if self._model is None:
            return [[0.0] * 384 for _ in input]
        embeddings = self._model.encode(input, show_progress_bar=False)
        return embeddings.tolist()

    def name(self) -> str:
        return f"sentence-transformers-{self.model_name}"


class HybridEmbeddingFunction(EmbeddingFunction[Documents]):
    """Hybrid embedding: try Ollama first, fall back to sentence-transformers."""

    def __init__(
        self,
        ollama_host: str = "http://localhost:11434",
        ollama_model: str = "nomic-embed-text",
        fallback_model: str = "all-MiniLM-L6-v2",
    ):
        self._primary = OllamaEmbeddingFunction(ollama_host, ollama_model)
        self._fallback = SentenceTransformerEmbeddingFunction(fallback_model)

    def __call__(self, input: Documents) -> Embeddings:
        try:
            return self._primary(input)
        except Exception:
            logger.warning("Ollama embedding failed, using sentence-transformers fallback")
            return self._fallback(input)

    def name(self) -> str:
        return f"hybrid-{self._primary.model}-{self._fallback.model_name}"


# ============================================================================
# Chunking
# ============================================================================


def chunk_text(text: str, chunk_size: int = 512, overlap: int = 64) -> List[str]:
    """Split text into overlapping chunks at paragraph/sentence boundaries."""
    if not text:
        return []

    # Split by paragraphs first
    paragraphs = re.split(r"\n\s*\n", text)
    chunks = []
    current_chunk = ""

    for para in paragraphs:
        para = para.strip()
        if not para:
            continue

        if len(current_chunk) + len(para) + 1 <= chunk_size:
            current_chunk = (current_chunk + "\n\n" + para).strip()
        else:
            if current_chunk:
                chunks.append(current_chunk)
            # If paragraph is longer than chunk_size, split at sentence boundaries
            if len(para) > chunk_size:
                sentences = re.split(r"(?<=[.!?])\s+", para)
                current_chunk = ""
                for sent in sentences:
                    if len(current_chunk) + len(sent) + 1 <= chunk_size:
                        current_chunk = (current_chunk + " " + sent).strip()
                    else:
                        if current_chunk:
                            chunks.append(current_chunk)
                        current_chunk = sent
                if current_chunk:
                    chunks.append(current_chunk)
                    current_chunk = ""
            else:
                current_chunk = para

    if current_chunk:
        chunks.append(current_chunk)

    # Apply overlap
    if overlap > 0 and len(chunks) > 1:
        overlapped = []
        for i, chunk in enumerate(chunks):
            if i > 0:
                prev_end = chunks[i - 1][-overlap:]
                chunk = prev_end + chunk
            overlapped.append(chunk)
        return overlapped

    return chunks


# ============================================================================
# RAG Engine
# ============================================================================


@dataclass
class SearchResult:
    """A single search result from a RAG collection."""

    content: str
    metadata: Dict[str, Any]
    distance: float
    collection: str


class RAGEngine:
    """RAG engine using ChromaDB for vector storage and retrieval.

    Manages 3 collections:
      - codebase: Source code indexing
      - memory: Cross-session facts
      - docs: Documentation
    """

    def __init__(
        self,
        persist_directory: str = "~/.local/share/kde-ai-agent/chromadb",
        ollama_host: str = "http://localhost:11434",
    ):
        self.persist_directory = os.path.expanduser(persist_directory)
        self._embedding_fn = HybridEmbeddingFunction(ollama_host=ollama_host)
        self._client = None
        self._collections: Dict[str, Any] = {}
        self._lock = threading.Lock()
        self._initialized = False

    def initialize(self) -> bool:
        """Initialize ChromaDB client and create/get collections."""
        if self._initialized:
            return True

        try:
            import chromadb
            self._client = chromadb.PersistentClient(path=self.persist_directory)

            # Create/get collections
            collection_names = ["codebase", "memory", "docs"]
            for name in collection_names:
                try:
                    collection = self._client.get_or_create_collection(
                        name=name,
                        embedding_function=self._embedding_fn,
                    )
                    self._collections[name] = collection
                except Exception as exc:
                    logger.error(f"Failed to create collection '{name}': {exc}")
                    return False

            self._initialized = True
            logger.info(f"RAG engine initialized: {self.persist_directory}")
            return True

        except ImportError:
            logger.error("chromadb not installed. Install with: pip install chromadb")
            return False
        except Exception as exc:
            logger.error(f"Failed to initialize RAG engine: {exc}")
            return False

    # ========================================================================
    # Codebase Indexing
    # ========================================================================

    def index_codebase(
        self,
        root_dir: str,
        file_patterns: Optional[List[str]] = None,
        max_file_size: int = 1_048_576,  # 1MB
    ) -> int:
        """Index source code files into the codebase collection.

        Returns the number of chunks indexed.
        """
        if not self._initialized:
            if not self.initialize():
                return 0

        collection = self._collections.get("codebase")
        if not collection:
            return 0

        root = Path(root_dir).expanduser().resolve()
        if not root.exists():
            logger.error(f"Directory not found: {root}")
            return 0

        # Default patterns: all common source files
        patterns = file_patterns or [
            "*.py", "*.qml", "*.js", "*.ts", "*.go", "*.rs",
            "*.cpp", "*.cxx", "*.cc", "*.h", "*.hpp",
            "*.md", "*.json", "*.yaml", "*.yml", "*.toml",
            "*.sh", "*.cmake", "*.xml", "*.txt",
        ]

        # Read .gitignore patterns
        gitignore_patterns = self._load_gitignore(root)

        total_chunks = 0
        for pattern in patterns:
            for file_path in root.rglob(pattern):
                # Skip .gitignore'd files
                rel_path = file_path.relative_to(root)
                if self._is_ignored(str(rel_path), gitignore_patterns):
                    continue

                # Skip large files
                if file_path.stat().st_size > max_file_size:
                    continue

                try:
                    content = file_path.read_text(encoding="utf-8", errors="replace")
                    chunks = chunk_text(content)
                    file_id = str(rel_path)

                    # Add chunks to collection
                    for i, chunk in enumerate(chunks):
                        chunk_id = f"{file_id}#chunk{i}"
                        collection.add(
                            ids=[chunk_id],
                            documents=[chunk],
                            metadatas=[{
                                "source": file_id,
                                "chunk": i,
                                "total_chunks": len(chunks),
                                "type": "code",
                            }],
                        )
                    total_chunks += len(chunks)

                except Exception as exc:
                    logger.debug(f"Skipping {file_path}: {exc}")

        logger.info(f"Indexed {total_chunks} chunks from {root}")
        return total_chunks

    def _load_gitignore(self, root: Path) -> List[str]:
        """Load .gitignore patterns."""
        gitignore_path = root / ".gitignore"
        patterns = []
        if gitignore_path.exists():
            try:
                for line in gitignore_path.read_text().splitlines():
                    line = line.strip()
                    if line and not line.startswith("#"):
                        patterns.append(line)
            except Exception:
                pass
        return patterns

    def _is_ignored(self, path: str, patterns: List[str]) -> bool:
        """Check if a path matches .gitignore patterns."""
        for pattern in patterns:
            if pattern.endswith("/"):
                if path.startswith(pattern) or f"/{pattern}" in path:
                    return True
            elif pattern.startswith("*"):
                if path.endswith(pattern[1:]):
                    return True
            elif pattern in path:
                return True
        return False

    # ========================================================================
    # Memory Operations
    # ========================================================================

    def store_memory(
        self,
        content: str,
        tags: Optional[List[str]] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Optional[str]:
        """Store a fact in the memory collection.

        Returns the memory ID if successful.
        """
        if not self._initialized:
            if not self.initialize():
                return None

        collection = self._collections.get("memory")
        if not collection:
            return None

        import uuid
        memory_id = str(uuid.uuid4())

        meta = {
            "tags": json.dumps(tags or []),
            "type": "memory",
        }
        if metadata:
            meta.update(metadata)

        try:
            collection.add(
                ids=[memory_id],
                documents=[content],
                metadatas=[meta],
            )
            return memory_id
        except Exception as exc:
            logger.error(f"Failed to store memory: {exc}")
            return None

    def recall_memory(
        self,
        query: str,
        n_results: int = 5,
        tags: Optional[List[str]] = None,
    ) -> List[SearchResult]:
        """Search the memory collection for relevant facts."""
        if not self._initialized:
            if not self.initialize():
                return []

        collection = self._collections.get("memory")
        if not collection:
            return []

        try:
            where = None
            if tags:
                where = {"tags": {"$contains": json.dumps(tags)}}

            results = collection.query(
                query_texts=[query],
                n_results=n_results,
                where=where,
            )

            return self._format_results(results, "memory")
        except Exception as exc:
            logger.error(f"Failed to recall memory: {exc}")
            return []

    # ========================================================================
    # Semantic Search
    # ========================================================================

    def semantic_search(
        self,
        query: str,
        collection_name: str = "codebase",
        n_results: int = 10,
    ) -> List[SearchResult]:
        """Search a collection by semantic similarity."""
        if not self._initialized:
            if not self.initialize():
                return []

        collection = self._collections.get(collection_name)
        if not collection:
            logger.warning(f"Collection not found: {collection_name}")
            return []

        try:
            results = collection.query(
                query_texts=[query],
                n_results=n_results,
            )
            return self._format_results(results, collection_name)
        except Exception as exc:
            logger.error(f"Semantic search failed: {exc}")
            return []

    # ========================================================================
    # Document Indexing
    # ========================================================================

    def index_document(
        self,
        content: str,
        doc_id: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> int:
        """Index a document into the docs collection.

        Returns the number of chunks indexed.
        """
        if not self._initialized:
            if not self.initialize():
                return 0

        collection = self._collections.get("docs")
        if not collection:
            return 0

        chunks = chunk_text(content)
        meta = metadata or {}

        try:
            for i, chunk in enumerate(chunks):
                chunk_id = f"{doc_id}#chunk{i}"
                collection.add(
                    ids=[chunk_id],
                    documents=[chunk],
                    metadatas=[{
                        **meta,
                        "source": doc_id,
                        "chunk": i,
                        "total_chunks": len(chunks),
                        "type": "document",
                    }],
                )
            return len(chunks)
        except Exception as exc:
            logger.error(f"Failed to index document: {exc}")
            return 0

    # ========================================================================
    # Helpers
    # ========================================================================

    def _format_results(
        self,
        results: Any,
        collection_name: str,
    ) -> List[SearchResult]:
        """Format ChromaDB query results into SearchResult objects."""
        formatted = []
        try:
            ids = results.get("ids", [[]])[0]
            documents = results.get("documents", [[]])[0]
            distances = results.get("distances", [[]])[0]
            metadatas = results.get("metadatas", [[]])[0]

            for i in range(len(ids)):
                formatted.append(SearchResult(
                    content=documents[i] if i < len(documents) else "",
                    metadata=metadatas[i] if i < len(metadatas) else {},
                    distance=distances[i] if i < len(distances) else 0.0,
                    collection=collection_name,
                ))
        except Exception as exc:
            logger.error(f"Failed to format results: {exc}")

        return formatted

    def get_collection_stats(self) -> Dict[str, int]:
        """Get statistics for all collections."""
        stats = {}
        for name, collection in self._collections.items():
            try:
                stats[name] = collection.count()
            except Exception:
                stats[name] = 0
        return stats

    def close(self) -> None:
        """Close the RAG engine."""
        self._collections.clear()
        self._client = None
        self._initialized = False
