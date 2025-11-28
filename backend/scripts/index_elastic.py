# reference: https://www.elastic.co/search-labs/blog/rag-agent-tool-elasticsearch-langchain
import re
import os
import sys
import requests
sys.path.append(os.path.join(os.path.dirname(__file__), ".."))
import json
import time
from typing import Literal, List, Union
from openai import OpenAI
from google import generativeai as genai
from elasticsearch import Elasticsearch, helpers
from langchain_text_splitters import RecursiveCharacterTextSplitter
from tqdm import tqdm
from utils import AppConfig


class Chunker: 
  def __init__(self, chunk_size: int=512, overlap: int=50): 
    self.chunk_size = chunk_size
    self.overlap = overlap
    self.text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=self.chunk_size,
        chunk_overlap=self.overlap,
        separators=["\n\n", "\n", ". ", ", ", " ", ""]
    )

  def load_pdf(self, file_path: str) -> str: 
    """Load PDF và trả về toàn bộ text"""
    reader = pypdf.PdfReader(file_path)
    text = ""
    for page in reader.pages:
      page_text = page.extract_text()
      if page_text:
        text += page_text + "\n"
    return text.strip()

  def load_pdf_by_pages(self, file_path: str) -> list[dict]:
    """Load PDF và trả về text theo từng trang với metadata"""
    reader = pypdf.PdfReader(file_path)
    pages = []
    for idx, page in enumerate(reader.pages):
      page_text = page.extract_text()
      if page_text:
        pages.append({
          "page_number": idx + 1,
          "content": page_text.strip()
        })
    return pages

  def chunk_text(self, text: str) -> list[str]: 
    """Chunk text thành các đoạn nhỏ"""
    chunks = self.text_splitter.split_text(text)
    return chunks

  def chunk_pdf(self, file_path: str) -> list[dict]:
    """Chunk PDF và trả về chunks với metadata"""
    pages = self.load_pdf_by_pages(file_path)
    all_chunks = []
    
    for page_data in pages:
      page_chunks = self.chunk_text(page_data["content"])
      for chunk_idx, chunk in enumerate(page_chunks):
        all_chunks.append({
          "chunk_id": len(all_chunks),
          "page_number": page_data["page_number"],
          "chunk_index": chunk_idx,
          "content": chunk,
          "char_count": len(chunk)
        })
    
    return all_chunks

  def chunk_pdf_simple(self, file_path: str) -> list[str]:
    """Chunk toàn bộ PDF thành list các chunks (không có metadata)"""
    text = self.load_pdf(file_path)
    return self.chunk_text(text)

  def save_chunks(self, chunks: list[dict] | list[str], output_path: str, format: Literal["json", "jsonl", "txt"] = "json") -> None:
    """
    Lưu chunks ra file
    
    Args:
      chunks: List các chunks (có thể là list[dict] hoặc list[str])
      output_path: Đường dẫn file output
      format: Định dạng file ("json", "jsonl", "txt")
    """
    os.makedirs(os.path.dirname(output_path), exist_ok=True) if os.path.dirname(output_path) else None
    
    if format == "json":
      with open(output_path, "w", encoding="utf-8") as f:
        json.dump(chunks, f, ensure_ascii=False, indent=2)
    
    elif format == "jsonl":
      with open(output_path, "w", encoding="utf-8") as f:
        for chunk in chunks:
          if isinstance(chunk, dict):
            f.write(json.dumps(chunk, ensure_ascii=False) + "\n")
          else:
            f.write(json.dumps({"content": chunk}, ensure_ascii=False) + "\n")
    
    elif format == "txt":
      with open(output_path, "w", encoding="utf-8") as f:
        for idx, chunk in enumerate(chunks):
          content = chunk["content"] if isinstance(chunk, dict) else chunk
          f.write(f"=== Chunk {idx} ===\n{content}\n\n")
    
    print(f"Đã lưu {len(chunks)} chunks vào {output_path}")
   


