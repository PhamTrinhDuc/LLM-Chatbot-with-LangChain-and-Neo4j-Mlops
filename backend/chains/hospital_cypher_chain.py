import os
import sys
sys.path.append(os.path.join(os.path.dirname(__file__), ".."))
from typing import Literal
from langchain.prompts import PromptTemplate
from langchain_community.graphs import Neo4jGraph
from langchain_community.chains.graph_qa.cypher import GraphCypherQAChain
from prompt.hospital_prompt import QA_GENERATION_TEMPLATE, CYPHER_GENERATION_TEMPLATE
from utils import ModelFactory, AppConfig, logger

class HospitalCypherChain:
    """
    Chain for querying hospital data using Cypher queries on Neo4j Graph database.
    
    Generates Cypher queries from natural language questions and returns human-readable answers.
    """
    def __init__(self, llm_model: str):
        """Initialize the HospitalCypherChain."""
        self.neo4j_uri = AppConfig.NEO4J_URI
        self.neo4j_user = AppConfig.NEO4J_USER
        self.neo4j_password = AppConfig.NEO4J_PASSWORD
        self.llm_model = llm_model
        self._graph = None
        self._cypher_chain = None
        self._llm = None
    
    @property
    def llm(self): 
        """Lazy initialization of LLM model."""
        if self._llm is None:
          self._llm = ModelFactory.get_llm_model(llm_model=self.llm_model)
        return self._llm

    @property
    def graph(self) -> Neo4jGraph:
        """Lazy initialization of Neo4j graph."""
        if self._graph is None:
            self._graph = Neo4jGraph(
                url=self.neo4j_uri,
                username=self.neo4j_user,
                password=self.neo4j_password,
                enhanced_schema=True
            )
            self._graph.refresh_schema()
        return self._graph
    
    def _create_prompts(self) -> tuple[PromptTemplate, PromptTemplate]:
        """Create prompt templates for Cypher generation and QA."""
        cypher_prompt = PromptTemplate(
            input_variables=["schema", "question"],
            template=CYPHER_GENERATION_TEMPLATE
        )
        
        qa_prompt = PromptTemplate(
            input_variables=["context", "question"],
            partial_variables={"language": AppConfig.LANGUAGE},
            template=QA_GENERATION_TEMPLATE
        )
        
        return cypher_prompt, qa_prompt
    
    def _get_cypher_chain(self) -> GraphCypherQAChain:
        """Get or create the GraphCypherQAChain."""
        if self._cypher_chain is None:
            cypher_prompt, qa_prompt = self._create_prompts()
            
            self._cypher_chain = GraphCypherQAChain.from_llm(
                cypher_llm=self.llm,
                qa_llm=self.llm,
                graph=self.graph,
                allow_dangerous_requests=True,
                verbose=False,
                qa_prompt=qa_prompt,
                cypher_prompt=cypher_prompt,
                validate_cypher=True,
                top_k=AppConfig.CYPHER_TOP_K,
                return_intermediate_steps=True
            )
        
        return self._cypher_chain
    
    def invoke(self, query: str) -> tuple[str, str]:
      """
      Synchronous Cypher query.
      
      Args:
          query: User's natural language question
          
      Returns:
          Tuple of (answer, generated_cypher_query)
      """
      try:
        logger.info(f"Processing sync cypher query: {query}")
        chain = self._get_cypher_chain()
        response = chain.invoke(input={"query": query})
        
        generated_cypher = response["intermediate_steps"][0]["query"]
        answer = response.get("result")
        
        return answer, generated_cypher
      except Exception as e:
        logger.error(f"Error in invoke: {str(e)}")
        raise e

    async def ainvoke(self, query: str) -> tuple[str, str]: 
      """
      Asynchronous Cypher query.
      
      Args:
          query: User's natural language question
          
      Returns:
          Tuple of (answer, generated_cypher_query)
      """
      try:
        logger.info(f"Processing async cypher query: {query}")
        chain = self._get_cypher_chain()
        response = await chain.ainvoke(input={"query": query})
        
        generated_cypher = response["intermediate_steps"][0]["query"]
        answer = response.get("result")
        
        return answer, generated_cypher
      
      except Exception as e:
        logger.error(f"Error in ainvoke: {str(e)}")
        raise e

    def __del__(self):
        """Cleanup when object is destroyed."""
        try:
            if self._graph and hasattr(self._graph, '_driver'):
                self._graph._driver.close()
        except Exception:
            pass

if __name__ == "__main__":
    chain = HospitalCypherChain(llm_model="google")
    query = "Tiểu bang nào có mức tăng phần trăm lớn nhất trong các lần khám Medicaid từ năm 2022 đến năm 2023"
    answer, generated_cypher = chain.invoke(query=query)
    print(f"Generated Cypher:\n{generated_cypher}\n")
    print(f"Answer: {answer}")

