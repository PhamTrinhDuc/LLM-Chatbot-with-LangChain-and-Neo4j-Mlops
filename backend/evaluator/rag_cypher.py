import pandas as pd
from loguru import logger
from neo4j import GraphDatabase
from tqdm import tqdm

from chains.hospital_cypher_chain import HospitalCypherChain
from utils import AppConfig

CYPHER_DATASET_EVAL_PATH = AppConfig.CYPHER_DATASET_EVAL_PATH
CYPHER_RESULT_EVAL_PATH = AppConfig.CYPHER_RESULT_EVAL_PATH

# Kết nối tới Neo4j
driver = GraphDatabase.driver(
    uri=AppConfig.NEO4J_URI, auth=(AppConfig.NEO4J_USER, AppConfig.NEO4J_PASSWORD)
)
chain = HospitalCypherChain(llm_model="groq")


def is_valid_cypher(query: str) -> bool:
    # Dùng EXPLAIN (không execute) → chỉ kiểm tra plan
    try:
        with driver.session() as session:
            session.run(f"EXPLAIN {query}")
        return True
    except Exception as e:
        print("❌ Syntax/semantic error:", e)
        return False


def safe_execute(cypher: str, driver):
    try:
        with driver.session() as s:
            res = s.run(cypher + " LIMIT 50")
            return {tuple(sorted(r.items())) for r in res}
    except Exception as e:
        logger.error(f"Error during execute cypher query: {cypher}. {str(e)}")
        return set()


def generate_response(dataset_path: str, store_path: str = None) -> pd.DataFrame:

    if store_path:
        cypher_dataset = pd.read_csv(store_path)
        if all(
            col in cypher_dataset.columns.to_list()
            for col in ["question", "cypher_gt", "cypher_gen", "answer"]
        ):
            logger.info("The Cypher dataset is already generated")
            return cypher_dataset

    logger.info("Start generate cypher query and answer")
    cypher_dataset = pd.read_csv(dataset_path)

    total_sucess = 0
    for index, row in cypher_dataset.iterrows():
        question, cypher = row["question"], row["cypher_gt"]

        if is_valid_cypher(query=cypher):
            total_sucess += 1

            try:
                answer, cypher_generated = chain.invoke(query=question)
                return answer, cypher_generated
            except Exception as e:
                logger.error(
                    f"Error during get response from chain cypher for query: {question}. {str(e)}"
                )

            # Gán trực tiếp vào DataFrame gốc thông qua index
            cypher_dataset.at[index, "cypher_gen"] = cypher_generated
            cypher_dataset.at[index, "answer"] = answer
        else:
            logger.warning("Cypher query not valid")
            continue

    logger.info(
        f"Percent sucess evaluate cypher query: {total_sucess / len(cypher_dataset):.2f}"
    )
    if store_path:
        cypher_dataset.to_csv(store_path, index=False)
    return cypher_dataset


def evaludate_cypher_rag(cypher_dataset: pd.DataFrame, store_path: str = None):
    logger.info("Start evaluate rag cypher")

    for index, row in tqdm(
        cypher_dataset.iterrows(),
        total=len(cypher_dataset),
        desc="Evaluating Cypher queries",
    ):
        try:
            cypher_gt = row["cypher_gt"]
            cypher_pred = row["cypher_gen"]

            response_cypher_gt = safe_execute(cypher=cypher_gt, driver=driver)
            response_cypher_pred = safe_execute(cypher=cypher_pred, driver=driver)

            equiv = response_cypher_gt == response_cypher_pred
            jacc = (
                len(response_cypher_gt & response_cypher_pred)
                / len(response_cypher_gt | response_cypher_pred)
                if (response_cypher_gt | response_cypher_pred)
                else 1.0
            )
            cypher_dataset.at[index, "equiv"] = equiv
            cypher_dataset.at[index, "jacc"] = jacc

        except Exception as e:
            logger.error(f"Error during evaluate question: {row['question']}. {str(e)}")
            continue

    if store_path:
        cypher_dataset.to_csv(store_path, index=False)

    return cypher_dataset


if __name__ == "__main__":
    cypher_dataset = generate_response(
        dataset_path=CYPHER_DATASET_EVAL_PATH, store_path=CYPHER_RESULT_EVAL_PATH
    )
    cypher_eval = evaludate_cypher_rag(
        cypher_dataset=cypher_dataset, store_path=CYPHER_RESULT_EVAL_PATH
    )
