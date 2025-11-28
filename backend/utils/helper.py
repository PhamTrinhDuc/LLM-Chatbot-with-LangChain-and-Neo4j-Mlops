import asyncio
from typing import Literal
from utils.config import AppConfig
from utils.logging import logger


def format_output(response: dict) -> dict[str, str]:
  tool = response["intermediate_steps"][0][0].tool
  if tool == "Graph": 
    context = response["intermediate_steps"][0][1]["generated_cypher"]
  elif tool == "Experiences":
    context = response["intermediate_steps"][0][1]["context"]
  else:
    context = None

  result = response["intermediate_steps"][0][1]["result"]

  return {
    "tool": tool, 
    "answer": result, 
    "context": context
  }


def async_retry(max_retries: int = 3, delay: int = 1):
  def decorator(func):
    async def wrapper(*args, **kwargs):
      for attempt in range(1, max_retries + 1):
          try:
              result = await func(*args, **kwargs)
              return result
          except Exception as e:
              print(f"Attempt {attempt} failed: {str(e)}")
              await asyncio.sleep(delay)

      raise ValueError(f"Failed after {max_retries} attempts")

    return wrapper

  return decorator


class ModelFactory:
  @staticmethod
  def get_llm_model(llm_model: Literal["google", "openai"]="google"): 
      
    try:
      if llm_model == "google": 
        from langchain_google_genai import ChatGoogleGenerativeAI
        llm = ChatGoogleGenerativeAI(
          model=AppConfig.GOOGLE_LLM, 
          temperature=AppConfig.TEMPERATURE, 
          api_key=AppConfig.GOOGLE_API_KEY
        )
    except Exception as e: 
      logger.error(f"Error initializing model {llm_model}: {str(e)}")
      raise ValueError(f"Error initializing model {llm_model}: {str(e)}")
    
    from langchain_openai import ChatOpenAI
    llm = ChatOpenAI(
      model=AppConfig.OPENAI_LLM, 
      temperature=AppConfig.TEMPERATURE, 
      api_key=AppConfig.OPENAI_API_KEY
    )
    return llm
  
  @staticmethod
  def get_embedding_model(embedding_model: Literal["google", "openai"]="openai"): 
    try:
      if embedding_model == "google": 
        from langchain_google_genai import GoogleGenerativeAIEmbeddings
        embedding_model = GoogleGenerativeAIEmbeddings(
          model=AppConfig.GOOGLE_EMBEDDING, 
          api_key=AppConfig.GOOGLE_API_KEY, 

        )
        return embedding_model
    except Exception as e: 
      logger.error(f"Error initializing embedding model {embedding_model}: {str(e)}")
      raise ValueError(f"Error initializing embedding model {embedding_model}: {str(e)}")
    
    from langchain_openai import OpenAIEmbeddings
    embedding_model = OpenAIEmbeddings(
      model=AppConfig.OPENAI_EMBEDDING, 
      api_key=AppConfig.OPENAI_API_KEY, 
    )
    return embedding_model 