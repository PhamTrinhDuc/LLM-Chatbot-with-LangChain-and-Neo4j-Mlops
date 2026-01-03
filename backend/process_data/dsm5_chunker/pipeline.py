import os
import re
from typing import Any, Dict, List

import pdfplumber

# ============================================================
# CONFIGURATION
# ============================================================
MIN_CHUNK_SIZE = 200  # Chunk nhỏ hơn sẽ được merge
MAX_CHUNK_SIZE = 1500  # Chunk lớn hơn sẽ được split
TARGET_CHUNK_SIZE = 800  # Kích thước mục tiêu

# ============================================================
# PATTERNS
# ============================================================
# Pattern cho section header: "1.2.3 Tên section"
SECTION_PATTERN = re.compile(r"^(\d+(?:\.\d+)*)\s+([A-ZÀ-Ỹa-zà-ỹ].*)")

# Pattern cho tiêu chí chẩn đoán: "A.", "B.", "C."
CRITERIA_PATTERN = re.compile(r"^([A-Z])\.\s+(.+)", re.DOTALL)

# Pattern cho mục con: "1.", "2.", "3." hoặc "a.", "b.", "c."
SUB_CRITERIA_PATTERN = re.compile(r"^(\d+|[a-z])\.\s+(.+)", re.DOTALL)

# Pattern cho phần "Chẩn đoán phân biệt"
DIFF_DIAG_PATTERN = re.compile(
    r"(Chẩn đoán phân biệt|chẩn đoán phân biệt)[:\s]*", re.IGNORECASE
)

# Pattern cho số trang footer (ví dụ: "12 Chỉ sử dụng tài liệu...")
PAGE_FOOTER_PATTERN = re.compile(r"^\d+\s+[Cc]hỉ sử dụng tài liệu.*$")


def smart_join_lines(lines: list[str]) -> str:
    """
    Ghép các dòng PDF thành các đoạn logic:
    - Không ghép nếu dòng trước kết thúc bằng dấu câu (. ! ? : ) …
    - Không ghép nếu dòng sau bắt đầu bằng tiêu chí (A., 1., v.v.)
    - Bỏ qua footer trang
    """
    if not lines:
        return ""

    # Lọc bỏ footer trang
    filtered_lines = [
        line for line in lines if not PAGE_FOOTER_PATTERN.match(line.strip())
    ]
    if not filtered_lines:
        return ""

    paragraphs = []
    current_para = filtered_lines[0]

    for i in range(1, len(filtered_lines)):
        prev_line = current_para.strip()
        curr_line = filtered_lines[i].strip()

        # Nếu dòng trước kết thúc bằng dấu kết thúc => ngắt đoạn
        if re.search(r"[.!?…:)]$", prev_line):
            paragraphs.append(current_para)
            current_para = curr_line

        # Nếu dòng sau bắt đầu bằng tiêu chí => ngắt (A., B., 1., 2., v.v.)
        elif re.match(r"^[A-Z]\.\s", curr_line) or re.match(r"^\d+\.\s", curr_line):
            paragraphs.append(current_para)
            current_para = curr_line

        else:
            current_para += " " + curr_line

    paragraphs.append(current_para)
    return "\n".join(paragraphs)


def add_parent_title(chunks: list[dict]) -> list[dict]:
    """
    Thêm parent_title cho mỗi chunk dựa trên parent_id.

    FIX: Sử dụng unique_id thay vì section_id vì PDF có thể có
    nhiều section cùng ID ở các phần khác nhau.
    """
    # Build map từ unique_id -> chunk
    # unique_id được gán trong extract function
    chunk_map = {}
    for c in chunks:
        uid = c.get("unique_id")
        if uid:
            chunk_map[uid] = c

    for chunk in chunks:
        parent_uid = chunk.get("parent_unique_id")
        if parent_uid and parent_uid in chunk_map:
            parent_chunk = chunk_map[parent_uid]
            chunk["parent_title"] = parent_chunk.get("title", "")
        else:
            chunk["parent_title"] = None

    return chunks


