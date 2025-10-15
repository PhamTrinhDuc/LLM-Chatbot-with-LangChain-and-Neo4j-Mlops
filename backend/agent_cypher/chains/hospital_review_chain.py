import os
import sys
sys.path.append(os.path.join(os.path.dirname(__file__), ".."))
from dotenv import load_dotenv
from langchain.chains.retrieval_qa.base import RetrievalQA
from langchain.prompts import ChatPromptTemplate
from langchain_community.vectorstores import Neo4jVector
from langchain_openai import ChatOpenAI, OpenAIEmbeddings

from utils.config import AppConfig

load_dotenv(".env.dev")


class HospitalReviewChain:
    """
    Chain for querying hospital reviews using RAG (Retrieval-Augmented Generation).
    
    Chain type: 'stuff' - Gộp toàn bộ context → gửi 1 prompt duy nhất cho LLM
    Phù hợp khi: Context nhỏ, LLM mạnh
    """
    
    # Constants
    SYSTEM_PROMPT = """
    ##### ROLE #####
    Your job is to use patient reviews to answer questions about their experience at a hospital. 
    Use the following context to answer questions. Be as detailed as possible, but don't make up 
    any information that's not from context. If you don't know an answer, say you don't know.

    ##### CONTEXT #####
    {context}

    ##### LANGUAGE #####
    You need to answer in the user's language: {language}
    """
        
    USER_PROMPT = """
    ##### QUESTION ##### 
    This is a user question: {question}
    """
        
    TEXT_NODE_PROPERTIES = [
        "physician_name",
        "patient_name", 
        "text",
        "hospital_name",
    ]
    
    def __init__(self):
        """Initialize the HospitalReviewChain."""
        self._vector_index = None
        self._review_chain = None
    
    @property
    def vector_index(self) -> Neo4jVector:
        """Lazy initialization of Neo4j vector index."""
        if self._vector_index is None:
          self._vector_index = Neo4jVector.from_existing_graph(
            embedding=OpenAIEmbeddings(model=AppConfig.embedding_model),
            url=os.getenv("NEO4J_URI"),
            username=os.getenv("NEO4J_USER"),
            password=os.getenv("NEO4J_PASSWORD"),
            index_name="reviews",
            node_label="Review",
            text_node_properties=self.TEXT_NODE_PROPERTIES,
            embedding_node_property="embedding"
          )
        return self._vector_index
    
    def _create_prompt(self) -> ChatPromptTemplate:
        """Create the prompt template for review chain."""
        return ChatPromptTemplate.from_messages([
            ("system", self.SYSTEM_PROMPT),
            ("human", self.USER_PROMPT)
        ])
    
    def _get_review_chain(self) -> RetrievalQA:
        """Get or create the RetrievalQA chain."""
        if self._review_chain is None:
            prompt = self._create_prompt()
            
            self._review_chain = RetrievalQA.from_chain_type(
                llm=ChatOpenAI(
                    model=AppConfig.hospital_qa_model, 
                    temperature=AppConfig.temperature
                ), 
                chain_type="stuff",
                retriever=self.vector_index.as_retriever(k=AppConfig.review_top_k), 
                return_source_documents=True
            )
            
            # Override default prompt
            self._review_chain.combine_documents_chain.llm_chain.prompt = prompt
        
        return self._review_chain
    
    def _process_response(self, query: str, docs: list) -> tuple[str, list]:
        """Process documents and generate response."""
        chain = self._get_review_chain()
        
        response = chain.combine_documents_chain.invoke(
            input={
                "question": query, 
                "input_documents": docs, 
                "language": AppConfig.language
            }
        )
        
        return response.get("output_text"), docs
    
    def invoke(self, query: str) -> tuple[str, list]:
        """
        Synchronous review query.
        
        Args:
            query: User's question about hospital reviews
            
        Returns:
            Tuple of (answer, source_documents)
        """
        chain = self._get_review_chain()
        docs = chain.retriever.invoke(input=query)
        return self._process_response(query, docs)
    
    async def ainvoke(self, query: str) -> tuple[str, list]:
        """
        Asynchronous review query.
        
        Args:
            query: User's question about hospital reviews
            
    Returns:
            Tuple of (answer, source_documents)
        """
        chain = self._get_review_chain()
        docs = await chain.retriever.ainvoke(input=query)
        return self._process_response(query, docs)


if __name__ == "__main__": 
    # Test with class instance
    chain = HospitalReviewChain()
    query = "Bệnh nhân nói gì về hiệu quả của bệnh viện?"
    answer, context = chain.invoke(query=query)
    print(f"Answer: {answer}")
    print(f"\nSource documents: {len(context)} docs")