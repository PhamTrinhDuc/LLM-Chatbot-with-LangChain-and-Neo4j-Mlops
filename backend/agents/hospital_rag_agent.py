import os
import sys
from datetime import datetime
sys.path.append(os.path.join(os.path.dirname(__file__), ".."))
from typing import Literal
from langchain import hub
from langchain.agents import AgentExecutor, Tool, create_openai_functions_agent
from langchain_community.chat_message_histories import RedisChatMessageHistory
from langchain.memory import ConversationBufferWindowMemory
from langchain_community.chat_message_histories import FileChatMessageHistory
from tools import (
  CypherTool, 
  ReviewTool, 
  DSM5RetrievalTool,
  get_current_wait_times, 
  get_most_available_hospital
)
from utils import AppConfig, ModelFactory, logger

class HospitalRAGAgent:
    """
    RAG Agent for answering hospital-related questions using multiple tools.
    
    Combines Cypher queries, semantic search, and real-time wait time data
    to provide comprehensive answers about hospital operations.
    """
    
    def __init__(self, 
                 llm_model: str,
                 embedding_model: str,  
                 user_id: str, 
                 type_memory: Literal["file", 'redis']="file",
                 session_id: str=None):
        """Initialize the HospitalRAGAgent with tools and agent executor."""
        self.llm_model = llm_model
        self.embedding_model = embedding_model
        self.user_id = user_id  
        self.session_id = session_id
        self.type_memory = type_memory
        self._agent_executor = None
        self._llm = None
        self._tools = None
        self._prompt = None
        self._memory = None

    @property
    def memory(self): 
      if self._memory is None:
        session_id = self.session_id or f"{self.user_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        
        if self.type_memory == 'file': 
           # File-based memory
           file_chat_history = FileChatMessageHistory(
              file_path=session_id + ".json"
           )
           self._memory = ConversationBufferWindowMemory(
              chat_memory=file_chat_history,
              memory_key="chat_history", 
              return_messages=True, 
              output_key="output", 
              k=AppConfig.MEMORY_TOP_K
           )
        else:
          # Redis-based memory
          message_history = RedisChatMessageHistory(
             session_id=session_id, 
             url=AppConfig.REDIS_URL, 
             ttl=AppConfig.TTL
          )
          self._memory = ConversationBufferWindowMemory(
            chat_memory=message_history, 
            memory_key="chat_history", 
            return_messages=True, 
            output_key="output", 
            k=AppConfig.MEMORY_TOP_K
          )
      return self._memory
    
    @property
    def llm(self):
        """Lazy initialization of LLM model."""
        if self._llm is None:
          self._llm = ModelFactory.get_llm_model(llm_model=self.llm_model)
        return self._llm

    @property
    def prompt(self):
        """Lazy load the agent prompt from LangChain Hub."""
        if self._prompt is None:
            self._prompt = hub.pull("hwchase17/openai-functions-agent")
        return self._prompt
    
    @property
    def tools(self) -> list:
      """Get or create the list of tools available to the agent."""
      if self._tools is None:
        self._tools = [
          CypherTool(llm_model=self.llm_model),

          ReviewTool(llm_model=self.llm_model, 
                      embedding_model=self.embedding_model),

          DSM5RetrievalTool(
              embedding_model=self.embedding_model),
              
          Tool(
            name="Waits",
            func=get_current_wait_times,
            description="""Use when asked about current wait times at a specific hospital. \
            This tool can only get the current wait time at a hospital and does not have any information \
            about aggregate or historical wait times. Do not pass the word "hospital" as input, only the \
            hospital name itself. For example, if the prompt is "What is the current wait time at \
            Jordan Inc Hospital?", the input should be "Jordan Inc"."""
          ),
          
          Tool(
            name="Availability",
            func=get_most_available_hospital,
            description="""Use when you need to find out which hospital has the shortest \
            wait time. This tool does not have any information about aggregate or historical wait times. \
            This tool returns a dictionary with the hospital name as the key and the wait time in minutes \
            as the value."""
          ),
        ]
      return self._tools
    
    @property
    def agent_executor(self) -> AgentExecutor:
      """Get or create the agent executor."""
      if self._agent_executor is None:
        agent = create_openai_functions_agent(
            llm=self.llm,
            prompt=self.prompt,
            tools=self.tools,
        )
        
        self._agent_executor = AgentExecutor(
            agent=agent,
            tools=self.tools,
            memory=self.memory,
            return_intermediate_steps=True,
            verbose=False,
        )
      return self._agent_executor
    
    def _extract_metadata(self, result: dict) -> dict:
        """Extract metadata from intermediate steps."""
        metadata_list = []
        for step in result.get("intermediate_steps", []):
            action, observation = step
            if isinstance(observation, dict) and "metadata" in observation:
                metadata_list.append(observation['metadata'])
        
        result['metadata'] = metadata_list
        return result
    
    def invoke(self, query: str) -> dict:
      """
      Synchronous execution of agent query.
      
      Args:
          query: User's question about hospital data
          
      Returns:
          Dictionary with 'output', 'intermediate_steps', and 'metadata'
      """
      try:
        result = self.agent_executor.invoke({"input": query})
        return self._extract_metadata(result)
      except Exception as e:
        logger.error(f"Error in invoke: {e}")
        raise e
    
    async def ainvoke(self, query: str) -> dict:
      """
      Asynchronous execution of agent query.
      
      Args:
          query: User's question about hospital data
          
      Returns:
          Dictionary with 'output', 'intermediate_steps', and 'metadata'
      """
      try:
        result = await self.agent_executor.ainvoke({"input": query})
        return self._extract_metadata(result)
      except Exception as e:
        logger.error(f"Error in ainvoke: {e}")
        raise e
    
    def stream(self, query: str):
        """
        Synchronous streaming execution of agent query.
        
        Yields intermediate steps and final output as they become available.
        
        Args:
            query: User's question about hospital data
            
        Yields:
            Dictionary chunks containing 'actions', 'steps', or 'output'
        """
        try:
          for chunk in self.agent_executor.stream({"input": query}):
              yield chunk
        except Exception as e:
          logger.error(f"Error in stream: {e}")
          raise e
    
    async def astream(self, query: str):
        """
        Asynchronous streaming execution of agent query.
        
        Yields intermediate steps and final output as they become available.
        Useful for real-time UI updates and progressive response display.
        
        Args:
            query: User's question about hospital data
            
        Yields:
            Dictionary chunks containing:
            - 'actions': Tool invocations being executed
            - 'steps': Completed tool execution results  
            - 'output': Final agent response
            
        Example:
            async for chunk in agent.astream("What is the wait time?"):
                if 'actions' in chunk:
                    print(f"Tool: {chunk['actions'][0].tool}")
                elif 'steps' in chunk:
                    print(f"Result: {chunk['steps'][0].observation}")
                elif 'output' in chunk:
                    print(f"Final: {chunk['output']}")
        """
        try:
          async for chunk in self.agent_executor.astream({"input": query}):
            yield chunk
        except Exception as e:
          logger.error(f"Error in astream: {e}")
          raise e


