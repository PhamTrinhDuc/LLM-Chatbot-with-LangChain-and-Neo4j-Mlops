import os
import sys
sys.path.append(os.path.join(os.path.dirname(__file__), ".."))
sys.path.append(os.path.join(os.path.dirname(__file__), "..", ".."))

from backend.chains.hospital_review_chain import create_retriever_review


def test_retrieval(): 
  retriever = create_retriever_review(
    temperature=0, 
    top_k=5, 
    language="Vietnamese"
  )

  response = retriever.invoke(input={"query": "Bệnh nhân nói gì về hiệu quả của bệnh viện?"})
  print(response.get("result"))