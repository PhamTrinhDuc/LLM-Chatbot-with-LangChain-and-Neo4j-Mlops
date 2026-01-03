import threading

from langchain.tools import BaseTool

from chains.hospital_cypher_chain import HospitalCypherChain


class CypherTool(BaseTool):
    """
    Tool for querying structured hospital data using Cypher queries on Neo4j Graph.

    Uses HospitalCypherChain to answer objective questions about patients, physicians,
    hospitals, insurance payers, and visit statistics.
    """

    name: str = "Graph"
    description: str = """Useful for answering questions about patients, physicians, \
    hospitals, insurance payers, patient review statistics, and hospital visit details. \
    Use the entire prompt as input to the tool. For instance, if the prompt is \
    "How many visits have there been?", the input should be "How many visits have there been?"."""

    class Config:
        extra = "allow"  # Cho phép tạo thuộc tính mới sau khi init

    def __init__(self, llm_model: str):
        """Initialize the CypherTool with a HospitalCypherChain instance."""
        super().__init__()
        self.llm_model = llm_model
        self._cypher_chain = None

    @property
    def cypher_chain(self):
        if not self._cypher_chain:
            with threading.Lock():
                self._cypher_chain = HospitalCypherChain(llm_model=self.llm_model)
        return self._cypher_chain

    def _run(self, query: str) -> dict[str, any]:
        """
        Synchronous execution of Cypher query.

        Args:
            query: User's question about hospital data

        Returns:
            Dictionary with 'result' (answer) and 'generated_cypher' (Cypher query)
        """
        answer, generated_cypher = self.cypher_chain.invoke(query=query)

        return {"result": answer, "generated_cypher": generated_cypher}

    async def _arun(self, query: str) -> dict[str, any]:
        """
        Asynchronous execution of Cypher query.

        Args:
            query: User's question about hospital data

        Returns:
            Dictionary with 'result' (answer) and 'generated_cypher' (Cypher query)
        """
        answer, generated_cypher = await self.cypher_chain.ainvoke(query=query)

        return {"result": answer, "generated_cypher": generated_cypher}


if __name__ == "__main__":
    tool = CypherTool(llm_model="groq")
    response = tool.invoke(
        input="Tiểu bang nào có mức tăng phần trăm lớn nhất trong các lần khám Medicaid từ năm 2022 đến năm 2023"
    )
    print(response)
    print("=" * 50)