if __name__ == "__main__":
    import asyncio
    # Test with class instance
    agent = HospitalRAGAgent(
      llm_model="openai",
      embedding_model="openai",
      user_id=1, 
      type_memory='file'
    )
    
    # Test query
    query = "Tiểu bang nào có mức tăng phần trăm lớn nhất trong các lần khám Medicaid từ năm 2022 đến năm 2023"
    
    response = agent.invoke(query=query)
    print(f"Query: {query}\n")
    print(f"Output: {response.get('output')}\n")
    print(f"Intermediate steps: {len(response.get('intermediate_steps', []))} steps")
    
    # print("\n" + "=" * 50)
    # print("TEST 2: Streaming (progressive response)")
    # print("=" * 50)
    
    # async def test_streaming():
    #     print(f"Query: {query}\n")
    #     async for chunk in agent.astream(query=query):
    #         if 'actions' in chunk:
    #             for action in chunk['actions']:
    #                 print(f"🔧 Calling tool: {action.tool}")
    #                 print(f"   Input: {action.tool_input}")
    #         elif 'steps' in chunk:
    #             for step in chunk['steps']:
    #                 print(f"✅ Tool result received")
    #         elif 'output' in chunk:
    #             print(f"\n📝 Final answer: {chunk['output']}")
    
    # asyncio.run(test_streaming())
    # print("=" * 50)