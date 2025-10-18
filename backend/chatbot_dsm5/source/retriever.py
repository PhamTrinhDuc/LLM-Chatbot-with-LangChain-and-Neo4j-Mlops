"""Document ingester for managing document retrieval with parent-child architecture."""

import os
import sys
from typing import Optional

sys.path.append(os.path.join(os.path.dirname(__file__), ".."))

from langchain.schema import Document, BaseStore
from langchain.storage import InMemoryStore
from langchain_openai import OpenAIEmbeddings
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain.retrievers import ParentDocumentRetriever
from langchain.embeddings.base import Embeddings
from langchain_community.vectorstores import Chroma


import sqlite3
import pickle
from typing import List, Tuple, Optional, Iterator

class SQLiteDocumentStore(BaseStore[str, Document]):
    """SQLite-based document store that implements BaseStore interface"""
    
    def __init__(self, db_path: str):
        self.db_path = db_path
        self.conn = sqlite3.connect(db_path, check_same_thread=False)
        self._create_table()
    
    def _create_table(self):
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS documents (
                key TEXT PRIMARY KEY,
                value BLOB
            )
        """)
        self.conn.commit()
    
    def mget(self, keys: List[str]) -> List[Optional[Document]]:
        results = []
        for key in keys:
            cursor = self.conn.execute(
                "SELECT value FROM documents WHERE key = ?", (key,)
            )
            row = cursor.fetchone()
            if row:
                results.append(pickle.loads(row[0]))
            else:
                results.append(None)
        return results
    
    def mset(self, key_value_pairs: List[Tuple[str, Document]]) -> None:
        for key, value in key_value_pairs:
            self.conn.execute(
                "INSERT OR REPLACE INTO documents (key, value) VALUES (?, ?)",
                (key, pickle.dumps(value))
            )
        self.conn.commit()
    
    def mdelete(self, keys: List[str]) -> None:
        for key in keys:
            self.conn.execute("DELETE FROM documents WHERE key = ?", (key,))
        self.conn.commit()
    
    def yield_keys(self, prefix: Optional[str] = None) -> Iterator[str]:
        """Yield all keys in the store, optionally with a prefix filter"""
        if prefix:
            cursor = self.conn.execute(
                "SELECT key FROM documents WHERE key LIKE ?", (f"{prefix}%",)
            )
        else:
            cursor = self.conn.execute("SELECT key FROM documents")
        
        for row in cursor:
            yield row[0]

class DocumentRetriever:
    """Class for managing document ingestion with parent-child retrieval"""
    
    def __init__(
        self,
        collection_name: str = "bot-dms5",
        embedding_function: Optional[Embeddings] = None,
        persist_directory: str = "./chroma_db",
        store_type: str = "local",
        store_path: str = "./docstore",
        chunk_size: int = 400,
        chunk_overlap: int = 50
    ):
        """
        Initialize DocumentIngester
        
        Args:
            collection_name: Name of the Chroma collection
            embedding_function: Embedding function to use
            persist_directory: Directory for Chroma persistence
            store_type: Type of document store ('local' or 'memory')
            store_path: Path for local file store
            chunk_size: Size of text chunks
            chunk_overlap: Overlap between chunks
        """
        self.collection_name = collection_name
        self.embedding_function = embedding_function or OpenAIEmbeddings()
        self.persist_directory = persist_directory
        self.store_type = store_type.lower()
        self.store_path = store_path
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        
        # Validate store type
        if self.store_type not in ["local", "memory"]:
            raise ValueError(f"Invalid store_type: {store_type}. Must be 'local' or 'memory'")
        
        self._vectorstore = None
        self._docstore = None
        self._retriever = None
    
    def _create_vectorstore(self) -> Chroma:
        """Create Chroma vectorstore instance"""
        if self._vectorstore is None:
            self._vectorstore = Chroma(
                collection_name=self.collection_name,
                embedding_function=self.embedding_function,
                persist_directory=self.persist_directory
            )
        return self._vectorstore
    
    def _create_docstore(self):
        """Create document store based on type"""
        if self._docstore is None:
            if self.store_type == "local":
                # Ensure parent directory exists for SQLite database
                store_dir = os.path.dirname(self.store_path)
                if store_dir and not os.path.exists(store_dir):
                    os.makedirs(store_dir, exist_ok=True)
                    
                print(f"Using SQLite3 storage at: {self.store_path}")
                self._docstore = SQLiteDocumentStore(self.store_path)
            else:
                print("Using InMemoryStore (non-persistent)")
                self._docstore = InMemoryStore()
        return self._docstore
    
    def create_retriever(self) -> ParentDocumentRetriever:
        """
        Create parent document retriever
        
        Returns:
            Configured ParentDocumentRetriever instance
        """
        if self._retriever is None:
            # Create vectorstore and docstore
            vectorstore = self._create_vectorstore()
            docstore = self._create_docstore()
            
            # Create text splitter
            child_splitter = RecursiveCharacterTextSplitter(
                chunk_size=self.chunk_size,
                chunk_overlap=self.chunk_overlap,
                separators=["\n\n", "\n", " ", ""]
            )

            parent_splitter = RecursiveCharacterTextSplitter(
                chunk_size=self.chunk_size*3, 
                chunk_overlap=self.chunk_overlap,
                separators=["\n\n", "\n", " ", ""]
            )
            
            print(f"\nCreating ParentDocumentRetriever with:")
            print(f"  - Collection: {self.collection_name}")
            print(f"  - Chunk size: {self.chunk_size}")
            print(f"  - Chunk overlap: {self.chunk_overlap}")
            print(f"  - Store type: {self.store_type}")
            
            self._retriever = ParentDocumentRetriever(
                vectorstore=vectorstore,
                docstore=docstore,
                child_splitter=child_splitter,
                parent_splitter=parent_splitter
            )
        
        return self._retriever
    
    def get_vectorstore(self) -> Chroma:
        """Get the vectorstore instance"""
        return self._create_vectorstore()
    
    def get_docstore(self):
        """Get the document store instance"""
        return self._create_docstore()
    
    def get_config(self) -> dict:
        """Get current configuration"""
        return {
            "collection_name": self.collection_name,
            "persist_directory": self.persist_directory,
            "store_type": self.store_type,
            "store_path": self.store_path,
            "chunk_size": self.chunk_size,
            "chunk_overlap": self.chunk_overlap,
            "embedding_function": type(self.embedding_function).__name__
        }


if __name__ == "__main__":
    # Example usage
    print("=== Testing DocumentIngester Class ===\n")
    
    # Create ingester instance
    ingester = DocumentRetriever(
        collection_name="test_collection",
        persist_directory="./test_chroma",
        store_type="local",
        store_path="./docstore/chunks.db",
        chunk_size=500,
        chunk_overlap=50
    )
    
    # Display configuration
    config = ingester.get_config()
    print("Configuration:")
    for key, value in config.items():
        print(f"  {key}: {value}")
    
    # Create retriever
    print("\n=== Creating Retriever ===")
    retriever = ingester.create_retriever()
    print(f"\nRetriever created successfully: {type(retriever).__name__}")
    
    # Get components
    vectorstore = ingester.get_vectorstore()
    docstore = ingester.get_docstore()
    print(f"\nComponents:")
    print(f"  - Vectorstore: {type(vectorstore).__name__}")
    print(f"  - Docstore: {type(docstore).__name__}")
