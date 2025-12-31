import os
import sys
sys.path.append(os.path.join(os.path.dirname(__file__), ".."))
sys.path.append(os.path.join(os.path.dirname(__file__), "..", ".."))
import pandas as pd
from ragas import evaluate
from ragas.metrics import (
    LLMContextRecall,
    Faithfulness,
    FactualCorrectness, 
    AnswerRelevancy, 
    ContextPrecision, 
    ContextRecall
)
from datasets import Dataset
from chains.healthcare_chain import HealthcareRetriever
from utils import ModelFactory, AppConfig


DSM5_DATASET_EVAL_PATH = AppConfig.DSM5_DATASET_EVAL_PATH
DSM5_RESULT_EVAL_PATH = AppConfig.DSM5_RESULT_EVAL_PATH

retriever = HealthcareRetriever()
model = ModelFactory.get_llm_model("groq")


def rag_with_elasticsearch(question: str): 
    # Get relevant contexts from retriever
    retrieved_docs = retriever.invoke(query=question)

    # Format contexts as list of strings for Ragas
    contexts = ['\n'.join([doc['title'], doc['context_headers'], doc['content']]) for doc in retrieved_docs]
    
    prompt = f"""You are a medical expert assistant specializing in mental health disorders based on DSM-5.

    Use the following context to answer the question accurately and professionally.

    {contexts}

    Question: {question}

    Instructions:
    - Answer based ONLY on the provided context
    - Be accurate and cite relevant diagnostic criteria when applicable
    - If the context doesn't contain enough information, state that clearly
    - Provide a clear, professional response
    - Only using Vietnamese language to generate

    Answer:"""
    
    # Invoke model
    response = model.invoke(prompt)
    answer = response.content.strip()

    return answer, contexts


def evaluate_rag(testset_df: pd.DataFrame):
  eval_data = {
    "user_input": [],
    "response": [],
    "retrieved_contexts": [],
    "reference": []
  }

  for _, row in testset_df.iterrows():
    answer, contexts = rag_with_elasticsearch(row['user_input'])
    
    eval_data["user_input"].append(row['user_input'])
    eval_data["response"].append(answer)
    eval_data["retrieved_contexts"].append(contexts)
    eval_data["reference"].append(row.get('reference', ''))

  # Evaluate
  eval_dataset = Dataset.from_dict(eval_data)
  result = evaluate(
    dataset=eval_dataset,
    metrics=[LLMContextRecall(), 
            Faithfulness(), 
            FactualCorrectness(), 
            AnswerRelevancy(), 
            ContextPrecision(), 
            ContextRecall()]
  )
  return result


if __name__ == "__main__": 
#   contexts = rag_with_elasticsearch(question="Phân biệt rối loạn phát triển trí tuệ với rối loạn phổ tự kỷ như thế nào?")
#   print(contexts)

  testset_df = pd.read_csv(DSM5_DATASET_EVAL_PATH)
  results = evaluate_rag(testset_df=testset_df.iloc[:10])

  df_result = results.to_pandas()
  df_result.to_csv(DSM5_RESULT_EVAL_PATH, index=False)
