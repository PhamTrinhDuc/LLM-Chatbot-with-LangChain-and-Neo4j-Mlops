import json
import os
import sys
from typing import List, Optional

import pandas as pd
from groq import Groq
from neo4j import GraphDatabase
from pydantic import BaseModel, Field

sys.path.append(os.path.join(os.path.dirname(__file__), ".."))
sys.path.append(os.path.join(os.path.dirname(__file__), "..", ".."))
from prompt.evaluate import (
    SYSTEM_CYPHER_GENERATION_TEMPLATE,
    USER_CYPHER_GENERATION_TEMPLATE,
)
from utils import AppConfig

# Kết nối tới Neo4j
driver = GraphDatabase.driver(
    uri=AppConfig.NEO4J_URI, auth=(AppConfig.NEO4J_USER, AppConfig.NEO4J_PASSWORD)
)
groq = Groq(api_key=AppConfig.GROQ_API_KEY)


class CypherPairGeneration(BaseModel):
    question: str = Field(..., description="Question narual of human")
    cypher_gt: str = Field(..., description="Cypher generated following question")


class CypherDataset(BaseModel):
    dataset: List[CypherPairGeneration]


TOPICS_SPECIFICS = {
    "Hospital Analytics": [
        "Hospital",
        "Physician",
        "Visit",
    ],  # Quản trị & Hiệu suất Bệnh viện
    "Patient Journey": [
        "Patient",
        "Visit",
        "Hospital",
        "Physician",
    ],  # Hành trình & Hồ sơ Bệnh nhân
    "Healthcare Economics": ["Visit", "Payer", "Physician"],  # Tài chính & Bảo hiểm
    "Advanced Reasoning": [],
    "Physician Career & Background": [
        "Physician",
        "Hospital",
    ],  # Phân tích Sự nghiệp & Nhân sự
    "Admission Efficiency": [
        "Visit",
        "Hospital",
        "Patient",
    ],  # Quy trình Nhập viện & Hiệu quả Vận hành
    "Data Validation & Integrity": [
        "Review",
        "Visit",
        "Physician",
        "Patient",
    ],  # Đối soát Dữ liệu & Tính nhất quán
    "Clinical Grouping": ["Patient", "Visit"],  # Phân tích Nhóm bệnh & Dịch tễ
}


def get_graph_schema():
    with driver.session() as session:
        # 1. Lấy thông tin Nodes & Properties
        nodes_info = session.run("CALL db.schema.nodeTypeProperties()").data()

        # 2. Lấy thông tin Relationships & Properties
        rels_info = session.run("CALL db.schema.relTypeProperties()").data()

        # 3. Lấy Topology (Mối quan hệ giữa các Node)
        topology = session.run(
            """
        MATCH (n)-[r]->(m) 
        RETURN DISTINCT labels(n) as source, type(r) as rel, labels(m) as target
    """
        ).data()

        # Format thành chuỗi văn bản cho LLM
        schema_text = "Node Labels & Properties:\n"
        for node in nodes_info:
            schema_text += f"- {node['nodeLabels']}: {node['propertyName']} ({node['propertyTypes']})\n"

        schema_text += "\nRelationship Topology:\n"
        for top in topology:
            schema_text += f"- ({top['source']}) -[:{top['rel']}]-> ({top['target']})\n"

    driver.close()
    return schema_text


def generate_cypher_query(
    schema_text: str,
    topic: str,
    focus_nodes: Optional[List[str]] = None,
    num_pairs: int = 5,
):

    system_prompt = SYSTEM_CYPHER_GENERATION_TEMPLATE.format(schema=schema_text)
    user_prompt = USER_CYPHER_GENERATION_TEMPLATE.format(
        topic=topic, focus_nodes=focus_nodes, num_pairs=num_pairs
    )

    response = groq.chat.completions.create(
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        model=AppConfig.GROQ_LLM,
        temperature=0.3,
        response_format={
            "type": "json_schema",
            "json_schema": {
                "name": "cypher_query_generation",
                "schema": CypherDataset.model_json_schema(),
            },
        },
    )
    result = json.loads(response.choices[0].message.content or "{}")
    return result


if __name__ == "__main__":
    schema_info = get_graph_schema()

    dataset = []

    for i, (topic, focus_node) in enumerate(TOPICS_SPECIFICS.items()):
        data = generate_cypher_query(
            schema_text=schema_info, topic=topic, focus_nodes=focus_node
        )
        dataset.extend(data["dataset"])
        if i == 2:
            break

    df_dataset = pd.DataFrame(dataset)
    df_dataset.to_csv(AppConfig.CYPHER_DATASET_EVAL_PATH, index=False)
