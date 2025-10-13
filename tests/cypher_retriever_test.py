import os
import sys
sys.path.append(os.path.join(os.path.dirname(__file__), ".."))
sys.path.append(os.path.join(os.path.dirname(__file__), "..", ".."))

from backend.chains.hospital_cypher_chain import create_retriver_cypher


def test_retrieval(): 
  retriever = create_retriver_cypher(
    temperature=0, 
    top_k=10, 
    language="Vietnamese"
  )

  response = retriever.invoke(input={"query": "Tiểu bang nào có mức tăng phần trăm lớn nhất trong các lần khám Medicaid từ năm 2022 đến năm 2023?"})
  print(response.get("result"))