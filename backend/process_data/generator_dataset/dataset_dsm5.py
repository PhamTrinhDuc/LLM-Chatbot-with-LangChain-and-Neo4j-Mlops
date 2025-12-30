import os
import sys
sys.path.append(os.path.join(os.path.dirname(__file__), ".."))
sys.path.append(os.path.join(os.path.dirname(__file__), "..", ".."))
import time
import json
import pandas as pd
from tqdm import tqdm
from ragas.testset import TestsetGenerator
from ragas.testset.synthesizers import default_query_distribution
from langchain_core.documents import Document
from utils import ModelFactory, AppConfig


DSM5_CHUNKS_PATH = AppConfig.DSM5_CHUNKS_PATH
DSM5_DATASET_EVAL_PATH = AppConfig.DSM5_DATASET_EVAL_PATH

model = ModelFactory.get_llm_model(llm_model="groq")
embedding_model = ModelFactory.get_embedding_model(embedding_model="google")

generator  = TestsetGenerator(
  llm=model, 
  embedding_model=embedding_model,
)

def transform_chunks(chunks: list[dict]) -> list[Document]: 
  documents = []

  for chunk in chunks:
    doc = Document(
      page_content=chunk['title'] + chunk['content'], 
      metadata = {
        "chunk_idx": chunk['chunk_idx'],
        "section_id": chunk['section_id'],
        "title": chunk['title'],
        "parent_section_id": chunk['parent_section_id'],
        "parent_section_title": chunk['parent_section_title'],
        "context_headers": chunk['context_headers'],
      }
    )
    documents.append(doc)
  return documents
      

def generate_dataset(chunks: list[Document], num_questions: int=20):
  try:
    testset = generator.generate_with_langchain_docs(
      documents=chunks, 
      testset_size=num_questions, 
      transforms=None,
      query_distribution=default_query_distribution
    )
      
    testset_df = testset.to_pandas()
  
  except Exception as e: 
    print(f"⚠️ Ragas generation failed: {e}")
    print("🔄 Fallback to manual generation...")
    
    system_prompt = """You are an expert in creating test questions.
    Task: Read the passage and create 1 specific question that can be answered from the passage.

    Requirements:
    - Question must be SPECIFIC and answerable from the context
    - Answer must be ACCURATE based on the content
    - Vary question types: What, How, Why, When, Define, Explain, etc.
    - Only using Vietnamese language to generate

    Return ONLY a valid JSON object (no markdown, no explanation):
    {"question": "your question here", "ground_truth": "complete answer here"}"""
    
    dataset = []
    
    # Sample random chunks
    import random
    if len(chunks) > num_questions:
        selected_chunks = random.sample(chunks, num_questions)
    else:
        selected_chunks = chunks
    
    for chunk in tqdm(selected_chunks, desc="Generating QA"):
      try:
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"Passage:\n\n{chunk.page_content}"}
        ]
        
        response = model.invoke(messages)
        time.sleep(1) # tránh rate limit
        
        # Clean response - remove markdown code blocks if present
        content = response.content.strip()
        if content.startswith("```json"):
            content = content[7:]
        if content.startswith("```"):
            content = content[3:]
        if content.endswith("```"):
            content = content[:-3]
        content = content.strip()
        
        qa_data = json.loads(content)
        
        dataset.append({
          "user_input": qa_data["question"],
          "reference": qa_data["ground_truth"],
          "retrieved_contexts": [chunk.page_content]
        })
          
      except Exception as e:
          print(f"⚠️ Error parsing response: {e}")
          print(f"Response content: {response.content[:200]}")
          continue
    
    testset_df = pd.DataFrame(data=dataset)
  return testset_df


if __name__ == "__main__":
  with open(DSM5_CHUNKS_PATH, 'r', encoding='utf-8') as f:
    chunks_data = json.load(f)

  documents = transform_chunks(chunks=chunks_data)
  testset_df = generate_dataset(chunks=documents, num_questions=100)
  testset_df.to_csv(DSM5_DATASET_EVAL_PATH, index=False)