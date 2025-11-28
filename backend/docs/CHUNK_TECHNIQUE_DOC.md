# 📚 DSM-5 Chunking Techniques Documentation

> Tài liệu mô tả chi tiết các kỹ thuật và luồng xử lý logic cho việc chunking tài liệu DSM-5 để index vào Elasticsearch.

---

## 📋 Mục lục

1. [Tổng quan vấn đề](#1-tổng-quan-vấn-đề)
2. [Kiến trúc giải pháp](#2-kiến-trúc-giải-pháp)
3. [Các kỹ thuật chunking](#3-các-kỹ-thuật-chunking)
4. [Luồng xử lý chi tiết](#4-luồng-xử-lý-chi-tiết)
5. [Data Schema](#5-data-schema)
6. [Elasticsearch Integration](#6-elasticsearch-integration)
7. [Best Practices](#7-best-practices)

---

## 1. Tổng quan vấn đề

### 1.1. Vấn đề gặp phải

Khi chunking tài liệu DSM-5 (PDF), ta thường gặp các vấn đề:

| Vấn đề | Mô tả |
|--------|-------|
| **Chunk không đồng đều** | Chunk quá ngắn (chỉ tiêu đề) hoặc quá dài (toàn bộ section) |
| **Mất ngữ cảnh** | Chunk không biết thuộc rối loạn nào, tiêu chí nào |
| **Search kém hiệu quả** | Không có metadata để filter/boost |
| **Không phù hợp LLM** | Chunk quá lớn vượt context window |

### 1.2. Cấu trúc tài liệu DSM-5

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                        CẤU TRÚC DSM-5                                       │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  Rối loạn phổ tự kỷ (F84.0)              ← DISORDER HEADER                 │
│  ├── A. Khiếm khuyết kéo dài...          ← MAIN CRITERIA (A, B, C...)      │
│  │   ├── 1. Khiếm khuyết có đi có lại... ← SUB CRITERIA (1, 2, 3...)       │
│  │   ├── 2. Khiếm khuyết trong hành vi...                                  │
│  │   └── 3. Khiếm khuyết trong việc...                                     │
│  ├── B. Các kiểu hành vi...                                                │
│  ├── C. Các triệu chứng phải xuất hiện...                                  │
│  ├── D. Các triệu chứng gây ra...                                          │
│  ├── E. Không giải thích tốt hơn bởi...                                    │
│  ├── Đặc điểm chẩn đoán                  ← DESCRIPTIVE SECTION             │
│  ├── Các đặc điểm hỗ trợ chẩn đoán                                         │
│  ├── Tỉ lệ mắc                                                             │
│  ├── Sự phát triển và diễn tiến                                            │
│  ├── Yếu tố nguy cơ                                                        │
│  ├── Chẩn đoán phân biệt                                                   │
│  └── Bệnh đi kèm                                                           │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 2. Kiến trúc giải pháp

### 2.1. Tổng quan Pipeline

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              INPUT                                          │
│                         DSM-5 PDF File                                      │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                     BƯỚC 1: TEXT EXTRACTION                                 │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │  PyMuPDF (fitz)                                                     │   │
│  │  - Extract text với page positions                                  │   │
│  │  - Giữ thông tin layout (blocks)                                    │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                     BƯỚC 2: DISORDER IDENTIFICATION                         │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │  Regex Pattern Matching                                             │   │
│  │  - Nhận diện tên rối loạn + mã ICD                                  │   │
│  │  - Xác định phạm vi (start_pos, end_pos)                            │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                     BƯỚC 3: SEMANTIC CHUNKING                               │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │  Hierarchical Chunking Strategy                                     │   │
│  │  - Chunk theo tiêu chí chẩn đoán (A, B, C...)                       │   │
│  │  - Split tiêu chí dài theo mục con (1, 2, 3...)                     │   │
│  │  - Chunk sections mô tả theo paragraph                              │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                     BƯỚC 4: SIZE BALANCING                                  │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │  Merge & Split Logic                                                │   │
│  │  - Merge chunks < min_size với chunk lân cận                        │   │
│  │  - Split chunks > max_size theo sentence                            │   │
│  │  - Target size: ~800 ký tự                                          │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                     BƯỚC 5: CONTEXT ENRICHMENT                              │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │  Add Metadata & Context Header                                      │   │
│  │  - Thêm context header: [Rối loạn (Mã) - Tiêu chí]                  │   │
│  │  - Extract keywords                                                 │   │
│  │  - Build section_path (breadcrumb)                                  │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                              OUTPUT                                         │
│                    List[DSMChunk] → JSON/Elasticsearch                      │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 2.2. Chunk Types

| Type | Description | Example |
|------|-------------|---------|
| `disorder_header` | Tên rối loạn + mã ICD | "Rối loạn phổ tự kỷ (F84.0)" |
| `diagnostic_criteria` | Tiêu chí chẩn đoán chính | "A. Khiếm khuyết kéo dài..." |
| `criteria_item` | Mục con của tiêu chí | "1. Khiếm khuyết có đi có lại..." |
| `descriptive_section` | Section mô tả | "Đặc điểm chẩn đoán: ..." |
| `specification` | Biệt định mức độ | "Mức độ 1: Cần hỗ trợ" |

---

## 3. Các kỹ thuật chunking

### 3.1. Semantic Chunking (Chunking theo ngữ nghĩa)

**Nguyên tắc**: Chunk theo cấu trúc logic của tài liệu, không phải theo độ dài cố định.

```python
# ❌ BAD: Fixed-size chunking
chunks = text_splitter.split_text(text, chunk_size=500)

# ✅ GOOD: Semantic chunking
for criteria_match in MAIN_CRITERIA_PATTERN.finditer(text):
    criteria_content = criteria_match.group()
    if len(criteria_content) <= max_size:
        chunks.append(criteria_content)  # Giữ nguyên
    else:
        chunks.extend(split_by_sub_criteria(criteria_content))  # Split theo cấu trúc
```

### 3.2. Hierarchical Context (Ngữ cảnh phân cấp)

**Nguyên tắc**: Mỗi chunk phải biết "mình thuộc về đâu".

```
Chunk content:
┌─────────────────────────────────────────────────────────────────────────────┐
│ [Rối loạn phổ tự kỷ (F84.0) - Tiêu chí A]          ← CONTEXT HEADER        │
│                                                                             │
│ 1. Khiếm khuyết có đi có lại về mặt cảm xúc-xã hội, từ cách tiếp cận xã    │
│ hội bất thường và thất bại trong giao tiếp có đi có lại thông thường...    │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘

section_path = ["Rối loạn phổ tự kỷ", "Tiêu chí A", "Mục 1"]
```

### 3.3. Size Balancing (Cân bằng kích thước)

**Tham số cấu hình**:

```python
min_chunk_size = 200   # Merge nếu < 200 ký tự
max_chunk_size = 1500  # Split nếu > 1500 ký tự
target_chunk_size = 800  # Mục tiêu ~800 ký tự
```

**Logic xử lý**:

```
                    ┌──────────────┐
                    │  Chunk Size  │
                    └──────┬───────┘
                           │
            ┌──────────────┼──────────────┐
            │              │              │
            ▼              ▼              ▼
    ┌───────────┐  ┌───────────┐  ┌───────────┐
    │  < 200    │  │ 200-1500  │  │  > 1500   │
    │  (Quá    │  │  (Phù    │  │  (Quá    │
    │   ngắn)   │  │   hợp)    │  │   dài)   │
    └─────┬─────┘  └─────┬─────┘  └─────┬─────┘
          │              │              │
          ▼              ▼              ▼
    ┌───────────┐  ┌───────────┐  ┌───────────┐
    │  MERGE    │  │   KEEP    │  │  SPLIT    │
    │ với chunk │  │  nguyên   │  │ theo cấu  │
    │  lân cận  │  │           │  │   trúc    │
    └───────────┘  └───────────┘  └───────────┘
```

### 3.4. Overlap Strategy (Chiến lược chồng lấp)

**Nguyên tắc**: Context overlap chỉ áp dụng cho phần text thường, không áp dụng cho tiêu đề/bảng.

```python
# Khi split dài, giữ context header ở mỗi chunk
context_header = f"[{disorder_name} ({disorder_code}) - Tiêu chí {criteria_letter}]\n"

# Mỗi chunk con đều có header này
chunk_1 = context_header + "1. Nội dung mục 1..."
chunk_2 = context_header + "2. Nội dung mục 2..."
```

### 3.5. Keyword Extraction (Trích xuất từ khóa)

**Mục đích**: Hỗ trợ search và filter trong Elasticsearch.

```python
# Từ khóa y học DSM-5
medical_terms = [
    'rối loạn', 'hội chứng', 'triệu chứng', 'chẩn đoán', 'tiêu chí',
    'khiếm khuyết', 'suy giảm', 'phát triển', 'hành vi', 'nhận thức',
    'cảm xúc', 'lo âu', 'trầm cảm', 'tâm thần', 'phân liệt',
    'ám ảnh', 'cưỡng chế', 'hoảng loạn', 'ám sợ', 'chấn thương',
    'tự kỷ', 'tăng động', 'giảm chú ý'
]

# Mức độ nặng nhẹ
severity_patterns = ['Mức độ 1', 'Mức độ 2', 'Mức độ 3', 'Nhẹ', 'Trung bình', 'Nặng']
```

---

## 4. Luồng xử lý chi tiết

### 4.1. Bước 1: Text Extraction

```python
def extract_text_with_positions(pdf_path: str) -> List[Dict]:
    """
    Trích xuất text với thông tin vị trí trang.
    
    Output:
    [
        {'page': 1, 'text': '...', 'blocks': [...]},
        {'page': 2, 'text': '...', 'blocks': [...]},
        ...
    ]
    """
    doc = fitz.open(pdf_path)
    pages_content = []
    
    for page_num, page in enumerate(doc, 1):
        pages_content.append({
            'page': page_num,
            'text': page.get_text("text"),
            'blocks': page.get_text("blocks")
        })
    
    return pages_content
```

### 4.2. Bước 2: Disorder Identification

```python
# Pattern nhận diện rối loạn
DISORDER_HEADER_PATTERN = re.compile(
    r'^([A-ZÀÁẢÃẠ...][^()]+)\s*\(([A-Z]\d+\.?\d*)\)',
    re.MULTILINE
)

# Ví dụ matches:
# "Rối loạn phổ tự kỷ (F84.0)" → name="Rối loạn phổ tự kỷ", code="F84.0"
# "Rối loạn tăng động/giảm chú ý (F90.x)" → name="...", code="F90.x"
```

### 4.3. Bước 3: Chunking Tiêu chí chẩn đoán

```
Input: "A. Khiếm khuyết kéo dài trong giao tiếp...
        1. Khiếm khuyết có đi có lại...
        2. Khiếm khuyết trong hành vi..."
           │
           ▼
    ┌──────────────────┐
    │ Đủ nhỏ (<1500)?  │
    └────────┬─────────┘
             │
      ┌──────┴──────┐
      │             │
     YES           NO
      │             │
      ▼             ▼
┌──────────┐  ┌──────────────────────────┐
│ Giữ      │  │ Tìm sub-criteria (1,2,3) │
│ nguyên   │  └─────────────┬────────────┘
└──────────┘                │
                   ┌────────┴────────┐
                   │                 │
                  YES               NO
                   │                 │
                   ▼                 ▼
            ┌──────────┐      ┌──────────┐
            │ Split    │      │ Split    │
            │ theo     │      │ theo     │
            │ mục con  │      │ sentence │
            └──────────┘      └──────────┘
```

### 4.4. Bước 4: Chunking Sections mô tả

```python
def chunk_descriptive_section(section_name, content, disorder_info):
    """
    Chunk các section như "Đặc điểm chẩn đoán", "Chẩn đoán phân biệt"...
    
    Chiến lược:
    1. Split theo paragraph (double newline)
    2. Gom paragraphs cho đến khi đạt target_size
    3. Đảm bảo mỗi chunk >= min_size
    """
    paragraphs = content.split('\n\n')
    
    chunks = []
    current_chunk = ""
    
    for para in paragraphs:
        if len(current_chunk + para) <= max_chunk_size:
            current_chunk += "\n\n" + para
        else:
            if len(current_chunk) >= min_chunk_size:
                chunks.append(current_chunk)
            current_chunk = para
    
    return chunks
```

### 4.5. Bước 5: Merge Small Chunks

```python
def merge_small_chunks(chunks: List[DSMChunk]) -> List[DSMChunk]:
    """
    Merge các chunk quá nhỏ với chunk lân cận.
    
    Điều kiện merge:
    1. Chunk < min_chunk_size (200)
    2. Cùng disorder_code
    3. Cùng chunk_type
    4. Merged size <= max_chunk_size
    """
    merged = []
    i = 0
    
    while i < len(chunks):
        current = chunks[i]
        
        if current.char_count < min_chunk_size and i + 1 < len(chunks):
            next_chunk = chunks[i + 1]
            
            if (current.disorder_code == next_chunk.disorder_code and 
                current.chunk_type == next_chunk.chunk_type):
                
                merged_content = current.content + "\n\n" + next_chunk.content
                
                if len(merged_content) <= max_chunk_size:
                    merged.append(create_merged_chunk(current, next_chunk))
                    i += 2
                    continue
        
        merged.append(current)
        i += 1
    
    return merged
```

---

## 5. Data Schema

### 5.1. DSMChunk Dataclass

```python
@dataclass
class DSMChunk:
    chunk_id: str              # Unique ID: "F84.0_A_1"
    chunk_type: str            # "diagnostic_criteria", "descriptive_section", etc.
    disorder_name: str         # "Rối loạn phổ tự kỷ"
    disorder_code: str         # "F84.0"
    section_path: List[str]    # ["Rối loạn phổ tự kỷ", "Tiêu chí A", "Mục 1"]
    content: str               # Nội dung chunk (có context header)
    page_number: int           # Trang trong PDF
    char_count: int            # Số ký tự
    parent_chunk_id: str       # ID chunk cha (nếu có)
    keywords: List[str]        # ["rối loạn", "khiếm khuyết", "tự kỷ"]
    severity_level: str        # "Mức độ 1", "Nhẹ", etc.
```

### 5.2. Output JSON Example

```json
{
  "chunk_id": "F84.0_A_1",
  "chunk_type": "criteria_item",
  "disorder_name": "Rối loạn phổ tự kỷ",
  "disorder_code": "F84.0",
  "section_path": ["Rối loạn phổ tự kỷ", "Tiêu chí A", "Phần 1"],
  "content": "[Rối loạn phổ tự kỷ (F84.0) - Tiêu chí A]\n1. Khiếm khuyết có đi có lại về mặt cảm xúc-xã hội, từ cách tiếp cận xã hội bất thường và thất bại trong giao tiếp có đi có lại thông thường, đến giảm chia sẻ sở thích, cảm xúc, hoặc tình cảm, đến thất bại trong việc bắt đầu hoặc phản ứng với các tương tác xã hội.",
  "page_number": 50,
  "char_count": 456,
  "keywords": ["rối loạn", "khiếm khuyết", "tự kỷ", "cảm xúc", "xã hội"],
  "parent_chunk_id": "F84.0_A",
  "severity_level": null
}
```

---

## 6. Elasticsearch Integration

### 6.1. Index Mapping

```json
{
  "mappings": {
    "properties": {
      "chunk_id": { "type": "keyword" },
      "chunk_type": { "type": "keyword" },
      "disorder_name": {
        "type": "text",
        "analyzer": "vietnamese",
        "fields": {
          "keyword": { "type": "keyword" }
        }
      },
      "disorder_code": { "type": "keyword" },
      "section_path": { "type": "keyword" },
      "section_path_text": {
        "type": "text",
        "analyzer": "vietnamese"
      },
      "content": {
        "type": "text",
        "analyzer": "vietnamese"
      },
      "page_number": { "type": "integer" },
      "char_count": { "type": "integer" },
      "keywords": { "type": "keyword" },
      "content_vector": {
        "type": "dense_vector",
        "dims": 768,
        "index": true,
        "similarity": "cosine"
      }
    }
  },
  "settings": {
    "analysis": {
      "analyzer": {
        "vietnamese": {
          "type": "custom",
          "tokenizer": "standard",
          "filter": ["lowercase", "asciifolding"]
        }
      }
    }
  }
}
```

### 6.2. Search Query Example

```python
def search_dsm5(query: str, filters: dict = None):
    """
    Hybrid search: BM25 + Vector similarity
    """
    body = {
        "query": {
            "bool": {
                "must": [
                    {
                        "multi_match": {
                            "query": query,
                            "fields": [
                                "content^2",      # Boost content
                                "disorder_name^3", # Boost disorder name
                                "keywords^1.5"
                            ],
                            "type": "best_fields"
                        }
                    }
                ],
                "filter": [
                    {"term": {"disorder_code": filters.get("disorder_code")}},
                    {"term": {"chunk_type": filters.get("chunk_type")}}
                ]
            }
        },
        "highlight": {
            "fields": {
                "content": {"fragment_size": 200}
            }
        }
    }
    
    return es_client.search(index="dsm5", body=body)
```

---

## 7. Best Practices

### 7.1. Khi nào sử dụng kỹ thuật nào?

| Tình huống | Kỹ thuật khuyên dùng |
|------------|---------------------|
| Tài liệu có cấu trúc rõ ràng (DSM-5, luật) | Semantic chunking theo cấu trúc |
| Tài liệu tự do, không cấu trúc | Fixed-size chunking với overlap |
| Cần search chính xác | Thêm context header + keywords |
| Cần filter theo loại | Đánh chunk_type metadata |
| Chunk quá dài/ngắn | Size balancing (merge/split) |

### 7.2. Tham số khuyến nghị

```python
# Cho tài liệu y tế (DSM-5)
min_chunk_size = 200    # Đủ để có nghĩa
max_chunk_size = 1500   # Không quá dài cho LLM
target_chunk_size = 800 # Cân bằng

# Cho tài liệu pháp lý
min_chunk_size = 300
max_chunk_size = 2000
target_chunk_size = 1000

# Cho tài liệu ngắn (FAQ, etc.)
min_chunk_size = 100
max_chunk_size = 500
target_chunk_size = 300
```

### 7.3. Checklist trước khi index

- [ ] Mỗi chunk có context header
- [ ] Chunk size trong khoảng [min, max]
- [ ] Không có chunk trùng lặp
- [ ] Keywords đã được extract
- [ ] section_path đúng format
- [ ] disorder_code hợp lệ (F84.0, F90.x, etc.)

### 7.4. Monitoring và Debug

```python
def print_statistics(chunks: List[DSMChunk]):
    """In thống kê để debug"""
    sizes = [c.char_count for c in chunks]
    
    print(f"Tổng số chunks: {len(chunks)}")
    print(f"Kích thước TB: {sum(sizes)/len(sizes):.0f}")
    print(f"Min: {min(sizes)}, Max: {max(sizes)}")
    
    # Phân bố theo loại
    type_counts = Counter(c.chunk_type for c in chunks)
    for t, count in type_counts.items():
        print(f"  {t}: {count}")
```

---

## 📚 References

- [PyMuPDF Documentation](https://pymupdf.readthedocs.io/)
- [Elasticsearch Text Analysis](https://www.elastic.co/guide/en/elasticsearch/reference/current/analysis.html)
- [LangChain Text Splitters](https://python.langchain.com/docs/modules/data_connection/document_transformers/)
- [Chunking Strategies for RAG](https://www.pinecone.io/learn/chunking-strategies/)

---

*Document version: 1.0*  
*Last updated: 2025-11-29*
