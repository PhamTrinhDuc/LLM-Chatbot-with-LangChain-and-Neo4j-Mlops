from agents.hospital_rag_agent import HospitalRAGAgent
from models.hospital_rag_query import HospitalQueryInput, HospitalQueryOutput
from utils.helper import async_retry

from fastapi import FastAPI

app = FastAPI(
    title="Hospital Chatbot",
    description="Endpoints for a hospital system graph RAG chatbot",
)


@app.get("/")
async def get_status():
    return {"status": "running"}


@app.post("/hospital-rag-agent")
async def query_hospital_agent(
    query: HospitalQueryInput,
) -> HospitalQueryOutput:
    agent = HospitalRAGAgent()
    query_response = await agent.ainvoke(query=query.text)
    query_response["intermediate_steps"] = [
        str(s) for s in query_response["intermediate_steps"]
    ]

    return query_response

# script: uvicorn main:app --host 0.0.0.0 --port 8000 --reload
