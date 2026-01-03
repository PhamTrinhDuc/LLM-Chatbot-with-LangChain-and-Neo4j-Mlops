import json
import time
from typing import List

import pandas as pd
from groq import Groq
from langchain_core.documents import Document
from pydantic import BaseModel, Field
from tqdm import tqdm

from prompt import DSM5_SYSTEM_GENERATION_TEMPLATE
from utils import AppConfig

DSM5_CHUNKS_PATH = AppConfig.DSM5_CHUNKS_PATH
DSM5_DATASET_EVAL_PATH = AppConfig.DSM5_DATASET_EVAL_PATH
groq = Groq(api_key=AppConfig.GROQ_API_KEY)


class Dsm5Generation(BaseModel):
    question: str = Field(..., description="Question for user")
    ground_truth: str = Field(
        ..., description="the correct answer to the question based on the context"
    )


class Dsm5Dataset(BaseModel):
    dataset: List[Dsm5Generation]


def transform_chunks(chunks: list[dict]) -> list[Document]:
    documents = []

    for chunk in chunks:
        doc = Document(
            page_content=chunk["title"] + chunk["content"],
            metadata={
                "chunk_idx": chunk["chunk_idx"],
                "section_id": chunk["section_id"],
                "title": chunk["title"],
                "parent_section_id": chunk["parent_section_id"],
                "parent_section_title": chunk["parent_section_title"],
                "context_headers": chunk["context_headers"],
            },
        )
        documents.append(doc)
    return documents


def generate_dataset(
    chunks: list[Document], num_samples: int = 20, num_pairs_generated: int = 2
):
    print("🔄 Starting manual generation...")

    dataset = []

    # Sample random chunks
    import random

    if len(chunks) > num_samples:
        selected_chunks = random.sample(chunks, num_samples)
    else:
        selected_chunks = chunks

    for chunk in tqdm(selected_chunks, desc="Generating QA"):
        try:

            system_prompt = DSM5_SYSTEM_GENERATION_TEMPLATE.format(
                num_pairs=num_pairs_generated, passage=selected_chunks
            )
            messages = [
                {"role": "system", "content": system_prompt},
            ]

            response = groq.chat.completions.create(
                model=AppConfig.GROQ_LLM,
                messages=messages,
                temperature=0.3,
                response_format={
                    "type": "json_schema",
                    "json_schema": {
                        "name": "cypher_query_generation",
                        "schema": Dsm5Dataset.model_json_schema(),
                    },
                },
            )

            time.sleep(1)  # tránh rate limit
            response_json = json.loads(response.choices[0].message.content or "{}")
            print(response_json)

            for qa_data in response_json["dataset"]:
                dataset.append(
                    {
                        "user_input": qa_data["question"],
                        "reference": qa_data["ground_truth"],
                        "retrieved_contexts": [chunk.page_content],
                    }
                )

        except Exception as e:
            print(f"⚠️ Error parsing response: {e}")
            print(f"Response content: {response.content[:200]}")
            continue

    testset_df = pd.DataFrame(data=dataset)
    return testset_df


if __name__ == "__main__":
    with open(DSM5_CHUNKS_PATH, "r", encoding="utf-8") as f:
        chunks_data = json.load(f)

    documents = transform_chunks(chunks=chunks_data)
    testset_df = generate_dataset(
        chunks=documents, num_samples=3, num_pairs_generated=2
    )
    print(testset_df)

    # testset_df.to_csv(DSM5_DATASET_EVAL_PATH, index=False)