def clean_text(text: str) -> str:
    """
    Clean and normalize text.
    """
    if not text or not isinstance(text, str):
        return ""

    # Remove extra whitespace
    text = re.sub(r"\s+", " ", text)
    # Remove special characters but keep Vietnamese
    text = re.sub(r"[^\w\s\u00C0-\u1EF9.,;:!?()/-]", "", text)
    return text.strip()


def build_context_header(chunk: dict, chunk_map: dict) -> str:
    """
    Xây dựng context header cho chunk.
    Ví dụ: "[1 Rối loạn phát triển thần kinh > 1.3 Rối loạn phổ tự kỷ]"

    FIX: Sử dụng unique_id thay vì section_id
    """
    path_parts = []
    current = chunk

    # Traverse up the hierarchy
    visited = set()
    while current:
        unique_id = current.get("unique_id")
        if unique_id in visited:
            break
        visited.add(unique_id)

        title = current.get("title", "")
        if title:
            # Lấy phần tiêu đề ngắn gọn (bỏ phần chi tiết sau dấu :)
            short_title = title.split(":")[0].strip()[:60]
            path_parts.insert(0, short_title)

        parent_uid = current.get("parent_unique_id")
        if parent_uid and parent_uid in chunk_map:
            current = chunk_map[parent_uid]
        else:
            break

    if path_parts:
        return "[" + " > ".join(path_parts) + "]"
    return ""


def split_long_content(text: str) -> List[Dict[str, Any]]:
    """
    Split nội dung dài thành các chunks nhỏ hơn.

    Chiến lược:
    1. Ưu tiên split theo tiêu chí chẩn đoán (A., B., C., ...)
    2. Nếu vẫn còn dài, split theo mục con (1., 2., 3., ...)
    3. Cuối cùng, split theo câu
    """
    sub_chunks = []

    # Thử split theo tiêu chí chính (A., B., C., ...)
    criteria_parts = re.split(r"(?=\n[A-Z]\.\s)", text)
    if len(criteria_parts) > 1:
        # Có nhiều tiêu chí, split theo từng tiêu chí
        for i, part in enumerate(criteria_parts):
            part = part.strip()
            if not part:
                continue

            # Tìm label của tiêu chí
            match = re.match(r"^([A-Z])\.\s", part)
            if match:
                criteria_label = match.group(1)
                sub_id = f"criteria_{criteria_label}"
                sub_title = f"Tiêu chí {criteria_label}"
            else:
                sub_id = "intro"
                sub_title = "Giới thiệu"

            # Nếu phần này vẫn còn quá dài, split tiếp theo câu
            if len(part) > MAX_CHUNK_SIZE:
                sentence_chunks = split_by_sentences(part, MAX_CHUNK_SIZE)
                for j, sent_chunk in enumerate(sentence_chunks):
                    sub_chunks.append(
                        {
                            "content": sent_chunk,
                            "sub_id": f"{sub_id}_p{j + 1}",
                            "sub_title": f"{sub_title} (phần {j + 1})",
                        }
                    )
            else:
                sub_chunks.append(
                    {"content": part, "sub_id": sub_id, "sub_title": sub_title}
                )
    else:
        # Không có tiêu chí A/B/C, thử split theo mục con (1., 2., ...)
        sub_parts = re.split(r"(?=\n\d+\.\s)", text)

        if len(sub_parts) > 1 and all(len(p) < MAX_CHUNK_SIZE for p in sub_parts):
            for i, part in enumerate(sub_parts):
                part = part.strip()
                if not part:
                    continue

                match = re.match(r"^(\d+)\.\s", part)
                if match:
                    item_num = match.group(1)
                    sub_id = f"item_{item_num}"
                    sub_title = f"Mục {item_num}"
                else:
                    sub_id = "intro"
                    sub_title = "Giới thiệu"

                sub_chunks.append(
                    {"content": part, "sub_id": sub_id, "sub_title": sub_title}
                )
        else:
            # Fallback: split theo câu
            sentence_chunks = split_by_sentences(text, MAX_CHUNK_SIZE)
            for j, sent_chunk in enumerate(sentence_chunks):
                sub_chunks.append(
                    {
                        "content": sent_chunk,
                        "sub_id": f"part_{j + 1}",
                        "sub_title": f"Phần {j + 1}",
                    }
                )

    return (
        sub_chunks
        if sub_chunks
        else [{"content": text, "sub_id": None, "sub_title": None}]
    )


