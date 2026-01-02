#!/usr/bin/env python3
"""
Script để quản lý embeddings cho Neo4j vector index.
- Insert: Tính và lưu embeddings mới
- Delete: Xóa embeddings cũ
- Recompute: Xóa rồi tính lại embeddings
"""

import os
import sys
import argparse
from dotenv import load_dotenv

# Add parent directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from neo4j import GraphDatabase
from langchain_community.vectorstores import Neo4jVector
from utils.helper import ModelFactory


class EmbeddingManager:
    """Quản lý embeddings cho Neo4j vector index."""
    
    def __init__(
        self,
        neo4j_uri: str,
        neo4j_user: str,
        neo4j_password: str,
        embedding_model: str = "openai",
    ):
        """Initialize EmbeddingManager."""
        self.neo4j_uri = neo4j_uri
        self.neo4j_user = neo4j_user
        self.neo4j_password = neo4j_password
        self.embedding_model = embedding_model
        self.driver = GraphDatabase.driver(
            self.neo4j_uri, 
            auth=(self.neo4j_user, self.neo4j_password)
        )
        self.embeddings = ModelFactory.get_embedding_model(embedding_model=embedding_model)

    def delete_embeddings(
        self,
        node_label: str = "Review",
        embedding_property: str = "embedding"
    ) -> int:
        """
        Xóa tất cả embeddings từ nodes.
        
        Args:
            node_label: Nhãn node (mặc định: "Review")
            embedding_property: Tên property embedding (mặc định: "embedding")
            
        Returns:
            Số nodes đã xóa embedding
        """
        with self.driver.session(database="neo4j") as session:
            query = f"""
            MATCH (n:`{node_label}`)
            WHERE n.`{embedding_property}` IS NOT NULL
            SET n.`{embedding_property}` = NULL
            RETURN count(n) as cleared_count
            """
            try:
                result = session.run(query)
                cleared_count = result.single()["cleared_count"]
                print(f"✅ Đã xóa embedding từ {cleared_count} nodes")
                return cleared_count
            except Exception as e:
                print(f"❌ Lỗi khi xóa embeddings: {str(e)}")
                raise
    
    def delete_vector_index(self, index_name: str = "reviews") -> None:
        """
        Xóa vector index từ Neo4j.
        
        Args:
            index_name: Tên index cần xóa
        """
        with self.driver.session(database="neo4j") as session:
            try:
                # Thử cách 1: db.index.vector.drop (Neo4j 5.13+)
                try:
                    query = f"CALL db.index.vector.drop($index_name)"
                    session.run(query, {"index_name": index_name})
                    print(f"✅ Đã xóa vector index '{index_name}' (method 1)")
                    return
                except Exception as e1:
                    if "ProcedureNotFound" not in str(e1):
                        raise
                
                # Thử cách 2: DROP INDEX (Neo4j 4.4+)
                try:
                    query = f"DROP INDEX {index_name}"
                    session.run(query)
                    print(f"✅ Đã xóa vector index '{index_name}' (method 2)")
                    return
                except Exception as e2:
                    if "No such index" in str(e2) or "does not exist" in str(e2):
                        print(f"⚠️  Index '{index_name}' không tồn tại")
                    else:
                        raise
                        
            except Exception as e:
                print(f"❌ Lỗi khi xóa index: {str(e)}")
                raise
    
    def count_pending_embeddings(
        self,
        node_label: str = "Review",
        embedding_property: str = "embedding",
        text_node_properties: list = None
    ) -> int:
        """
        Đếm số nodes cần được embedding.
        
        Args:
            node_label: Nhãn node
            embedding_property: Tên property embedding
            text_node_properties: Danh sách text properties để check
            
        Returns:
            Số nodes cần embedding
        """
        text_node_properties = text_node_properties or ["text"]
        
        with self.driver.session(database="neo4j") as session:
            query = f"""
            MATCH (n:`{node_label}`)
            WHERE n.`{embedding_property}` IS NULL
            AND any(k in $props WHERE n[k] IS NOT null)
            RETURN count(n) as pending_count
            """
            try:
                result = session.run(query, {"props": text_node_properties})
                pending_count = result.single()["pending_count"]
                return pending_count
            except Exception as e:
                print(f"❌ Lỗi khi đếm pending embeddings: {str(e)}")
                raise
    
    def insert_embeddings(
        self,
        index_name: str = "vector",
        node_label: str = "Review",
        embedding_property: str = "embedding",
        text_node_properties: list = None,
    ) -> None:
        """
        Tính toán và insert embeddings mới vào Neo4j.
        
        Args:
            index_name: Tên vector index
            node_label: Nhãn node
            embedding_property: Tên property embedding
            text_node_properties: Danh sách text properties để embedding
        """
        text_node_properties = text_node_properties or ["text"]
        
        # Kiểm tra số nodes cần embedding
        pending = self.count_pending_embeddings(
            node_label, 
            embedding_property, 
            text_node_properties
        )
        
        if pending == 0:
            print("⚠️  Không có nodes nào cần embedding")
            return
        
        print(f"⏳ Đang tính embedding cho {pending} nodes...")
        print("   (Quá trình này có thể mất vài phút tùy vào số lượng documents)")
        
        try:
            vector_index = Neo4jVector.from_existing_graph(
              embedding=self.embeddings,
              url=self.neo4j_uri,
              username=self.neo4j_user,
              password=self.neo4j_password,
              index_name=index_name,
              node_label=node_label,
              embedding_node_property=embedding_property,
              text_node_properties=text_node_properties,
            )
            
            print(f"✅ Đã insert embeddings xong!")
            print(f"   - Model: {self.embedding_model}")
            print(f"   - Index: {index_name}")
            print(f"   - Node label: {node_label}")
            
            # Verify
            with self.driver.session(database="neo4j") as session:
                query = f"""
                MATCH (n:`{node_label}`)
                WHERE n.`{embedding_property}` IS NOT NULL
                RETURN count(n) as embedded_count
                """
                result = session.run(query)
                embedded_count = result.single()["embedded_count"]
                print(f"📊 Tổng nodes có embedding: {embedded_count}")
                
        except Exception as e:
            print(f"❌ Lỗi khi insert embeddings: {str(e)}")
            raise
    
    def recompute_embeddings(
        self,
        index_name: str = "vector",
        node_label: str = "Review",
        embedding_property: str = "embedding",
        text_node_properties: list = None,
    ) -> None:
        """
        Xóa index cũ, xóa embeddings, và tính lại.
        
        Args:
            index_name: Tên vector index
            node_label: Nhãn node
            embedding_property: Tên property embedding
            text_node_properties: Danh sách text properties để embedding
        """
        print("🔄 Bắt đầu recompute embeddings...")
        
        # Bước 1: Xóa vector index cũ (nếu embedding dimension khác)
        self.delete_vector_index(index_name)
        
        # Bước 2: Xóa embeddings cũ từ nodes
        self.delete_embeddings(node_label, embedding_property)
        
        # Bước 3: Tính lại embeddings mới
        self.insert_embeddings(
            index_name,
            node_label,
            embedding_property,
            text_node_properties
        )
        
        print("✅ Recompute embeddings hoàn tất!")
    
    def close(self):
        """Đóng connection Neo4j."""
        self.driver.close()


