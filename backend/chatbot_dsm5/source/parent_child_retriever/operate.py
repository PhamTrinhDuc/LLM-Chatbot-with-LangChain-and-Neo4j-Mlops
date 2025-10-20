"""Main operation script for document ingestion and testing."""

import os
import sys
from pathlib import Path
from typing import List

sys.path.append(os.path.join(os.path.dirname(__file__), ".."))

from dotenv import load_dotenv
from langchain_openai import OpenAIEmbeddings
from langchain.schema import Document

from loader import DocumentLoader
from parent_child_retriever.retriever import DocumentRetriever

# Load environment variables
load_dotenv('.env.dev')

# Configuration
PDF_PATH = "/home/ducpham/workspace/LLM-Chatbot-with-LangChain-and-Neo4j/data/dsm-5-cac-tieu-chuan-chan-doan.pdf"
COLLECTION_NAME = "chatbot-dsm5"


def setup_retriever() -> DocumentRetriever:
    """Setup and return DocumentRetriever instance."""
    print("=== Setting up DocumentRetriever ===")
    
    # Ensure directories exist
    os.makedirs("./chroma_db", exist_ok=True)
    os.makedirs("./docstore", exist_ok=True)
    
    retriever = DocumentRetriever(
        collection_name=COLLECTION_NAME,
        embedding_function=OpenAIEmbeddings(),
        persist_directory="./chroma_db",
        store_type="local",
        store_path="./docstore/chunks.db",
        chunk_size=400,
        chunk_overlap=50
    )
    
    # Display configuration
    config = retriever.get_config()
    print("Configuration:")
    for key, value in config.items():
        print(f"  {key}: {value}")
    
    return retriever


def load_documents() -> List[Document]:
    """Load documents from PDF."""
    print("\n=== Loading Documents ===")
    
    # Check if PDF exists
    if not Path(PDF_PATH).exists():
        raise FileNotFoundError(f"PDF file not found at {PDF_PATH}")
    
    # Load documents
    loader = DocumentLoader(min_doc_length=100)
    docs = loader.load_pdf(pdf_path=PDF_PATH)
    
    # Show document statistics
    stats = loader.get_stats(docs)
    print(f"Document Statistics:")
    for key, value in stats.items():
        print(f"  {key}: {value}")
    
    return docs


def ingest_documents(retriever: DocumentRetriever, docs: List[Document]):
    """Ingest documents into the retriever."""
    print("\n=== Ingesting Documents ===")
    
    # Get the ParentDocumentRetriever and add documents
    parent_retriever = retriever.create_retriever()
    parent_retriever.add_documents(docs)
    
    print(f"Successfully ingested {len(docs)} documents")


def test_retrieval(retriever: DocumentRetriever):
    """Test document retrieval functionality."""
    print("\n=== Testing Document Retrieval ===")
    
    test_queries = [
        "Tác giả của bài viết là ai",
        "triệu chứng của bệnh tâm thần",
        "chẩn đoán rối loạn tâm lý",
        "điều trị bệnh nhân"
    ]
    
    parent_retriever = retriever.create_retriever()
    
    for query in test_queries:
        print(f"\nQuery: '{query}'")
        print("-" * 60)
        
        try:
            # Use the retriever to get relevant documents
            results = parent_retriever.get_relevant_documents(query)
            
            if not results:
                print("No documents found for this query.")
                continue
                
            for i, doc in enumerate(results[:3], 1):  # Show top 3 results
                print(f"\nResult {i}:")
                print(f"Content: {doc.page_content}")
                if doc.metadata:
                    print(f"Metadata: {doc.metadata}")
                print("-" * 40)
                
        except Exception as e:
            print(f"Retrieval error for query '{query}': {e}")


def test_vectorstore_search(retriever: DocumentRetriever):
    """Test direct vectorstore search."""
    print("\n=== Testing Vectorstore Search ===")
    
    vectorstore = retriever.get_vectorstore()
    
    test_query = "triệu chứng bệnh tâm thần"
    print(f"\nDirect vectorstore search for: '{test_query}'")
    
    try:
        results = vectorstore.similarity_search(test_query, k=3)
        
        for i, doc in enumerate(results, 1):
            print(f"\nResult {i}:")
            print(f"Content: {doc.page_content}")
                
    except Exception as e:
        print(f"Vectorstore search error: {e}")


def main():
    """Main execution function."""
    print("Starting DSM-5 Document Processing Pipeline...")
    print("=" * 60)
    
    try:
        # Setup retriever
        retriever = setup_retriever()
        
        # Load documents
        docs = load_documents()
        
        # # Ingest documents
        ingest_documents(retriever, docs)
        
        # Test retrieval functionality
        test_retrieval(retriever)
        
        # Test direct vectorstore search
        # test_vectorstore_search(retriever)
        
        print("\n" + "=" * 60)
        print("Pipeline completed successfully!")
        
    except Exception as e:
        print(f"\nError in pipeline: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
