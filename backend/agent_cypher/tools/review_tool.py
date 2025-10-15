import os
import sys
sys.path.append(os.path.join(os.path.dirname(__file__), ".."))
from dotenv import load_dotenv
from langchain.tools import BaseTool

from chains.hospital_review_chain import HospitalReviewChain

load_dotenv(".env.dev")


class ReviewTool(BaseTool):
    """
    Tool for querying patient experiences and reviews using semantic search.
    
    Uses HospitalReviewChain to answer qualitative questions about patient experiences.
    """
    
    name: str = "Experiences"
    description: str = """Useful when you need to answer questions about patient experiences, \
    feelings, or any other qualitative question that could be answered about a patient using \
    semantic search. Not useful for answering objective questions that involve counting, \
    percentages, aggregations, or listing facts. Use the entire prompt as input to the tool. \
    For instance, if the prompt is "Are patients satisfied with their care?", the input should \
    be "Are patients satisfied with their care?"."""

    class Config:
      extra = "allow" # Cho phép tạo thuộc tính mới sau khi init
        
    def __init__(self):
        """Initialize the ReviewTool with a HospitalReviewChain instance."""
        super().__init__()
        self.review_chain = HospitalReviewChain()
    
    def _run(self, query: str) -> dict[str, any]:
        """
        Synchronous execution of review query.
        
        Args:
            query: User's question about patient experiences
            
        Returns:
            Dictionary with 'result' (answer) and 'context' (source documents)
        """
        answer, docs = self.review_chain.invoke(query=query)
        
        return {
            "result": answer,
            "context": "\n".join([doc.page_content for doc in docs])
        }
    
    async def _arun(self, query: str) -> dict[str, any]:
        """
        Asynchronous execution of review query.
        
        Args:
            query: User's question about patient experiences
            
        Returns:
            Dictionary with 'result' (answer) and 'context' (source documents)
        """
        answer, docs = await self.review_chain.ainvoke(query=query)
        
        return {
            "result": answer,
            "context": "\n".join([doc.page_content for doc in docs])
        }

