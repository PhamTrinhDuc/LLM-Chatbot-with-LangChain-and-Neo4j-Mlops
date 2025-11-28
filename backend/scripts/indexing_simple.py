"""
Phiên bản đơn giản hóa của indexer.py
Dễ hiểu, dễ maintain, có thể mở rộng dần.
"""

import re
import uuid
from dataclasses import dataclass
from typing import Optional
from elasticsearch import Elasticsearch, helpers

# ═══════════════════════════════════════════════════════════════════════════════
# REGEX PATTERNS
# ═══════════════════════════════════════════════════════════════════════════════

# Tách documents: # Public_001
DOC_SPLIT_RE = re.compile(r"^#\s*(Public[_-]?\d{3,})[^\n]*$", flags=re.M)

# Parse headers: ## Chương I, ### Điều 1
HEADER_RE = re.compile(r"^(?P<hashes>#{1,6})\s+(?P<title>.+?)\s*$", flags=re.M)

# Detect tables
TABLE_RE = re.compile(r"<table\b[^>]*>.*?</table>", flags=re.S | re.I)

# Extract cells
CELL_RE = re.compile(r"<t[dh][^>]*>(.*?)</t[dh]>", flags=re.S | re.I)

# Formulas
FORMULA_RE = re.compile(r"\$\$.*?\$\$|\$[^$]+\$", flags=re.S)

# HTML tags
TAG_RE = re.compile(r"<[^>]+>")


# ═══════════════════════════════════════════════════════════════════════════════
# TẦNG 1: PARSING - Tách document và sections
# ═══════════════════════════════════════════════════════════════════════════════

def split_documents(md_text: str) -> dict[str, str]:
    """
    Tách markdown thành nhiều documents.
    
    Input:  "# Public_001\ncontent1\n# Public_002\ncontent2"
    Output: {"Public_001": "content1", "Public_002": "content2"}
    """
    parts = re.split(DOC_SPLIT_RE, md_text)
    docs = {}
    for i in range(1, len(parts), 2):
        doc_name = parts[i].strip()
        content = parts[i + 1].strip() if i + 1 < len(parts) else ""
        docs[doc_name] = content
    return docs


@dataclass
class Section:
    """Một section trong document (ứng với 1 header)."""
    level: int              # 1-6 (## = 2, ### = 3)
    title: str              # "Điều 1: Phạm vi"
    path: list[str]         # ["Chương I", "Điều 1"] - breadcrumb
    own_text: str           # Nội dung riêng (không bao gồm children)


def parse_sections(doc_text: str) -> list[Section]:
    """
    Parse document thành danh sách sections với breadcrumb.
    
    Input:
        ## Chương I
        Nội dung chương
        ### Điều 1
        Nội dung điều 1
        
    Output:
        [
            Section(level=2, title="Chương I", path=["Chương I"], own_text="Nội dung chương"),
            Section(level=3, title="Điều 1", path=["Chương I", "Điều 1"], own_text="Nội dung điều 1"),
        ]
    """
    # Tìm tất cả headers
    headers = []
    for m in HEADER_RE.finditer(doc_text):
        headers.append({
            "level": len(m.group("hashes")),
            "title": m.group("title").strip(),
            "start": m.start(),
            "body_start": m.end(),
        })
    
    if not headers:
        # Không có header -> toàn bộ là 1 section
        return [Section(level=1, title="", path=[""], own_text=doc_text.strip())]
    
    # Tính body_end cho mỗi header (đến header cùng/cao hơn level)
    for i, h in enumerate(headers):
        h["body_end"] = len(doc_text)
        for j in range(i + 1, len(headers)):
            if headers[j]["level"] <= h["level"]:
                h["body_end"] = headers[j]["start"]
                break
    
    # Build sections với path (breadcrumb)
    sections = []
    stack = []  # [(level, title), ...]
    
    for i, h in enumerate(headers):
        # Pop stack cho đến khi tìm được parent
        while stack and stack[-1][0] >= h["level"]:
            stack.pop()
        
        # Build path
        path = [t for _, t in stack] + [h["title"]]
        
        # Tính own_text (không bao gồm children)
        own_end = h["body_end"]
        for j in range(i + 1, len(headers)):
            if headers[j]["level"] > h["level"]:
                own_end = min(own_end, headers[j]["start"])
                break
        
        own_text = doc_text[h["body_start"]:own_end].strip()
        
        sections.append(Section(
            level=h["level"],
            title=h["title"],
            path=path,
            own_text=own_text,
        ))
        
        stack.append((h["level"], h["title"]))
    
    return sections


