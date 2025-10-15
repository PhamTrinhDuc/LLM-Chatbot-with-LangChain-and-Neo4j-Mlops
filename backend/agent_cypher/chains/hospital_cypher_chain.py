import os
import sys
sys.path.append(os.path.join(os.path.dirname(__file__), ".."))
from dotenv import load_dotenv
from langchain.prompts import PromptTemplate
from langchain_community.graphs import Neo4jGraph
from langchain_community.chains.graph_qa.cypher import GraphCypherQAChain
from langchain_openai import ChatOpenAI

from utils.config import AppConfig

load_dotenv(".env.dev")


class HospitalCypherChain:
    """
    Chain for querying hospital data using Cypher queries on Neo4j Graph database.
    
    Generates Cypher queries from natural language questions and returns human-readable answers.
    """
    
    # Constants
    CYPHER_GENERATION_TEMPLATE = """
    ##### ROLE ##### 
    Generate Cypher query for a Neo4j Graph database
    Instructions: 
    use only the provided relatiobship types and properties in schema. 
    DO NOT use any other relationship types or properties tha are not provided

    ##### SCHEMA ######
    {schema}

    ##### NOTE #####
    DO NOT inclue any explanations or apologies in your response. 
    DO NOT respond to any questions that might ask anything other than for you to construct a Cypher statement. 
    DO NOT include any text except the generated Cypher statement. Make sure the direction of the relationship is
    correct in your queries. Make sure you alias both entities and relationships
    properly
    DO NOT run any queries that would ADD to or DELETE from
    the database. Make sure to alias all statements that follow as with
    statement (e.g. WITH v as visit, c.billing_amount as billing_amount)
    If you need to divide numbers, make sure to
    filter the denominator to be non zero.

    ##### EXAMPLE #####

    # Who is the oldest patient and how old are they?
    MATCH (p:Patient)
    RETURN p.name AS oldest_patient,
          duration.between(date(p.dob), date()).years AS age
    ORDER BY age DESC
    LIMIT 1

    # Which physician has billed the least to Cigna
    MATCH (p:Payer)<-[c:COVERED_BY]-(v:Visit)-[t:TREATS]-(phy:Physician)
    WHERE p.name = 'Cigna'
    RETURN phy.name AS physician_name, SUM(c.billing_amount) AS total_billed
    ORDER BY total_billed
    LIMIT 1

    # Which state had the largest percent increase in Cigna visits
    # from 2022 to 2023?
    MATCH (h:Hospital)<-[:AT]-(v:Visit)-[:COVERED_BY]->(p:Payer)
    WHERE p.name = 'Cigna' AND v.admission_date >= '2022-01-01' AND
    v.admission_date < '2024-01-01'
    WITH h.state_name AS state, COUNT(v) AS visit_count,
        SUM(CASE WHEN v.admission_date >= '2022-01-01' AND
        v.admission_date < '2023-01-01' THEN 1 ELSE 0 END) AS count_2022,
        SUM(CASE WHEN v.admission_date >= '2023-01-01' AND
        v.admission_date < '2024-01-01' THEN 1 ELSE 0 END) AS count_2023
    WITH state, visit_count, count_2022, count_2023,
        (toFloat(count_2023) - toFloat(count_2022)) / toFloat(count_2022) * 100
        AS percent_increase
    RETURN state, percent_increase
    ORDER BY percent_increase DESC
    LIMIT 1

    # How many non-emergency patients in North Carolina have written reviews?
    match (r:Review)<-[:WRITES]-(v:Visit)-[:AT]->(h:Hospital)
    where h.state_name = 'NC' and v.admission_type <> 'Emergency'
    return count(*)

    String category values:
    Test results are one of: 'Inconclusive', 'Normal', 'Abnormal'
    Visit statuses are one of: 'OPEN', 'DISCHARGED'
    Admission Types are one of: 'Elective', 'Emergency', 'Urgent'
    Payer names are one of: 'Cigna', 'Blue Cross', 'UnitedHealthcare', 'Medicare',
    'Aetna'

    A visit is considered open if its status is 'OPEN' and the discharge date is
    missing.
    Use abbreviations when
    filtering on hospital states (e.g. "Texas" is "TX",
    "Colorado" is "CO", "North Carolina" is "NC",
    "Florida" is "FL", "Georgia" is "GA, etc.)

    Make sure to use IS NULL or IS NOT NULL when analyzing missing properties.
    Never return embedding properties in your queries. You must never include the
    statement "GROUP BY" in your query. Make sure to alias all statements that
    follow as with statement (e.g. WITH v as visit, c.billing_amount as
    billing_amount)
    If you need to divide numbers, make sure to filter the denominator to be non
    zero.

    ##### QUESTION #####
    {question}
    """


    QA_GENERATION_TEMPLATE = """
    ##### ROLE #####
    You are an assistant that takes the results from a Neo4j Cypher query and forms 
    a human-readable response. The query results section contains the results of a 
    Cypher query that was generated based on a users natural language question. The 
    provided information is authoritative, you must never doubt it or try to use your 
    internal knowledge to correct it. Make the answer sound like a response to the question.

    ##### CONTEXT #####
    {context}

    ##### QUESTION #####
    {question}

    If the provided information is empty, say you don't know the answer.
    Empty information looks like this: []

    If the information is not empty, you must provide an answer using the results. 
    If the question involves a time duration, assume the query results are in units 
    of days unless otherwise specified.

    When names are provided in the query results, such as hospital names, beware of 
    any names that have commas or other punctuation in them. For instance, 
    'Jones, Brown and Murray' is a single hospital name, not multiple hospitals. 
    Make sure you return any list of names in a way that isn't ambiguous and allows 
    someone to tell what the full names are.

    Never say you don't have the right information if there is data in the query results. 
    Make sure to show all the relevant query results if you're asked.

    ##### LANGUAGE #####
    You need to answer in the user's language: {language}
    """
    
    def __init__(self):
        """Initialize the HospitalCypherChain."""
        self._graph = None
        self._cypher_chain = None
    
    @property
    def graph(self) -> Neo4jGraph:
        """Lazy initialization of Neo4j graph."""
        if self._graph is None:
            self._graph = Neo4jGraph(
                url=os.getenv("NEO4J_URI"),
                username=os.getenv("NEO4J_USER"),
                password=os.getenv("NEO4J_PASSWORD"),
                enhanced_schema=True
            )
            self._graph.refresh_schema()
        return self._graph
    
    def _create_prompts(self) -> tuple[PromptTemplate, PromptTemplate]:
        """Create prompt templates for Cypher generation and QA."""
        cypher_prompt = PromptTemplate(
            input_variables=["schema", "question"],
            template=self.CYPHER_GENERATION_TEMPLATE
        )
        
        qa_prompt = PromptTemplate(
            input_variables=["context", "question"],
            partial_variables={"language": AppConfig.language},
            template=self.QA_GENERATION_TEMPLATE
        )
        
        return cypher_prompt, qa_prompt
    
    def _get_cypher_chain(self) -> GraphCypherQAChain:
        """Get or create the GraphCypherQAChain."""
        if self._cypher_chain is None:
            cypher_prompt, qa_prompt = self._create_prompts()
            
            self._cypher_chain = GraphCypherQAChain.from_llm(
                cypher_llm=ChatOpenAI(
                    model=AppConfig.hospital_cypher_model,
                    temperature=AppConfig.temperature
                ),
                qa_llm=ChatOpenAI(
                    model=AppConfig.hospital_qa_model,
                    temperature=AppConfig.temperature
                ),
                graph=self.graph,
                allow_dangerous_requests=True,
                verbose=False,
                qa_prompt=qa_prompt,
                cypher_prompt=cypher_prompt,
                validate_cypher=True,
                top_k=AppConfig.cypher_top_k,
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
      chain = self._get_cypher_chain()
      response = chain.invoke(input={"query": query})
      
      generated_cypher = response["intermediate_steps"][0]["query"]
      answer = response.get("result")
      
      return answer, generated_cypher

    async def ainvoke(self, query: str) -> tuple[str, str]: 
      """
      Asynchronous Cypher query.
      
      Args:
          query: User's natural language question
          
      Returns:
          Tuple of (answer, generated_cypher_query)
      """
      chain = self._get_cypher_chain()
      response = await chain.invoke(input={"query": query})
      
      generated_cypher = response["intermediate_steps"][0]["query"]
      answer = response.get("result")
      
      return answer, generated_cypher


if __name__ == "__main__":
    # Test with class instance
    chain = HospitalCypherChain()
    query = "Tiểu bang nào có mức tăng phần trăm lớn nhất trong các lần khám Medicaid từ năm 2022 đến năm 2023"
    answer, generated_cypher = chain.invoke(query=query)
    print(f"Generated Cypher:\n{generated_cypher}\n")
    print(f"Answer: {answer}")

