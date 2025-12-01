import os
import sys
import json
sys.path.append(os.path.join(os.path.dirname(__file__), ".."))
import requests
import time
import tqdm
from typing import List, Union, Literal
from google import generativeai as genai 
from openai import OpenAI
from elasticsearch import Elasticsearch, helpers
from utils import AppConfig, logger


class ElsIndexer: 
  def __init__(self, 
               model_name: Literal['google', 'openai', 'hf_api']='hf_api', 
               batch_size: int=64, 
               chunk_path: str=None): 

    self._client = None
    self.index_name = AppConfig.INDEX_NAME_ELS
    self.batch_size = batch_size
    self.chunk_path = chunk_path or AppConfig.DSM5_CHUNKS_PATH

    if model_name == "google": 
        genai.configure(api_key=AppConfig.GOOGLE_API_KEY)
    else:
        self.openai_client = OpenAI(api_key=AppConfig.OPENAI_API_KEY)

  @property
  def client(self): 
    if self._client is None: 
      self._client = Elasticsearch([f"http://{self.els_host}:{self.els_port}"])
    
    return self._client

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

  def _get_chunks(self): 
    with open(self.chunk_path, 'r', encoding="utf-8") as f: 
      for item in f: 
        try: 
          chunk = json.loads(item)
          yield chunk
        except json.JSONDecodeError:
          logger.warning(f"Cannot read chunk")
          continue
  
  def create_index(self): 
    """
    Tạo Elasticsearch index với mapping phù hợp cho DSM-5 chunks.
    
    Elasticsearch Field Types:
    ─────────────────────────────────────────────────────────────────
    • keyword: Exact match, dùng cho filter/aggregation, KHÔNG tokenize
              VD: "1.2.3" được lưu nguyên, search phải đúng y chang
              
    • text:    Full-text search, CÓ tokenize (tách từ, lowercase...)
              VD: "Rối loạn tâm thần" → ["rối", "loạn", "tâm", "thần"]
              
    • text + fields.keyword: Vừa full-text search VỪA exact match
              - title: "Rối loạn" → tìm được "rối" hoặc "loạn"
              - title.keyword: "Rối loạn" → phải đúng y chang
              
    • integer: Số nguyên, dùng cho range query (>, <, between)
    
    • dense_vector: Vector embedding cho semantic search (KNN)
    ─────────────────────────────────────────────────────────────────
    
    Analyzer "vietnamese":
    - tokenizer: standard → tách theo khoảng trắng và dấu câu
    - lowercase → chuyển thành chữ thường
    - asciifolding → bỏ dấu (để search "roi loan" tìm được "rối loạn")
    """
    mappings = {
      # ============================================================
      # SETTINGS: Cấu hình index-level
      # ============================================================
      "settings": {
        "number_of_shards": 1,      # Số partition của data (1 cho dev, nhiều hơn cho prod)
        "number_of_replicas": 0,    # Số bản sao (0 cho dev, 1+ cho prod high-availability)
        "analysis": {
          "analyzer": {
            "vietnamese": {
              "type": "custom",          # Custom analyzer tự định nghĩa
              "tokenizer": "standard",   # Tách từ theo chuẩn (khoảng trắng, dấu câu)
              "filter": [
                "lowercase",             # "Rối Loạn" → "rối loạn"
                "asciifolding"           # "rối loạn" → "roi loan" (bỏ dấu để search dễ hơn)
              ]
            }
          }
        }
      },
      
      # ============================================================
      # MAPPINGS: Định nghĩa schema cho documents
      # ============================================================
      "mappings": {
        "properties": {
          # ─────────── ID & Structure ───────────
          # keyword: exact match, dùng cho filter
          "index": {"type": "keyword"},              # "chunk-1", "chunk-2" - ID duy nhất
          "section_id": {"type": "keyword"},         # "1.2.3" - mã section
          "parent_section_id": {"type": "keyword"},  # "1.2" - mã section cha
          
          # ─────────── Searchable Text Fields ───────────
          # text + keyword: vừa search full-text, vừa filter exact
          "title": {
              "type": "text",                        # Full-text search
              "analyzer": "vietnamese",              # Dùng analyzer tự định nghĩa
              "fields": {
                  "keyword": {                       # Sub-field cho exact match
                    "type": "keyword", 
                    "ignore_above": 256              # Bỏ qua nếu > 256 chars
                  }
              }
          },
          "sub_title": {
              "type": "text",
              "analyzer": "vietnamese",
              "fields": {
                  "keyword": {"type": "keyword", "ignore_above": 256}
              }
          },
          "parent_section_title": {
              "type": "text",
              "analyzer": "vietnamese",
              "fields": {
                  "keyword": {"type": "keyword", "ignore_above": 256}
              }
          },
          
          # ─────────── Content Fields ───────────
          # Chỉ cần text (không cần keyword vì quá dài)
          "context_headers": {
            "type": "text",
            "analyzer": "vietnamese"
          },
          "content": {
            "type": "text",
            "analyzer": "vietnamese" 
          },

          # ─────────── Metadata ───────────
          "page_start": {"type": "integer"},         # Số trang, dùng cho range query
          "merge_from": {"type": "text"},           # Thông tin merge (nếu có)
          
          # ─────────── Vector Embedding ───────────
          "embedding": {
             "type": "dense_vector",                 # Vector số thực
             "dims": AppConfig.VECTOR_SIZE,          # Số chiều (768, 1024, etc.)
             "index": True,                          # Cho phép KNN search
             "similarity": "cosine"                  # Độ tương đồng cosine (phổ biến nhất)
          }
        }
      }
    }

    try: 
      self.client.indices.create(index=self.index_name, body=mappings)
      logger.info("Create index for ELS successful")
    except Exception as e: 
      logger.error(f"Error while creating index for ELS. {str(e)} ")

  def _proces_batch(self, chunks: list[dict], start_id: int):
    """
    Embedding + index batch vào Elasticsearch bằng Bulk API
    """ 
    contents = [chunk['content'] for chunk in chunks]
    embeddings = self._get_embeddings(text=contents)

    # Chuẩn bị Bulk action
    def generate_actions(): 
      for idx, (chunk, embedding) in enumerate(zip(chunks, embeddings)): 
        doc_id = f"{start_id + idx}"

        yield {
          "_on_type": "idnex", 
          "_index": self.index_name, 
          "_id": doc_id, 
          "_source": {
            "index": chunk.get('index'), 
            "section_id": chunk.get('section_id'), 
            "parent_section_id": chunk.get('parent_section_id'), 
            "title": chunk.get('title'), 
            "sub_title": chunk.get("sub_title"), 
            "parent_section_title": chunk.get("parent_section_title"), 
            "context_headers": chunk.get("context_headers"),
            "content": chunk.get("content"), 
            "page_start": chunk.get("metdata").get("page_start"), 
            "merge_from": chunk.get("metdata").get("merge_from", "No merge"),
            "embedding": embedding
          }
        }
    client_with_option = self.client.options(request_timeout=10)
    success, failed = helpers.bulk(
      client=client_with_option, 
      actions=generate_actions(), 
      chunk_size=self.batch_size
    )
    if failed: 
      logger.error(f"Error while index chunk batch. {failed}")

  def upload_to_els(self):
    total_chunks = 0
    with open(self.chunk_path, mode='r', encoding="utf-8") as f: 
      for _ in f: 
        total_chunks += 1
    logger.info(f"Total chunks to process: {total_chunks}")

    batch = []
    chunk_id = 0
    total_uploaded = 0

    with tqdm.tqdm(total=total_chunks, desc="Indexing to ELS") as pbar: 
      for chunk in self._get_chunks(): 
        batch.append(chunk)

        if len(batch) >= self.batch_size: 
          self._proces_batch(chunks=batch, start_id=chunk_id)
          total_uploaded += len(batch)
          chunk_id += len(batch)
          pbar.update(len(batch))
          batch = []
          time.sleep(1)

    
      if batch: 
        self._proces_batch(chunks=batch, start_id=chunk_id)
        total_uploaded += len(batch)
        pbar.update(len(batch))
    logger.info(f"Complete! Total chunks processed : {total_uploaded}")

  def delete_index(self): 
    if self.els_client.indices.exists(index=self.index_name):
      self.els_client.indices.delete(index=self.index_name)
      logger.info(f"Delete index {self.index_name} sucessfull")
  