def split_by_sentences(text: str, max_size: int) -> List[str]:
    """
    Split text theo câu, đảm bảo mỗi chunk không vượt quá max_size.
    """
    # Split theo dấu chấm, nhưng giữ nguyên câu
    sentences = re.split(r"(?<=[.!?])\s+", text)

    chunks = []
    current_chunk = ""

    for sentence in sentences:
        if not sentence.strip():
            continue

        potential = current_chunk + " " + sentence if current_chunk else sentence

        if len(potential) <= max_size:
            current_chunk = potential
        else:
            if current_chunk:
                chunks.append(current_chunk.strip())
            current_chunk = sentence

    if current_chunk.strip():
        chunks.append(current_chunk.strip())

    return chunks if chunks else [text]


def convert_to_documents(
    chunks: list[dict], apply_split: bool = True
) -> List[Dict[str, Any]]:
    """
    Chuyển đổi chunks thành documents với:
    1. Context header
    2. Split chunks dài
    3. Merge chunks ngắn

    FIX: Sử dụng unique_id thay vì section_id cho chunk_map
    """
    # Build chunk_map để lookup parent (dùng unique_id)
    chunk_map = {}
    for c in chunks:
        uid = c.get("unique_id")
        if uid:
            chunk_map[uid] = c

    documents = []
    doc_index = 1

    for chunk in chunks:
        title = chunk.get("title", "")
        text = chunk.get("text", "")
        full_content = f"{title}\n{text}".strip()

        # Build context header
        context_header = build_context_header(chunk, chunk_map)

        if apply_split and len(full_content) > MAX_CHUNK_SIZE:
            # Split chunk dài
            sub_chunks = split_long_content(text, title)

            for sub in sub_chunks:
                sub_content = sub["content"]
                sub_title = sub.get("sub_title", "")
                sub_id = sub.get("sub_id", "")

                # Thêm context header
                final_content = (
                    f"{context_header}\n{sub_content}"
                    if context_header
                    else sub_content
                )
                cleaned_content = clean_text(final_content)

                if len(cleaned_content) < MIN_CHUNK_SIZE:
                    continue  # Bỏ qua chunk quá ngắn

                doc = {
                    "index": doc_index,
                    "section_id": chunk["section_id"],
                    "sub_id": sub_id,
                    "level": chunk["level"],
                    "parent_id": chunk.get("parent_id"),
                    "parent_title": chunk.get("parent_title"),
                    "title": title,
                    "sub_title": sub_title,
                    "context_header": context_header,
                    "content": cleaned_content,
                    "content_raw": sub_content,
                    "metadata": {
                        "page_start": chunk["page_start"],
                        "source": chunk["source"],
                        "char_count": len(cleaned_content),
                        "is_split": True,
                    },
                }
                documents.append(doc)
                doc_index += 1
        else:
            # Chunk đủ ngắn hoặc không cần split
            final_content = (
                f"{context_header}\n{full_content}" if context_header else full_content
            )
            cleaned_content = clean_text(final_content)

            # Đánh dấu chunk ngắn
            is_short = len(cleaned_content) < MIN_CHUNK_SIZE

            doc = {
                "index": doc_index,
                "section_id": chunk["section_id"],
                "sub_id": None,
                "level": chunk["level"],
                "parent_id": chunk.get("parent_id"),
                "parent_title": chunk.get("parent_title"),
                "title": title,
                "sub_title": None,
                "context_header": context_header,
                "content": cleaned_content,
                "content_raw": text,
                "metadata": {
                    "page_start": chunk["page_start"],
                    "source": chunk["source"],
                    "char_count": len(cleaned_content),
                    "is_split": False,
                    "is_short": is_short,
                },
            }
            documents.append(doc)
            doc_index += 1

    # Merge short chunks with next sibling
    documents = merge_short_chunks(documents)

    # Re-index
    for i, doc in enumerate(documents, 1):
        doc["index"] = i

    return documents