class ElasticsearchPaperIndexer:
    def __init__(self, model: Literal['google', 'openai', 'hf_api']='hf_api'):
        """
        Args:
            index_name: Tên index trong Elasticsearch
            embedding_model: Model OpenAI để tạo embedding
            batch_size: Số lượng papers xử lý mỗi batch
            vector_size: Kích thước vector (512 hoặc 1536)
        """
        self.index_name = AppConfig.INDEX_NAME
        self.model = model
        self.batch_size = AppConfig.BATCH_SIZE
        self.vector_size = AppConfig.VECTOR_SIZE

        # Khởi tạo clients
        els_host = os.getenv("ELS_HOST", "localhost")
        els_port = os.getenv("ELS_PORT", "9200")
        self.els_client = Elasticsearch([f"http://{els_host}:{els_port}"])

        
        if model == "google": 
            genai.configure(api_key=AppConfig.GOOGLE_API_KEY)
        else:
            self.openai_client = OpenAI(api_key=AppConfig.OPENAI_API_KEY)

    def _get_embeddings(self, text: Union[str, List[str]]) -> list[float]:
      """Get embedding from OpenAI"""
      if self.model == "openai":
          response = self.openai_client.embeddings.create(
              input=text,
              model=AppConfig.OPENAI_EMBEDDING,
              dimensions=AppConfig.VECTOR_SIZE
          )
          return [embedding.embedding for embedding in response.data]
      elif self.model == "google": 
        response = genai.embed_content(
            content=text,
            model=AppConfig.GOOGLE_EMBEDDING, 
            output_dimensionality=AppConfig.VECTOR_SIZE)
        return response['embedding']
      else: 
        response = requests.post(
          url=AppConfig.HF_EMBEDDING_API,
          headers={"Content-Type": "application/json"},
          json={"texts": text}
        )
        if response.status_code == 200:
            embeddings = response.json()
            if isinstance(text, str):
                return embeddings['embedding']
            else:
                return embeddings['embeddings']
        else:
            raise Exception(f"Failed to get embeddings from HF API. Status code: {response.status_code}, Response: {response.text}")

    def _get_papers(self, json_file_path: str): 
        """
        Generator để đọc và filter papers liên quan AI
        Giúp tiết kiệm memory khi xử lý file lớn
        """
        with open(json_file_path, 'r', encoding='utf-8') as f: 
            for line in f: 
              try:
                paper = json.loads(line)
                yield paper
              except json.JSONDecodeError: 
                  continue

    def _prerare_text_for_embedding(self, paper: dict[str, any]): 
        """
        Tạo trường text từ title + abstract để embedding
        """
        title = paper.get("title", "").strip()
        abstract = paper.get("abstract", "").strip()
        return f"{title}. {abstract}"
    
    def create_index(self, delete_if_exists: bool = False):
      try:
        if delete_if_exists and self.els_client.indices.exists(index=self.index_name):
            self.els_client.indices.delete(index=self.index_name)
            print(f"Đã xóa index tồn tại: {self.index_name}")
      except Exception as e:
          print(f"Lỗi trong khi xóa index. Error: {e}")

      
      mappings = {
        "mappings": {
            "properties": {
                "content": {"type": "text", "analyzer": "standard"},
                "embedding": {
                    "type": "dense_vector",
                    "dims": self.vector_size,
                    "index": True,
                    "similarity": "cosine"
                },
                "metadata": {  
                    "type": "object",
                    "properties": {
                        "authors": {"type": "text"},
                        "year": {"type": "keyword"},
                        "arxiv_id": {"type": "keyword"},
                        "doi": {"type": "keyword"},
                        "journal_ref": {"type": "text"},
                        "submitter": {"type": "keyword"},
                        "categories": {"type": "keyword"},
                        "title": {"type": "text"},
                        "abstract": {"type": "text"}
                    }
                }
            }
        }
    }

      self.els_client.indices.create(index=self.index_name, body=mappings)
      print(f"Created index: {self.index_name}")

    def _process_batch(self, papers: list[dict], start_id: int): 
        """
        Embedding + index batch vào Elasticsearch bằng Bulk API
        """
        texts = [self._prerare_text_for_embedding(paper=p) for p in papers]
        embeddings = self._get_embeddings(text=texts)

        # chuẩn bị bulk action

        def generate_actions(): 
          for idx, (paper, embedding) in enumerate(zip(papers, embeddings)): 
             doc_id = f"{start_id + idx}"
             
             
             yield {
                "_on_type": "index", 
                "_index": self.index_name, 
                "_id": doc_id, 
                "_source": {
                    "content": texts[idx],
                    "embedding": embedding,
                    "metadata": { 
                        "arxiv_id": paper.get("id"),
                        "submitter": paper.get("submitter"),
                        "authors": paper.get("authors"),
                        "title": paper.get("title"),
                        "comments": paper.get("comments"),
                        "journal_ref": paper.get("journal-ref"),
                        "doi": paper.get("doi"),
                        "categories": paper.get("categories"),
                        "year": paper.get("versions", [{}])[0].get("created", "N/A").split()[-3] if paper.get("versions") else "N/A",
                        "abstract": paper.get("abstract")
                    }
                }
             }
        
        client_with_options = self.els_client.options(request_timeout=30)
        success, failed = helpers.bulk(
            client=client_with_options,
            actions=generate_actions(),
            chunk_size=self.batch_size
        )
        if failed: 
          print(f"Lỗi trong khi index document batch. Error: {failed}")
           
    def upload_to_els(self, json_file_path: str, max_papers: int = None):
      """Upload toàn bộ papers vào Elasticsearch theo batch."""
      print("=" * 10 + " Bắt đầu quá trình xử lý... " + "=" * 10)

      # Đếm tổng số dòng (ước lượng)
      total_lines = 0
      with open(json_file_path, 'r', encoding='utf-8') as f:
          for _ in f:
              total_lines += 1

      total_to_process = min(total_lines, max_papers) if max_papers else total_lines
      print(f"Tổng số papers sẽ xử lý: {total_to_process}")

      batch = []
      total_uploaded = 0
      doc_id_counter = 0

      with tqdm(total=total_to_process, desc="Indexing to Elasticsearch") as pbar:
          for paper in self._get_papers(json_file_path):
              batch.append(paper)

              if len(batch) >= self.batch_size:
                  self._process_batch(batch, doc_id_counter)
                  total_uploaded += len(batch)
                  doc_id_counter += len(batch)
                  pbar.update(len(batch))
                  batch = []
                  time.sleep(1) 

                  if max_papers and total_uploaded >= max_papers:
                      break

          # Xử lý batch cuối
          if batch and (not max_papers or total_uploaded < max_papers):
              self._process_and_index_batch(batch, doc_id_counter)
              total_uploaded += len(batch)
              pbar.update(len(batch))

      print(f"\nHoàn thành! Tổng papers đã index: {total_uploaded}") 

    def get_stats(self): 
       return self.els_client.count(index=self.index_name)

if __name__ == "__main__":
    PDF_FILE = "./data/arxiv_dataset/arxiv-ai-papers.json"
    
    indexer = ElasticsearchPaperIndexer(
        model="hf_api"
    )
    indexer.create_index(delete_if_exists=True)
    
    indexer.upload_to_els(
        json_file_path=JSON_FILE,
        max_papers=1000
    )
    
    # kiểm tra info
    collection_info = indexer.get_stats()
    print(collection_info)