# ═══════════════════════════════════════════════════════════════════════════════
# TẦNG 2: CHUNKING - Chia nhỏ theo câu/table
# ═══════════════════════════════════════════════════════════════════════════════

def split_sentences(text: str) -> list[str]:
    """Tách text thành các câu."""
    sents = re.split(r'(?<=[.!?])\s+', text.strip())
    return [s.strip() for s in sents if s.strip()]


def count_words(text: str) -> int:
    """Đếm số từ trong text."""
    return len(text.split())


def chunk_text_simple(text: str, chunk_size: int = 300, overlap: int = 30) -> list[str]:
    """
    Chunking đơn giản theo câu.
    
    - Gom câu cho đến khi đạt chunk_size
    - Overlap: lấy vài từ cuối chunk trước làm đầu chunk sau
    """
    sentences = split_sentences(text)
    if not sentences:
        return []
    
    chunks = []
    current_chunk = []
    current_words = 0
    
    for sent in sentences:
        sent_words = count_words(sent)
        
        if current_words + sent_words <= chunk_size:
            current_chunk.append(sent)
            current_words += sent_words
        else:
            # Flush current chunk
            if current_chunk:
                chunks.append(" ".join(current_chunk))
            
            # Start new chunk với overlap
            if overlap > 0 and current_chunk:
                # Lấy vài từ cuối làm overlap
                overlap_text = " ".join(current_chunk)[-overlap * 6:]  # ~6 chars/word
                current_chunk = [overlap_text, sent]
                current_words = count_words(overlap_text) + sent_words
            else:
                current_chunk = [sent]
                current_words = sent_words
    
    # Flush remaining
    if current_chunk:
        chunks.append(" ".join(current_chunk))
    
    return chunks


def chunk_with_tables(text: str, chunk_size: int = 300) -> list[str]:
    """
    Chunking có xử lý table.
    
    - Text thường: chunk theo câu
    - Table: giữ nguyên hoặc tách theo hàng nếu quá lớn
    """
    chunks = []
    last_end = 0
    
    for m in TABLE_RE.finditer(text):
        # Chunk phần text trước table
        text_before = text[last_end:m.start()].strip()
        if text_before:
            chunks.extend(chunk_text_simple(text_before, chunk_size))
        
        # Xử lý table
        table_html = m.group(0)
        table_words = count_words(extract_table_text(table_html))
        
        if table_words <= chunk_size:
            # Table nhỏ -> giữ nguyên
            chunks.append(table_html)
        else:
            # Table lớn -> tách theo hàng (đơn giản)
            chunks.append(table_html)  # Hoặc implement tách hàng
        
        last_end = m.end()
    
    # Chunk phần text còn lại
    text_after = text[last_end:].strip()
    if text_after:
        chunks.extend(chunk_text_simple(text_after, chunk_size))
    
    return chunks


# ═══════════════════════════════════════════════════════════════════════════════
# TẦNG 3: TEXT PROCESSING - Làm sạch cho BM25
# ═══════════════════════════════════════════════════════════════════════════════

def remove_formulas(text: str) -> str:
    """Bỏ công thức toán học."""
    return FORMULA_RE.sub("", text)


def extract_table_text(table_html: str) -> str:
    """
    Lấy text từ table, bỏ các cell ngắn/toàn số.
    """
    cells = []
    for m in CELL_RE.finditer(table_html):
        cell_html = m.group(1)
        # Bỏ tags, formulas
        cell_text = TAG_RE.sub(" ", cell_html)
        cell_text = remove_formulas(cell_text)
        cell_text = re.sub(r"\s+", " ", cell_text).strip()
        
        if not cell_text:
            continue
        
        words = cell_text.split()
        
        # Bỏ cell toàn số
        if all(re.match(r"^[\d.,%-]+$", w) for w in words):
            continue
        
        # Bỏ cell quá ngắn (≤ 3 từ)
        if len(words) <= 3:
            continue
        
        cells.append(cell_text)
    
    return " ".join(cells)


