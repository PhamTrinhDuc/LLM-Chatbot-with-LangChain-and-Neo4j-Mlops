import os
import sys
sys.path.append(os.path.join(os.path.dirname(__file__), ".."))
sys.path.append(os.path.join(os.path.dirname(__file__), "..", ".."))
from dotenv import load_dotenv

load_dotenv(".env.dev")

from langchain.chains.retrieval_qa.base import RetrievalQA
from langchain.prompts import (
  HumanMessagePromptTemplate, 
  SystemMessagePromptTemplate, 
  ChatPromptTemplate, 
  PromptTemplate
)
from langchain_community.vectorstores import Neo4jVector
from langchain_openai import ChatOpenAI, OpenAIEmbeddings

NEO4J_URI = os.getenv("NEO4J_URI")
NEO4J_USER = os.getenv("NEO4J_USER")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD")
HOSPITAL_QA_MODEL = os.getenv("HOSPITAL_QA_MODEL")


neo4j_vector_index = Neo4jVector.from_existing_graph(
  embedding=OpenAIEmbeddings(model="text-embedding-ada-002"), 
  url=NEO4J_URI, 
  username=NEO4J_USER, 
  password=NEO4J_PASSWORD, 
  index_name="reviews", 
  node_label="Review", 
  text_node_properties=[ # neo4j sẽ join các field này lại thành đoạn để embedding
    "physician_name", 
    "patient_name", 
    "text", 
    "hospital_name",
  ], 
  embedding_node_property="embedding"
)

review_prompt_template = """
##### ROLE #####
Your job is to use patient reviews to answer questions about their experience at a hospital. Use the following context to answer questions. Be as detailed as possible, but don't make up any infomation that's not from context. If you don't know an answer, say you don't know. 
##### CONTEXT #####
{context}
##### LANGUAGE #####
you need to answer in the user's language: {language}
"""

user_prompt_template = """
##### QUESTION ##### 
This is a user question: {question} 
"""


def create_retriever_review(temperature: int=0, 
                     top_k:int=5, 
                     language: str="Vietnamese"):

  review_system_prompt = SystemMessagePromptTemplate(
    prompt=PromptTemplate(
      input_variables=["context", "language"], template=review_prompt_template
    )
  )

  review_human_prompt = HumanMessagePromptTemplate(
    prompt=PromptTemplate(
      input_variables=["question"], template=user_prompt_template
    )
  )

  review_prompt = ChatPromptTemplate(
    input_variables=["context", "question"], 
    partial_variables={"language": language},
    messages=[review_system_prompt, review_human_prompt]
  )

  review_vector_chain = RetrievalQA.from_chain_type(
    llm=ChatOpenAI(model=HOSPITAL_QA_MODEL, temperature=temperature), 
    # input_key="query",
    chain_type="stuff", # Gộp toàn bộ context → gửi 1 prompt duy nhất cho LLM => Context nhỏ, LLM mạnh
    # chain_type="map_reduce" # Tóm tắt từng doc → hợp nhất lại => Context lớn
    # chain_type="refine" # Từng bước refine câu trả lời qua từng doc => Khi cần độ chính xác cao
    retriever=neo4j_vector_index.as_retriever(k=top_k)
  )
  review_vector_chain.combine_documents_chain.llm_chain.prompt = review_prompt # override default prompt of RetrievalQA 

  return review_vector_chain


if __name__ == "__main__": 
  retriever = create_retriever_review()
  output = retriever.invoke(input={
    "query": "Bệnh nhân nói gì về hiệu quả của bệnh viện?", 
  })
  print(output.get("result"))