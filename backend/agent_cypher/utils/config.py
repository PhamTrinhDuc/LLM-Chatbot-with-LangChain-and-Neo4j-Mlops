from dataclasses import dataclass

@dataclass
class AppConfig: 
  review_top_k: int=10
  cypher_top_k: int=5
  language: str = "Vietnamese"
  temperature: int=0

  hospital_agent_model: str = "gpt-4o-mini"
  hospital_cypher_model: str = "gpt-4o-mini"
  hospital_qa_model: str = "gpt-4o-mini"
  embedding_model: str = "text-embedding-ada-002"