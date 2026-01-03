from langchain.chains.retrieval_qa.base import RetrievalQA
from langchain.prompts import ChatPromptTemplate
from langchain_community.vectorstores import Neo4jVector

from prompt.hospital_prompt import SYSTEM_PROMPT, TEXT_NODE_PROPERTIES, USER_PROMPT
from utils import AppConfig, ModelFactory, logger


class HospitalReviewChain:
    """
    Chain for querying hospital reviews using RAG (Retrieval-Augmented Generation).

    Chain type: 'stuff' - Gộp toàn bộ context → gửi 1 prompt duy nhất cho LLM
    Phù hợp khi: Context nhỏ, LLM mạnh
    """

    def __init__(self, embedding_model: str, llm_model: str):
        """Initialize the HospitalReviewChain."""
        self.neo4j_uri = AppConfig.NEO4J_URI
        self.neo4j_user = AppConfig.NEO4J_USER
        self.neo4j_password = AppConfig.NEO4J_PASSWORD
        self.embedding_model = embedding_model
        self.llm_model = llm_model
        self._vector_index = None
        self._review_chain = None
        self._llm = None
        self._embedder = None

    @property
    def llm(self):
        """Lazy initialization of LLM model."""
        if self._llm is None:
            self._llm = ModelFactory.get_llm_model(llm_model=self.llm_model)
        return self._llm

    @property
    def embedder(self):
        """Lazy initialization of embedding model."""
        if self._embedder is None:
            self._embedder = ModelFactory.get_embedding_model(
                embedding_model=self.embedding_model
            )
        return self._embedder

    @property
    def vector_index(self) -> Neo4jVector:
        """Lazy initialization of Neo4j vector index."""
        if self._vector_index is None:
            self._vector_index = Neo4jVector.from_existing_graph(
                embedding=self.embedder,
                url=self.neo4j_uri,
                username=self.neo4j_user,
                password=self.neo4j_password,
                index_name=AppConfig.INDEX_NAME_NEO4J,
                node_label="Review",
                text_node_properties=TEXT_NODE_PROPERTIES,
                embedding_node_property="embedding",
            )
        return self._vector_index

    def _create_prompt(self) -> ChatPromptTemplate:
        """Create the prompt template for review chain."""
        return ChatPromptTemplate.from_messages(
            [("system", SYSTEM_PROMPT), ("human", USER_PROMPT)]
        )

    @property
    def review_chain(self) -> RetrievalQA:
        """Get or create the RetrievalQA chain."""
        if self._review_chain is None:
            prompt = self._create_prompt()

            self._review_chain = RetrievalQA.from_chain_type(
                llm=self.llm,
                chain_type="stuff",
                retriever=self.vector_index.as_retriever(k=AppConfig.REVIEW_TOP_K),
                return_source_documents=True,
            )

            # Override default prompt
            self._review_chain.combine_documents_chain.llm_chain.prompt = prompt

        return self._review_chain

    def _process_response(self, query: str, docs: list) -> tuple[str, list]:
        """Process documents and generate response."""

        response = self.review_chain.combine_documents_chain.invoke(
            input={
                "question": query,
                "input_documents": docs,
                "language": AppConfig.LANGUAGE,
            }
        )

        return response.get("output_text"), docs

    def invoke(self, query: str) -> tuple[str, list]:
        """
        Synchronous review query.

        Args:
            query: User's question about hospital reviews

        Returns:
            Tuple of (answer, source_documents)
        """
        try:
            logger.info(f"Processing sync review query: {query}")
            docs = self.review_chain.retriever.invoke(input=query)
            return self._process_response(query, docs)
        except Exception as e:
            logger.error(f"Error in invoke: {str(e)}")
            raise e

    async def ainvoke(self, query: str) -> tuple[str, list]:
        """
        Asynchronous review query.

        Args:
            query: User's question about hospital reviews

        Returns:
            Tuple of (answer, source_documents)
        """
        try:
            logger.info(f"Processing async review query: {query}")
            docs = await self.review_chain.retriever.ainvoke(input=query)
            return self._process_response(query, docs)
        except Exception as e:
            logger.error(f"Error in ainvoke: {str(e)}")
            raise e

    def __del__(self):
        """Cleanup when object is destroyed."""
        try:
            if self._vector_index and hasattr(self._vector_index, "_driver"):
                self._vector_index._driver.close()
        except Exception:
            pass


if __name__ == "__main__":
    chain = HospitalReviewChain(embedding_model="openai", llm_model="google")
    try:
        query = "Bệnh nhân nói gì về hiệu quả của bệnh viện?"
        answer, context = chain.invoke(query=query)
        print(f"Answer: {answer}")
        print(f"\nSource documents: {len(context)} docs")
    finally:
        # Cleanup
        del chain