def clean_for_bm25(text: str) -> str:
    """
    Làm sạch text để index vào BM25.
    
    - Bỏ formulas
    - Với table: chỉ giữ text có nghĩa
    - Bỏ dấu câu thừa
    """
    # Xử lý tables
    result = []
    last_end = 0
    
    for m in TABLE_RE.finditer(text):
        # Text trước table
        text_before = text[last_end:m.start()]
        result.append(remove_formulas(text_before))
        
        # Table -> extract text
        result.append(extract_table_text(m.group(0)))
        last_end = m.end()
    
    # Text sau table cuối
    result.append(remove_formulas(text[last_end:]))
    
    # Join và clean
    cleaned = " ".join(result)
    cleaned = re.sub(r"[^\w\s]", " ", cleaned)  # Bỏ dấu câu
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    
    return cleaned


def segment_vietnamese(text: str) -> str:
    """
    Word segmentation cho tiếng Việt.
    Placeholder - thay bằng VnCoreNLP hoặc underthesea.
    """
    # TODO: Integrate với VnCoreNLP
    # from ai_race.utils.word_segmentation import segment_text
    # return segment_text(text)
    return text.lower()


# ═══════════════════════════════════════════════════════════════════════════════
# MAIN: Kết hợp tất cả
# ═══════════════════════════════════════════════════════════════════════════════

def process_markdown(md_text: str, chunk_size: int = 300) -> list[dict]:
    """
    Pipeline hoàn chỉnh: Markdown → Chunks với metadata.
    """
    documents = split_documents(md_text)
    all_chunks = []
    global_order = 0
    
    for doc_name, content in documents.items():
        sections = parse_sections(content)
        
        for section in sections:
            if not section.own_text.strip():
                continue
            
            # Chunking
            text_chunks = chunk_with_tables(section.own_text, chunk_size)
            
            # Build header path
            header_path = " > ".join(section.path)
            
            for i, chunk_text in enumerate(text_chunks, start=1):
                global_order += 1
                
                # Clean for BM25
                content_bm25 = clean_for_bm25(chunk_text)
                content_segmented = segment_vietnamese(content_bm25)
                
                all_chunks.append({
                    "doc_name": doc_name,
                    "section_id": str(uuid.uuid4()),
                    "section_level": section.level,
                    "chunk_id": i,
                    "global_order": global_order,
                    "header_path_raw": header_path,
                    "content_raw": chunk_text,
                    "content": content_segmented,  # Đã clean + segment
                })
    
    return all_chunks


def index_to_elasticsearch(chunks: list[dict], es: Elasticsearch, index_name: str):
    """Index chunks vào Elasticsearch."""
    actions = [
        {
            "_index": index_name,
            "_id": str(uuid.uuid4()),
            "_source": chunk,
        }
        for chunk in chunks
    ]
    
    helpers.bulk(es, actions)
    es.indices.refresh(index=index_name)
    print(f"Indexed {len(actions)} chunks to {index_name}")


# ═══════════════════════════════════════════════════════════════════════════════
# USAGE EXAMPLE
# ═══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    # Test với sample markdown
    sample_md = """
# Public_001

## Chương I: Quy định chung

### Điều 1: Phạm vi điều chỉnh

Văn bản này quy định về điều kiện hưởng bảo hiểm xã hội. 
Người lao động phải đóng đủ 12 tháng.

### Điều 2: Đối tượng áp dụng

<table>
<tr><td>STT</td><td>Đối tượng</td><td>Mức đóng</td></tr>
<tr><td>1</td><td>Người lao động có hợp đồng lao động</td><td>8%</td></tr>
<tr><td>2</td><td>Cán bộ công chức viên chức nhà nước</td><td>8%</td></tr>
</table>

# Public_002

## Chương I: Tổng quan

Nội dung tổng quan về văn bản.
"""
    
    chunks = process_markdown(sample_md)
    
    for c in chunks:
        print(f"\n{'='*60}")
        print(f"Doc: {c['doc_name']}")
        print(f"Path: {c['header_path_raw']}")
        print(f"Content: {c['content'][:100]}...")