def merge_short_chunks(documents: List[Dict]) -> List[Dict]:
    """
    Merge các chunk ngắn với chunk tiếp theo cùng parent.
    """
    if not documents:
        return documents

    merged = []
    i = 0

    while i < len(documents):
        current = documents[i]

        # Kiểm tra nếu chunk ngắn và có thể merge
        if current["metadata"].get("is_short", False) and i + 1 < len(documents):

            next_doc = documents[i + 1]

            # Chỉ merge nếu cùng parent
            if current.get("parent_id") == next_doc.get("parent_id"):
                combined_content = current["content"] + "\n\n" + next_doc["content"]

                if len(combined_content) <= MAX_CHUNK_SIZE:
                    # Merge
                    merged_doc = {
                        **next_doc,
                        "content": combined_content,
                        "title": current["title"] + " + " + next_doc["title"],
                        "metadata": {
                            **next_doc["metadata"],
                            "char_count": len(combined_content),
                            "merged_from": [
                                current["section_id"],
                                next_doc["section_id"],
                            ],
                        },
                    }
                    merged.append(merged_doc)
                    i += 2
                    continue

        merged.append(current)
        i += 1

    return merged


def extract_dsm_chunk_hierarchical(pdf_path: str) -> List[Dict[str, Any]]:
    """
    Trích xuất và chunk tài liệu DSM-5 tiếng Việt theo cấu trúc phân cấp.

    Cải tiến:
    1. Fix parent_id tracking - xóa level cao hơn khi gặp section mới
    2. Lọc footer trang
    3. Sử dụng unique_id để tránh conflict khi có duplicate section_id
    """
    chunks = []
    current_chunk = None
    buffer_lines = []

    # Lưu mục gần nhất ở mỗi cấp độ: {level: unique_id}
    last_section_at_level: Dict[int, str] = {}

    # Counter để tạo unique_id
    chunk_counter = 0

    with pdfplumber.open(pdf_path) as pdf:
        for page_num, page in enumerate(pdf.pages, 1):
            text = page.extract_text(x_tolerance=1, y_tolerance=1)
            if not text or not text.strip():
                continue

            lines = text.split("\n")

            for line in lines:
                line = line.strip()
                if not line:
                    continue

                # Bỏ qua footer trang
                if PAGE_FOOTER_PATTERN.match(line):
                    continue

                matched = SECTION_PATTERN.match(line)

                if matched:
                    # Lưu chunk hiện tại (nếu có)
                    if current_chunk is not None:
                        if buffer_lines:
                            current_chunk["text"] = smart_join_lines(buffer_lines)
                        chunks.append(current_chunk)
                        buffer_lines = []

                    section_id = matched.group(1)
                    level = len(section_id.split("."))

                    # Tạo unique_id
                    chunk_counter += 1
                    unique_id = f"chunk_{chunk_counter}"

                    # ✅ FIX: Xóa các level >= level hiện tại
                    # Điều này đảm bảo parent_id luôn chính xác
                    keys_to_remove = [k for k in last_section_at_level if k >= level]
                    for k in keys_to_remove:
                        del last_section_at_level[k]

                    # Lưu unique_id của level hiện tại
                    last_section_at_level[level] = unique_id

                    # Tìm parent_unique_id (level gần nhất thấp hơn)
                    parent_unique_id = None
                    for line in range(level - 1, 0, -1):
                        if line in last_section_at_level:
                            parent_unique_id = last_section_at_level[line]
                            break

                    current_chunk = {
                        "unique_id": unique_id,
                        "section_id": section_id,
                        "level": level,
                        "parent_id": (
                            section_id.rsplit(".", 1)[0] if "." in section_id else None
                        ),  # Vẫn giữ cho reference
                        "parent_unique_id": parent_unique_id,
                        "title": line,
                        "text": "",
                        "page_start": page_num,
                        "source": os.path.abspath(pdf_path),
                    }

                else:
                    # Không phải title → thêm vào buffer
                    if current_chunk is not None:
                        buffer_lines.append(line)

        # Xử lý chunk cuối cùng
        if current_chunk is not None:
            if buffer_lines:
                current_chunk["text"] = smart_join_lines(buffer_lines)
            chunks.append(current_chunk)

    # Thêm parent_title
    chunks = add_parent_title(chunks)

    # Convert sang documents với split/merge
    documents = convert_to_documents(chunks, apply_split=True)

    return documents


