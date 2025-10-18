"""Document ingestion module for DSM-5 chatbot with modular architecture."""

# Main classes
from .loader import DocumentLoader
from .retriever import DocumentIngester

# Configuration
from .config import (
    IngesterConfig,
    VectorStoreConfig,
    DocumentStoreConfig,
    ChunkingConfig,
    DEFAULT_CONFIG
)

# Components (for advanced usage)
from .vector_store import ChromaVectorStore
from .document_store import DocumentStoreFactory, LocalDocumentStore, MemoryDocumentStore
from .retriever import ParentChildRetriever
from .chunker import TextChunker

# Base classes (for custom implementations)
from .base import BaseVectorStore, BaseDocumentStore, BaseRetriever

__all__ = [
    # Main API
    "DocumentLoader",
    "DocumentIngester",
    
    # Configuration
    "IngesterConfig",
    "VectorStoreConfig", 
    "DocumentStoreConfig",
    "ChunkingConfig",
    "DEFAULT_CONFIG",
    
    # Components
    "ChromaVectorStore",
    "DocumentStoreFactory",
    "LocalDocumentStore",
    "MemoryDocumentStore", 
    "ParentChildRetriever",
    "TextChunker",
    
    # Base classes
    "BaseVectorStore",
    "BaseDocumentStore",
    "BaseRetriever"
]