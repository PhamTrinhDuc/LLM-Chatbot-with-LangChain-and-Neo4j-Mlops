"""Document loader for PDF processing with text cleaning capabilities."""

import re
from pathlib import Path
from typing import List

from langchain.schema import Document
from langchain_community.document_loaders import PyPDFLoader


class DocumentLoader:
    """Handle document preprocessing and cleaning with improved error handling."""
    
    def __init__(self, min_doc_length: int = 50):
        """
        Initialize DocumentLoader.
        
        Args:
            min_doc_length: Minimum length for documents to be processed
        """
        self.min_doc_length = min_doc_length
    
    def _clean_text(self, text: str) -> str:
        """
        Clean and normalize text.
        
        Args:
            text: Raw text to clean
            
        Returns:
            Cleaned and normalized text
        """
        if not text or not isinstance(text, str):
            return ""
            
        # Remove extra whitespace
        text = re.sub(r'\s+', ' ', text)
        # Remove special characters but keep Vietnamese
        text = re.sub(r'[^\w\s\u00C0-\u1EF9.,;:!?()-]', '', text)
        return text.strip().lower()
    
    def _process_documents(self, documents: List[Document]) -> List[Document]:
        """
        Process list of documents with cleaning and validation.
        
        Args:
            documents: List of raw documents
            
        Returns:
            List of processed documents
        """
        if not documents:
            print("Warning: No documents provided for processing")
            return []
            
        processed_docs = []
        skipped_count = 0
        
        for i, doc in enumerate(documents):
            if not doc or not hasattr(doc, 'page_content'):
                print(f"Warning: Skipping invalid document at index {i}")
                skipped_count += 1
                continue
                
            # Clean content
            cleaned_content = self._clean_text(doc.page_content)
            
            # Skip empty or too short documents
            if len(cleaned_content) < self.min_doc_length:
                skipped_count += 1
                continue
            
            # Create new document with cleaned content
            processed_doc = Document(
                page_content=cleaned_content,
                metadata={
                    **(doc.metadata or {}),
                    'processed': True,
                    'original_length': len(doc.page_content),
                    'cleaned_length': len(cleaned_content),
                    'document_index': i
                }
            )
            processed_docs.append(processed_doc)
        
        print(f"Processed {len(processed_docs)} documents, skipped {skipped_count}")
        return processed_docs
    
    def load_pdf(self, pdf_path: str) -> List[Document]:
        """
        Load and preprocess PDF documents with validation.
        
        Args:
            pdf_path: Path to PDF file
            
        Returns:
            List of processed documents
            
        Raises:
            FileNotFoundError: If PDF file doesn't exist
            ValueError: If file is not a PDF or no content extracted
        """
        pdf_file = Path(pdf_path)
        
        # Validate file exists
        if not pdf_file.exists():
            raise FileNotFoundError(f"PDF file not found: {pdf_path}")
            
        # Validate file extension
        if pdf_file.suffix.lower() != '.pdf':
            raise ValueError(f"File is not a PDF: {pdf_path}")
        
        print(f"Loading PDF: {pdf_path}")
        loader = PyPDFLoader(str(pdf_file))
        documents = loader.load()
        
        if not documents:
            raise ValueError(f"No content extracted from PDF: {pdf_path}")
            
        print(f"Loaded {len(documents)} raw documents from PDF")
        
        # Process documents
        processed_docs = self._process_documents(documents)
        
        if not processed_docs:
            raise ValueError(f"No valid documents after processing: {pdf_path}")
            
        print(f"Successfully processed {len(processed_docs)} documents")
        return processed_docs
    
    def get_stats(self, documents: List[Document]) -> dict:
        """
        Get statistics about processed documents.
        
        Args:
            documents: List of documents
            
        Returns:
            Dictionary with document statistics
        """
        if not documents:
            return {"total_docs": 0}
            
        total_length = sum(len(doc.page_content) for doc in documents)
        avg_length = total_length / len(documents)
        
        return {
            "total_docs": len(documents),
            "total_length": total_length,
            "average_length": round(avg_length, 2),
            "min_length": min(len(doc.page_content) for doc in documents),
            "max_length": max(len(doc.page_content) for doc in documents)
        }