def main():
  import argparse 

  parser = argparse.ArgumentParser(description="Indexing chunks to Elasticsearch")
  
  # Tạo mutually exclusive group - chỉ được chọn 1 trong các options
  group = parser.add_mutually_exclusive_group(required=True)
  
  # action="store_true" → args.index = True nếu có flag, False nếu không
  group.add_argument("--index", "-i", action="store_true", 
                     help="Index chunks to Elasticsearch")
  group.add_argument("--delete", "-d", action="store_true", 
                     help="Delete the index")
  group.add_argument("--create", "-c", action="store_true", 
                     help="Create index with mapping (without indexing data)")
  
  # Optional arguments
  parser.add_argument("--chunk-path", "-p", type=str, default=None,
                      help="Path to chunks JSON file")
  parser.add_argument("--batch-size", "-b", type=int, default=64,
                      help="Batch size for indexing (default: 64)")

  args = parser.parse_args()
  
  # Initialize indexer
  indexer = ElsIndexer(
    model_name="hf_api",
    batch_size=args.batch_size,
    chunk_path=args.chunk_path
  )

  if args.index: 
    logger.info("Starting indexing process...")
    indexer.create_index()  # Tạo index trước
    indexer.upload_to_els()
  elif args.delete: 
    logger.info(f"Deleting index: {indexer.index_name}")
    indexer.delete_index()
  elif args.create:
    logger.info(f"Creating index: {indexer.index_name}")
    indexer.create_index()

if __name__ == "__main__": 
  main()