def main():
    """Main function."""
    parser = argparse.ArgumentParser(
        description="Quản lý embeddings cho Neo4j vector index"
    )
    
    # Commands
    subparsers = parser.add_subparsers(dest="command", help="Commands")
    
    # Delete command
    delete_parser = subparsers.add_parser("delete", help="Xóa tất cả embeddings")
    delete_parser.add_argument(
        "--node-label",
        default="Review",
        help="Node label (default: Review)"
    )
    delete_parser.add_argument(
        "--embedding-property",
        default="embedding",
        help="Embedding property name (default: embedding)"
    )
    
    # Insert command
    insert_parser = subparsers.add_parser("insert", help="Tính và insert embeddings mới")
    insert_parser.add_argument(
        "--index-name",
        default="reviews",
        help="Vector index name (default: reviews)"
    )
    insert_parser.add_argument(
        "--node-label",
        default="Review",
        help="Node label (default: Review)"
    )
    insert_parser.add_argument(
        "--embedding-property",
        default="embedding",
        help="Embedding property name (default: embedding)"
    )
    insert_parser.add_argument(
        "--text-properties",
        nargs="+",
        default=["physician_name", "patient_name", "text", "hospital_name"],
        help="Text properties to embed (default: physician_name patient_name text hospital_name)"
    )
    
    # Recompute command
    recompute_parser = subparsers.add_parser("recompute", help="Xóa và tính lại embeddings")
    recompute_parser.add_argument(
        "--index-name",
        default="reviews",
        help="Vector index name (default: reviews)"
    )
    recompute_parser.add_argument(
        "--node-label",
        default="Review",
        help="Node label (default: Review)"
    )
    recompute_parser.add_argument(
        "--embedding-property",
        default="embedding",
        help="Embedding property name (default: embedding)"
    )
    recompute_parser.add_argument(
        "--text-properties",
        nargs="+",
        default=["physician_name", "patient_name", "text", "hospital_name"],
        help="Text properties to embed (default: physician_name patient_name text hospital_name)"
    )
    
    # Drop-index command
    drop_parser = subparsers.add_parser("drop-index", help="Xóa vector index")
    drop_parser.add_argument(
        "--index-name",
        default="reviews",
        help="Vector index name (default: reviews)"
    )
    
    args = parser.parse_args()
    
    # Load environment variables
    load_dotenv("../.env.dev")
    
    # Initialize manager
    manager = EmbeddingManager(
        neo4j_uri=os.getenv("NEO4J_URI", "bolt://localhost:7687"),
        neo4j_user=os.getenv("NEO4J_USER", "neo4j"),
        neo4j_password=os.getenv("NEO4J_PASSWORD", "bot-neo4j"),
        embedding_model="openai",
    )
    
    try:
        if args.command == "delete":
            manager.delete_embeddings(
                node_label=args.node_label,
                embedding_property=args.embedding_property
            )
        
        elif args.command == "insert":
            manager.insert_embeddings(
                index_name=args.index_name,
                node_label=args.node_label,
                embedding_property=args.embedding_property,
                text_node_properties=args.text_properties
            )
        
        elif args.command == "recompute":
            manager.recompute_embeddings(
                index_name=args.index_name,
                node_label=args.node_label,
                embedding_property=args.embedding_property,
                text_node_properties=args.text_properties
            )
        
        elif args.command == "drop-index":
            manager.delete_vector_index(index_name=args.index_name)
        
        else:
            parser.print_help()
    
    except Exception as e:
        print(f"Script error: {str(e)}")
        sys.exit(1)
    
    finally:
        manager.close()


if __name__ == "__main__":
    main()
