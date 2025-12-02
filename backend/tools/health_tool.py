import os
import sys
import threading
sys.path.append(os.path.join(os.path.dirname(__file__), ".."))
from langchain.tools import BaseTool
from chains.healthcare_chain import HealthcareRetriever
from utils import logger


class DSM5RetrievalTool(BaseTool):
  """
  Tool for retrieving DSM-5 diagnostic criteria and clinical information.
  
  Uses HealthcareRetriever to perform hybrid search (keyword + semantic)
  on DSM-5 chunks indexed in Elasticsearch.
  
  Supports:
  - Finding diagnostic criteria for psychiatric disorders
  - Querying clinical information and diagnostic features
  - Searching related information using hierarchical structure
  - Differential diagnosis information
  """
  name: str = "DSM5_Retriever"
  
  description: str = """Tool for querying DSM-5 diagnostic criteria and clinical information.
  Use cases:
  - Find diagnostic criteria for a disorder (e.g., "Diagnostic criteria for autism spectrum disorder")
  - Query clinical features and severity levels (e.g., "Diagnostic features of depression")
  - Search differential diagnosis (e.g., "Differentiate anxiety disorder from panic disorder")
  - Find related psychiatric disorder information
  
  Input: Query about DSM-5 (e.g., "Severe autism spectrum disorder criteria")
  Output: List of relevant sections with detailed diagnostic information
  """
    
  class Config:
      extra = "allow"  # Allow adding new attributes after init
  
  
  def __init__(
    self,
    embedding_model: str = "google",  # "google" or "openai"
    top_k: int = 5,
    include_context: bool = True,
  ):
    """
    Initialize DSM5RetrievalTool.
    
    Args:
        embedding_model: Embedding model to use ("google" or "openai")
        top_k: Number of top results to return (default: 5)
        include_context: Whether to include related sections
        debug: Whether to print debug information
    """
    super().__init__()
    
    self._retriever = None
    self.embedding_model = embedding_model
    self.top_k = top_k
    self.include_context = include_context

  @property
  def retriever(self): 
    if not self._retriever: 
      with threading.Lock():
        self._retriever = HealthcareRetriever(model_name=self.embedding_model)
    return self._retriever
    
  def _run(self, query: str) -> str:
    """
    Synchronous execution of DSM-5 retrieval.
    
    Args:
      query: User's question about DSM-5
        (e.g., "What are the diagnostic criteria for autism spectrum disorder?")
  
    Returns:
        Formatted text with relevant DSM-5 diagnostic information
    """
    try:
      # Perform hybrid search
      results = self.retriever.invoke(
          query=query,
          config={
              "top_k": self.top_k,
              "include_context": self.include_context,
          }
      )
      return results
        
    except Exception as e:
      error_msg = f"DSM5RetrievalTool error: {str(e)}"
      logger.error(error_msg)
      return f"Error retrieving DSM-5 information: {str(e)}"
  
  async def _arun(self, query: str) -> str:
      """
      Asynchronous execution of DSM-5 retrieval.
      
      Args:
          query: User's question about DSM-5
          
      Returns:
          Formatted text with relevant DSM-5 diagnostic information
      """
      try:
        # Perform async hybrid search
        results = await self.retriever.ainvoke(
            query=query,
            config={
              "top_k": self.top_k,
              "include_context": self.include_context,
            }
        )
        return results
          
      except Exception as e:
        error_msg = f"DSM5RetrievalTool async error: {str(e)}"
        logger.error(error_msg)
        return f"Error retrieving DSM-5 information: {str(e)}"


