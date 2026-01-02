import os
import sys
sys.path.append(os.path.join(os.path.dirname(__file__), ".."))
from dotenv import load_dotenv
load_dotenv()
from openai import OpenAI
from google import generativeai as genai
from elasticsearch import Elasticsearch
from typing import List, Dict, Any, Literal, Optional
import asyncio
from utils import AppConfig, logger


class HealthcareRetriever:
    """
    Hybrid Search Retriever cho DSM-5 Vietnamese psychiatric manual.
    
    Chiến lược search:
    ─────────────────────────────────────────────────────────────────
    1. KEYWORD SEARCH (BM25):
       - Multi-match trên title (boost cao), content, context_headers
       - Dùng Vietnamese analyzer (đã bỏ dấu, lowercase)
       - Phrase matching cho medical terms
       
    2. SEMANTIC SEARCH (kNN):
       - Dense vector search với cosine similarity
       - Tốt cho câu hỏi dài, paraphrase, đồng nghĩa
       
    3. HYBRID + RRF:
       - Reciprocal Rank Fusion kết hợp 2 phương pháp
       - Ưu tiên documents xuất hiện trong cả 2 results
       
    4. HIERARCHICAL BOOST:
       - Boost documents cùng section với top results
       - Trả về context (parent, siblings) khi cần
    ─────────────────────────────────────────────────────────────────
    """
    
    def __init__(
        self,
        model_name: Literal["openai", "google"] = "openai",
    ):
        self.index_name = AppConfig.INDEX_NAME_ELS
        self.model_name = model_name
        self.vector_size = AppConfig.VECTOR_SIZE

        # Elasticsearch client
        self.els_client = Elasticsearch([f"http://{AppConfig.ELS_HOST}:{AppConfig.ELS_PORT}"])

        # Embedding client
        if model_name == "google": 
            self.embed_model = AppConfig.GOOGLE_EMBEDDING
            genai.configure(api_key=AppConfig.GOOGLE_API_KEY)
        else:
            self.embed_model = AppConfig.OPENAI_EMBEDDING
            self.openai_client = OpenAI(api_key=AppConfig.OPENAI_API_KEY)

    def _get_embedding(self, text: str) -> List[float]:
        """Get embedding vector for query"""
        if self.model_name == "openai":
            response = self.openai_client.embeddings.create(
                input=text,
                model=self.embed_model,
                dimensions=self.vector_size
            )
            return response.data[0].embedding
        else: 
            response = genai.embed_content(
                content=text,
                model=self.embed_model, 
                output_dimensionality=self.vector_size)
            return response['embedding']

    def _build_keyword_query(
        self, 
        query: str, 
        size: int = 20,
        boost_title: float = 3.0,
        boost_context: float = 1.5
    ) -> Dict:
        """
        Build BM25 keyword query với multi-match strategy.
        
        Strategy:
        - title^3: Boost cao cho exact match tiêu đề
        - sub_title^2: Boost cho tiêu chí A, B, C...
        - context_headers^1.5: Breadcrumb context
        - content: Nội dung chính
        """
        return {
            "query": {
                "bool": {
                    "should": [
                        # Multi-match với cross_fields (tìm từ across all fields)
                        {
                          "multi_match": {
                              "query": query,
                              "fields": [
                                  f"title^{boost_title}",
                                  "sub_title^2",
                                  f"context_headers^{boost_context}",
                                  "content"
                              ],
                              "type": "best_fields",
                              "operator": "or",
                              "minimum_should_match": "30%"
                          }
                        },
                        # Phrase match cho medical terms (exact phrase boost)
                        {
                          "multi_match": {
                              "query": query,
                              "fields": ["title^4", "content^2"],
                              "type": "phrase",
                              "slop": 2  # Cho phép 2 từ xen giữa
                          }
                        },
                        # Match trên parent_section_title để lấy context
                        {
                          "match": {
                              "parent_section_title": {
                                  "query": query,
                                  "boost": 1.0
                              }
                          }
                        }
                    ],
                    "minimum_should_match": 1
                }
            },
            "size": size,
            "_source": ["title", "sub_title", "content", "section_id", 
                       "parent_section_id", "parent_section_title", 
                       "context_headers", "page_start"]
        }

    def _build_vector_query(
        self, 
        query_vector: List[float], 
        size: int = 20,
        num_candidates: int = 100
    ) -> Dict:
        """
        Build kNN vector search query.
        
        Strategy:
        - k: Số results trả về
        - num_candidates: Số candidates xem xét (cao hơn = chính xác hơn nhưng chậm hơn)
        """
        return {
          "knn": {
              "field": "embedding",
              "query_vector": query_vector,
              "k": size,
              "num_candidates": num_candidates
          },
          "_source": ["title", "sub_title", "content", "section_id", 
                      "parent_section_id", "parent_section_title", 
                      "context_headers", "page_start"]
        }

    def _reciprocal_rank_fusion(
        self,
        keyword_hits: List[Dict],
        vector_hits: List[Dict],
        k: int = 60,
        keyword_weight: float = 1.0,
        vector_weight: float = 1.0
    ) -> Dict[str, Dict]:
        """
        RRF với weighted scores.
        
        Công thức: score = w1/(k + rank_keyword) + w2/(k + rank_vector)
        
        Args:
            k: RRF constant (60 là standard, cao hơn = ít phân biệt rank)
            keyword_weight: Weight cho BM25 results
            vector_weight: Weight cho semantic results
        """
        doc_scores = {}
        doc_data = {}
        
        # Process keyword results
        for rank, hit in enumerate(keyword_hits, start=1):
            doc_id = hit["_id"]
            score = keyword_weight / (k + rank)
            doc_scores[doc_id] = doc_scores.get(doc_id, 0) + score
            doc_data[doc_id] = hit["_source"]
            doc_data[doc_id]["_keyword_rank"] = rank
            doc_data[doc_id]["_keyword_score"] = hit.get("_score", 0)
        
        # Process vector results
        for rank, hit in enumerate(vector_hits, start=1):
            doc_id = hit["_id"]
            score = vector_weight / (k + rank)
            doc_scores[doc_id] = doc_scores.get(doc_id, 0) + score
            if doc_id not in doc_data:
                doc_data[doc_id] = hit["_source"]
            doc_data[doc_id]["_vector_rank"] = rank
            doc_data[doc_id]["_vector_score"] = hit.get("_score", 0)
        
        # Add RRF score to doc_data
        for doc_id, score in doc_scores.items():
            doc_data[doc_id]["_rrf_score"] = score
            # Bonus nếu xuất hiện trong cả 2 results
            if "_keyword_rank" in doc_data[doc_id] and "_vector_rank" in doc_data[doc_id]:
                doc_data[doc_id]["_rrf_score"] *= 1.2  # 20% boost
        
        return doc_data

    def _get_section_context(
        self, 
        section_ids: List[str], 
        max_siblings: int = 2
    ) -> List[Dict]:
        """
        Lấy thêm context từ parent và sibling sections.
        Useful khi user hỏi về một phần của tiêu chí.
        """
        if not section_ids:
            return []
            
        # Get parent section IDs
        parent_ids = set()
        for sid in section_ids:
            parts = sid.rsplit('.', 1)
            if len(parts) > 1:
                parent_ids.add(parts[0])
        
        if not parent_ids:
            return []
        
        # Query siblings với cùng parent
        query = {
            "query": {
                "bool": {
                    "should": [
                        {"terms": {"parent_section_id": list(parent_ids)}},
                        {"terms": {"section_id": list(parent_ids)}}
                    ]
                }
            },
            "size": max_siblings * len(parent_ids),
            "_source": ["title", "section_id", "content"]
        }
        
        try:
            response = self.els_client.search(index=self.index_name, body=query)
            return [hit["_source"] for hit in response["hits"]["hits"]]
        except Exception as e:
            logger.warning(f"Error fetching section context: {str(e)}")
            return []

    def hybrid_search(
        self,
        query: str,
        top_k: int = 10,
        rrf_k: int = 60,
        keyword_weight: float = 1.0,
        vector_weight: float = 1.2,  # Slight boost cho semantic
        include_context: bool = False,
        num_candidates: int = 100
    ) -> List[Dict[str, Any]]:
        """
        Hybrid search với RRF fusion.
        
        Args:
            query: Search query
            top_k: Số results trả về
            rrf_k: RRF constant
            keyword_weight: Weight cho BM25
            vector_weight: Weight cho semantic search
            include_context: Có lấy thêm sibling sections không
            num_candidates: Số candidates cho kNN
            
        Returns:
            List of ranked results với scores và metadata
        """
        # Generate query embedding
        query_vector = self._get_embedding(text=query)
        
        # Lấy nhiều hơn top_k để RRF có đủ candidates
        fetch_size = min(top_k * 3, 50)
        
        # Execute both searches
        keyword_query = self._build_keyword_query(query, size=fetch_size)
        vector_query = self._build_vector_query(query_vector, size=fetch_size, num_candidates=num_candidates)
        
        try:
            keyword_response = self.els_client.search(index=self.index_name, body=keyword_query)
            vector_response = self.els_client.search(index=self.index_name, body=vector_query)
        except Exception as e:
            logger.error(f"Elasticsearch search failed: {str(e)}")
            raise
        
        keyword_hits = keyword_response["hits"]["hits"]
        vector_hits = vector_response["hits"]["hits"]
        
        # Log search stats
        logger.info(f"Keyword hits: {len(keyword_hits)}, Vector hits: {len(vector_hits)}")
        
        # Apply RRF fusion
        doc_data = self._reciprocal_rank_fusion(
            keyword_hits=keyword_hits,
            vector_hits=vector_hits,
            k=rrf_k,
            keyword_weight=keyword_weight,
            vector_weight=vector_weight
        )
        
        # Sort by RRF score
        sorted_docs = sorted(
            doc_data.items(), 
            key=lambda x: x[1].get("_rrf_score", 0), 
            reverse=True
        )[:top_k]
        
        # Format results
        results = []
        section_ids = []
        
        for doc_id, data in sorted_docs:
            result = {
                "id": doc_id,
                "title": data.get("title", ""),
                "sub_title": data.get("sub_title", ""),
                "content": data.get("content", ""),
                "section_id": data.get("section_id", ""),
                "parent_section_title": data.get("parent_section_title", ""),
                "context_headers": data.get("context_headers", ""),
                "page_start": data.get("page_start"),
                "scores": {
                    "rrf": round(data.get("_rrf_score", 0), 4),
                    "keyword_rank": data.get("_keyword_rank"),
                    "vector_rank": data.get("_vector_rank"),
                }
            }
            results.append(result)
            if data.get("section_id"):
                section_ids.append(data["section_id"])
        
        # Optionally add section context
        if include_context and section_ids:
            context_docs = self._get_section_context(section_ids)
            for result in results:
                result["related_sections"] = [
                    doc for doc in context_docs 
                    if doc.get("section_id") != result["section_id"]
                ][:3]
        
        return results

    def search_by_criteria(
        self,
        disorder_name: str,
        criteria: Optional[str] = None  # "A", "B", "C"...
    ) -> List[Dict[str, Any]]:
        """
        Tìm kiếm theo tên rối loạn và tiêu chí cụ thể.
        Ví dụ: search_by_criteria("Rối loạn trầm cảm", "A")
        """
        query_parts = [disorder_name]
        if criteria:
            query_parts.append(f"Tiêu chí {criteria}")
        
        # Build specific query for criteria
        query = {
            "query": {
                "bool": {
                    "must": [
                        {
                            "multi_match": {
                                "query": disorder_name,
                                "fields": ["title^3", "parent_section_title^2", "context_headers"],
                                "type": "phrase",
                                "slop": 3
                            }
                        }
                    ],
                    "should": [
                        {
                            "match": {
                                "sub_title": {
                                    "query": f"Tiêu chí {criteria}" if criteria else "",
                                    "boost": 5
                                }
                            }
                        }
                    ] if criteria else []
                }
            },
            "size": 10,
            "_source": ["title", "sub_title", "content", "section_id", 
                       "parent_section_title", "context_headers"]
        }
        
        response = self.els_client.search(index=self.index_name, body=query)
        return [
            {
                "id": hit["_id"],
                "score": hit["_score"],
                **hit["_source"]
            }
            for hit in response["hits"]["hits"]
        ]

    def invoke(
        self, 
        query: str, 
        config: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """
        LangChain-compatible synchronous invoke.
        """
        try:
            logger.info(f"Processing sync healthcare query: {query}")
            config = config or {}
            return self.hybrid_search(
                query=query,
                top_k=config.get("top_k", 10),
                rrf_k=config.get("rrf_k", 60),
                keyword_weight=config.get("keyword_weight", 1.0),
                vector_weight=config.get("vector_weight", 1.2),
                include_context=config.get("include_context", False)
            )
        except Exception as e: 
            logger.error(f"Error during sync process healhcrare: {str(e)}")
            raise
          
    async def ainvoke(
        self, 
        query: str, 
        config: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """
        LangChain-compatible async invoke.
        """
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self.invoke, query, config)
    
    def format_context_for_llm(self, results: List[Dict], max_chars: int = 8000) -> str:
      """
      Format search results thành context string cho LLM.
      
      Output format:
      ─────────────────────────────────────────────────────────────────
      [Section 1.2.3] Tiêu đề section
      Tiêu chí: A
      
      Nội dung chunk...
      ─────────────────────────────────────────────────────────────────
      """
      context_parts = []
      total_chars = 0
      
      for result in results:
          header = f"[Section {result.get('section_id', 'N/A')}] {result.get('title', '')}"
          if result.get('sub_title'):
              header += f"\nTiêu chí: {result['sub_title']}"
          
          content = result.get('content', '')
          entry = f"{header}\n\n{content}\n{'─' * 60}\n"
          
          if total_chars + len(entry) > max_chars:
              break
              
          context_parts.append(entry)
          total_chars += len(entry)
      
      return "\n".join(context_parts)


if __name__ == "__main__":
    retriever = HealthcareRetriever(model_name="openai")
    
    # Test hybrid search
    query = "Rối loạn trầm cảm"
    print(f"\n🔍 Query: '{query}'\n") 
    
    results = retriever.invoke(query, config={"top_k": 5, "include_context": False})
    
    print(f"Found {len(results)} results:\n")
    for i, result in enumerate(results, 1):
      print(f"#{i} [{result['section_id']}] {result['title'][:60]}...")
      print(f"   Sub-title: {result.get('sub_title', 'N/A')}")
      print(f"   Scores: {result['scores']}")
      print(f"   Content: {result['content']}")
      print()
    # print(retriever.format_context_for_llm(results, max_chars=2000))   