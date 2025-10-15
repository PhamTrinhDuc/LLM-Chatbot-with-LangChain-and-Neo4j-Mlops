import os
import sys
sys.path.append(os.path.join(os.path.dirname(__file__), ".."))
from dotenv import load_dotenv
from langchain import hub
from langchain.agents import AgentExecutor, Tool, create_openai_functions_agent
from langchain_openai import ChatOpenAI

from tools.wait_times import get_current_wait_times, get_most_available_hospital
from tools.cypher_tool import CypherTool
from tools.review_tool import ReviewTool
from utils.config import AppConfig

load_dotenv(".env.dev")


class HospitalRAGAgent:
    """
    RAG Agent for answering hospital-related questions using multiple tools.
    
    Combines Cypher queries, semantic search, and real-time wait time data
    to provide comprehensive answers about hospital operations.
    """
    
    def __init__(self):
        """Initialize the HospitalRAGAgent with tools and agent executor."""
        self._agent_executor = None
        self._tools = None
        self._prompt = None
    
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
            CypherTool(),
            
            ReviewTool(),
            
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
            llm = ChatOpenAI(
                model=AppConfig.hospital_qa_model,
                temperature=AppConfig.temperature
            )
            
            agent = create_openai_functions_agent(
                llm=llm,
                prompt=self.prompt,
                tools=self.tools,
            )
            
            self._agent_executor = AgentExecutor(
                agent=agent,
                tools=self.tools,
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
        result = self.agent_executor.invoke({"input": query})
        print(result)
        return self._extract_metadata(result)
    
    async def ainvoke(self, query: str) -> dict:
        """
        Asynchronous execution of agent query.
        
        Args:
            query: User's question about hospital data
            
        Returns:
            Dictionary with 'output', 'intermediate_steps', and 'metadata'
        """
        result = await self.agent_executor.ainvoke({"input": query})
        return self._extract_metadata(result)
    
    def stream(self, query: str):
        """
        Synchronous streaming execution of agent query.
        
        Yields intermediate steps and final output as they become available.
        
        Args:
            query: User's question about hospital data
            
        Yields:
            Dictionary chunks containing 'actions', 'steps', or 'output'
        """
        for chunk in self.agent_executor.stream({"input": query}):
            yield chunk
    
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
        async for chunk in self.agent_executor.astream({"input": query}):
            yield chunk


if __name__ == "__main__":
    import asyncio
    
    # Test with class instance
    agent = HospitalRAGAgent()
    
    # Test query
    query = "What have patients said about hospital efficiency?"
    
    print("=" * 50)
    print("TEST 1: Regular invoke (wait for full response)")
    print("=" * 50)
    response = agent.invoke(query=query)
    print(f"Query: {query}\n")
    print(f"Output: {response.get('output')}\n")
    print(f"Intermediate steps: {len(response.get('intermediate_steps', []))} steps")
    
    print("\n" + "=" * 50)
    print("TEST 2: Streaming (progressive response)")
    print("=" * 50)
    
    async def test_streaming():
        print(f"Query: {query}\n")
        async for chunk in agent.astream(query=query):
            if 'actions' in chunk:
                for action in chunk['actions']:
                    print(f"🔧 Calling tool: {action.tool}")
                    print(f"   Input: {action.tool_input}")
            elif 'steps' in chunk:
                for step in chunk['steps']:
                    print(f"✅ Tool result received")
            elif 'output' in chunk:
                print(f"\n📝 Final answer: {chunk['output']}")
    
    asyncio.run(test_streaming())
    print("=" * 50)