def print_statistics(documents: List[Dict]) -> None:
    """In thống kê về chunks."""
    if not documents:
        print("Không có chunks!")
        return

    sizes = [doc["metadata"]["char_count"] for doc in documents]

    print("\n" + "=" * 60)
    print("📊 THỐNG KÊ CHUNKS")
    print("=" * 60)
    print(f"Tổng số chunks: {len(documents)}")
    print(f"Kích thước trung bình: {sum(sizes) / len(sizes):.0f} ký tự")
    print(f"Kích thước nhỏ nhất: {min(sizes)} ký tự")
    print(f"Kích thước lớn nhất: {max(sizes)} ký tự")

    # Phân bố theo size
    short = sum(1 for s in sizes if s < MIN_CHUNK_SIZE)
    medium = sum(1 for s in sizes if MIN_CHUNK_SIZE <= s <= MAX_CHUNK_SIZE)
    long = sum(1 for s in sizes if s > MAX_CHUNK_SIZE)

    print("\nPhân bố kích thước:")
    print(f"  - Ngắn (<{MIN_CHUNK_SIZE}): {short}")
    print(f"  - Vừa ({MIN_CHUNK_SIZE}-{MAX_CHUNK_SIZE}): {medium}")
    print(f"  - Dài (>{MAX_CHUNK_SIZE}): {long}")

    # Theo level
    level_counts: Dict[int, int] = {}
    for doc in documents:
        lvl = doc["level"]
        level_counts[lvl] = level_counts.get(lvl, 0) + 1

    print("\nTheo cấp độ:")
    for lvl in sorted(level_counts.keys()):
        print(f"  - Level {lvl}: {level_counts[lvl]}")


if __name__ == "__main__":
    PDF_PATH = "/home/ducpham/workspace/LLM-Chatbot-with-LangChain-and-Neo4j/data/dsm-5-cac-tieu-chuan-chan-doan.pdf"

    print("🔄 Đang xử lý PDF...")
    chunks = extract_dsm_chunk_hierarchical(PDF_PATH)

    # In thống kê
    print_statistics(chunks)

    # In 5 chunks đầu tiên để kiểm tra
    print("\n" + "=" * 60)
    print("📝 MẪU 5 CHUNKS ĐẦU TIÊN")
    print("=" * 60)
    for chunk in chunks[:5]:
        print(f"\n--- Chunk {chunk['index']} ---")
        print(f"Section ID: {chunk['section_id']}")
        print(f"Level: {chunk['level']}")
        print(f"Parent: {chunk.get('parent_title', 'None')}")
        print(f"Title: {chunk['title'][:50]}...")
        print(
            f"Context: {chunk['context_header'][:80]}..."
            if chunk.get("context_header")
            else "Context: None"
        )
        print(f"Size: {chunk['metadata']['char_count']} chars")
        print(f"Content preview: {chunk['content'][:150]}...")

    # Lưu JSON
    import json

    with open("dsm5_chunks.json", "w", encoding="utf-8") as f:
        json.dump(chunks, f, ensure_ascii=False, indent=2)

    print(f"\n✅ Đã lưu {len(chunks)} chunks vào dsm5_chunks.json")
