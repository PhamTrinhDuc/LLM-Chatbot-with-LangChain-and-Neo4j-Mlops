from __future__ import annotations

import os
import re
import uuid
import asyncio
import html as _html
import unicodedata
from asyncio import to_thread
from loguru import logger
from dataclasses import dataclass
from typing import Optional, Iterable

import fitz
from dotenv import load_dotenv, find_dotenv
from elasticsearch import Elasticsearch, helpers

from ai_race.config.config import settings
from ai_race.utils.io import ensure_dirs, list_pdfs
from ai_race.utils.word_segmentation import segment_text
from ai_race.utils.table_utils import merge_adjacent_tables
from scripts.evaluation.utils import extract_task_section

__all__ = ["index_titles_to_es", "index_keyword_chunks_to_es"]

load_dotenv(find_dotenv())

# Regex chung cho parser
DOC_SPLIT_RE = re.compile(r"^#\s*(Public[_-]?\d{3,})[^\n]*$", flags=re.M)
HEADER_RE = re.compile(r"^(?P<hashes>#{1,6})\s+(?P<title>.+?)\s*$", flags=re.M)
TABLE_RE = re.compile(r"<table\b[^>]*>.*?</table>", flags=re.S | re.I)
CELL_RE = re.compile(r"<t[dh][^>]*>(.*?)</t[dh]>", flags=re.S | re.I)
BLOCK_FORMULA_RE = re.compile(r"\$\$(.*?)\$\$", flags=re.S)
ALL_FORMULAS_RE = re.compile(r"\$\$(.*?)\$\$|\$(?!\$)(.*?)(?<!\$)\$", flags=re.S)
TAG_RE = re.compile(r"<[^>]+>")
IMAGE_PLACEHOLDER_RE = re.compile(r"\|\s*<\s*image\s*_\s*\d+\s*>\s*\|", flags=re.I)
HEADER_HASH_PREFIX_RE = re.compile(r"^\s*#{1,6}\s*", flags=re.M)
DASHES_BULLETS_RE = re.compile(r"[–—\-•·∙‣▪•]+")
NONWORD_PUNCT_TO_SPACE_RE = re.compile(r"[^\w\s]", flags=re.UNICODE)
TABLE_OPEN_RE  = re.compile(r"<table\b[^>]*>", flags=re.I)
TABLE_CLOSE_RE = re.compile(r"</table\s*>", flags=re.I)
COLGROUP_RE    = re.compile(r"<colgroup\b[^>]*>.*?</colgroup\s*>", flags=re.S | re.I)
THEAD_RE       = re.compile(r"<thead\b[^>]*>.*?</thead\s*>", flags=re.S | re.I)
TBODY_RE       = re.compile(r"<tbody\b[^>]*>.*?</tbody\s*>", flags=re.S | re.I)
TR_RE          = re.compile(r"<tr\b[^>]*>.*?</tr>", flags=re.S | re.I)


def _get_es(es_client: Optional[Elasticsearch] = None) -> Elasticsearch:
    if es_client is not None:
        return es_client

    if settings.es_ca_cert:
        return Elasticsearch(
            settings.es_url,
            basic_auth=(settings.es_user, settings.es_password),
            ca_certs=settings.es_ca_cert,
            verify_certs=True
        )
    else:
        return Elasticsearch(
            settings.es_url,
            basic_auth=(settings.es_user, settings.es_password),
            verify_certs=False
        )

def _vn_segment_or_identity(s: str) -> str:
    try:
        return segment_text(s)
    except Exception:
        return s

async def _vn_segment_or_identity_async(s: str) -> str:
    return await to_thread(_vn_segment_or_identity, s)

# ---------------------------------------------------------------------
# ES index helpers
# ---------------------------------------------------------------------
def _create_titles_index(es: Elasticsearch, index_name: str, use_icu: bool = True) -> None:
    if es.options(ignore_status=[400, 404]).indices.exists(index=index_name):
        es.options(ignore_status=[400, 404]).indices.delete(index=index_name)
        logger.info(f"Deleted index {index_name}")

    folding = "icu_folding" if use_icu else "asciifolding"
    
    body = {
        "settings": {
            "analysis": {
                "normalizer": {
                    "vn_keyword": {"type": "custom", "filter": ["lowercase", "asciifolding"]},
                },
                "analyzer": {
                    "vietnamese_segmented": {
                        "type": "custom",
                        "tokenizer": "whitespace",
                        "filter": ["lowercase", folding],
                    }
                },
            }
        },
        "mappings": {
            "properties": {
                "doc_name": {"type": "keyword", "normalizer": "vn_keyword"},
                "doc_name_infile": {"type": "keyword", "normalizer": "vn_keyword"},
                "title": {"type": "text", "analyzer": "vietnamese_segmented", "search_analyzer": "vietnamese_segmented"},
                "title_raw": {"type": "text", "index": False, "store": False},
            }
        },
    }
    try:
        es.indices.create(index=index_name, body=body)
    except Exception as e:
        # fallback nếu thiếu plugin ICU
        if use_icu:
            logger.warning(f"Retry creating index without ICU filter due to: {e}")
            _create_titles_index(es, index_name, use_icu=False)
        else:
            raise

def _create_chunks_index(es: Elasticsearch, index_name: str, use_icu: bool = True) -> None:
    if es.options(ignore_status=[400, 404]).indices.exists(index=index_name):
        es.options(ignore_status=[400, 404]).indices.delete(index=index_name)
        logger.info(f"Deleted index {index_name}")

    folding = "icu_folding" if use_icu else "asciifolding"
    body = {
        "settings": {
            "analysis": {
                "normalizer": {
                    "vn_keyword": {"type": "custom", "filter": ["lowercase", "asciifolding"]},
                },
                "analyzer": {
                    "vietnamese_segmented": {
                        "type": "custom",
                        "tokenizer": "whitespace",
                        "filter": ["lowercase", folding],
                    }
                },
            }
        },
        "mappings": {
            "properties": {
                "doc_name": {"type": "keyword", "normalizer": "vn_keyword"},
                "section_id": {"type": "keyword"},
                "section_level": {"type": "integer"},
                "chunk_id": {"type": "integer"},
                "global_order": {"type": "integer"},
                "header_path_raw": {"type": "keyword", "normalizer": "vn_keyword"},
                "header_path_text": {"type": "text", "analyzer": "vietnamese_segmented"},
                "content": {"type": "text", "analyzer": "vietnamese_segmented"},
                "content_raw": {"type": "text", "index": False},
                "parent_text": {"type": "text", "analyzer": "vietnamese_segmented"},
                "parent_text_raw": {"type": "text", "index": False},
            }
        },
    }
    try:
        es.indices.create(index=index_name, body=body)
    except Exception as e:
        if use_icu:
            logger.warning(f"Retry creating index without ICU filter due to: {e}")
            _create_chunks_index(es, index_name, use_icu=False)
        else:
            raise

# ---------------------------------------------------------------------
# Title extraction helpers
# ---------------------------------------------------------------------
def _extract_headers_from_pdfs(pdf_files: Iterable[str]) -> list[dict]:
    """
    Đọc trang 1 của mỗi PDF, cắt 'TDxxx ... Lần ban hành', trả về [{name, header}]
    """
    #TODO: Cần bắt header chuẩn hơn do nội dung thay đổi
    headers = []
    pattern = re.compile(
        r"\b(?:(TD|Public)\s*\d+)\s+(.*?)\s+(?:Lần ban hành|Soát xét lần)",
        flags=re.S
    )
    for pdf_file in pdf_files:
        doc = fitz.open(pdf_file)
        text = doc[0].get_text("text")
        match = pattern.search(text)
        header = ""
        if match:
            full_match = match.group(0)
            code_match = re.match(r"(TD|Public)\s*\d+", full_match)
            doc_name_infile = code_match.group(0).strip() if code_match else ""
            header = re.sub(r"\s+", " ", match.group(2)).strip()
        else:
            lines = text.split("\n")
            first_index = next(
                (i for i, s in enumerate(lines) if "race" in s.lower()),
                0
            )
            start = min(first_index + 2, len(lines))
            lst = lines[start:]
            first_empty = next((i for i, s in enumerate(lst) if s.strip() == ""), len(lst))
            end = first_empty - 1

            header_list = lst[:end]
            header = " ".join(s.strip() for s in header_list)
            doc_name_infile = ""

        filename = os.path.basename(pdf_file)
        name_only = os.path.splitext(filename)[0]
        headers.append({
            "name": name_only,
            "header": header,
            "doc_name_infile": doc_name_infile
        })
    return headers

# ---------------------------------------------------------------------
# Markdown parsing + chunking helpers (nội bộ)
# ---------------------------------------------------------------------
def _split_markdown_documents(md_text: str) -> dict[str, str]:
    """Tách nhiều document trong 1 file markdown theo header '# Public_001'."""
    parts = re.split(DOC_SPLIT_RE, md_text)
    docs = {}
    # parts: ["...prefix...", "Public_001", "content1", "Public_002", "content2", ...]
    for i in range(1, len(parts), 2):
        file_name = parts[i].strip()
        content = parts[i + 1].strip()
        docs[file_name] = content
    return docs

def _split_units_preserve_blocks(text: str) -> list[tuple[str, str]]:
    """
    Tách text thành các unit theo thứ tự xuất hiện:
      ('table', '<table>...</table>'),
      ('block_formula', '$$...$$'),
      ('text', '...bất kỳ...').
    """
    units: list[tuple[str, str]] = []
    i = 0
    n = len(text)
    while i < n:
        # tìm đoạn tới gần nhất của table/block_formula
        table_m = TABLE_RE.search(text, i)
        math_m = BLOCK_FORMULA_RE.search(text, i)
        # chọn match sớm nhất
        candidates = [(table_m, 'table'), (math_m, 'block_formula')]
        candidates = [(m, t) for m, t in candidates if m]
        if not candidates:
            if i < n:
                units.append(('text', text[i:]))
            break
        m, typ = min(candidates, key=lambda x: x[0].start())
        # prefix text trước block
        if m.start() > i:
            units.append(('text', text[i:m.start()]))
        units.append((typ, m.group(0)))
        i = m.end()
    return units

def _split_sentences(text: str) -> list[str]:
    """Tách câu dựa trên ., ?, ! (có hỗ trợ khoảng trắng VN)."""
    sents = re.split(r'(?<=[.!?])\s+', text.strip())
    return [s.strip() for s in sents if s.strip()]

def _chunk_by_sentence_with_word_budget(text: str, chunk_size: int = 300, overlap: int = 30) -> list[str]:
    """
    Chunk theo câu (BM25-friendly).
    - Text: gói theo câu, tôn trọng chunk_size + overlap.
    - Table: chia nhỏ theo hàng <tr>, mỗi nhóm hàng được bọc lại thành <table ...>...</table>.
    - Block công thức $$...$$: không cắt.
    """
    # --- helpers ------------------------------------------------------
    def _normalize_ws_local(s: str) -> str:
        return re.sub(r"\s+", " ", s).strip()

    def _row_effective_text(row_html: str) -> str:
        """
        Lấy “text hữu ích” của 1 hàng (gần giống _extract_table_text_for_bm25):
          - Bỏ công thức inline/block
          - Lấy text từ các cell
          - Bỏ ô toàn số & quá ngắn (<= 3 từ)
          - Chuẩn hóa khoảng trắng, ký tự nối
        """
        kept_cells = []
        # Lặp các cell trong row
        for m in CELL_RE.finditer(row_html):
            cell_html = m.group(1)
            cell_no_math = ALL_FORMULAS_RE.sub("", cell_html)
            cell_text = TAG_RE.sub(" ", cell_no_math)
            cell_text = _html.unescape(cell_text)
            cell_text = re.sub(r"[–—\-•·/]", " ", cell_text)
            cell_text = _normalize_ws_local(cell_text)
            if not cell_text:
                continue
            words = cell_text.split()
            # bỏ ô toàn số
            if all(re.fullmatch(r"[+-]?\d+(?:[.,]\d+)?(?:[%/])?", w) for w in words):
                continue
            if len(words) <= 3:
                continue
            kept_cells.append(cell_text)
        return " ".join(kept_cells).strip()

    def _count_words_text(s: str) -> int:
        return len(s.split())

    def _count_words_table_rows(rows_html: list[str]) -> int:
        # Ước lượng số từ hữu ích của 1 nhóm hàng
        texts = []
        for r in rows_html:
            t = _row_effective_text(r)
            if t:
                texts.append(t)
        return _count_words_text(" ".join(texts))

    def _wrap_rows_as_table(original_table_html: str, rows_html: list[str]) -> str:
        """
        Duy trì opening tag của bảng gốc (để giữ thuộc tính), đồng thời bảo toàn
        <colgroup> và <thead> (nếu có). Các hàng được bọc trong <tbody> mới.
        """
        open_m = TABLE_OPEN_RE.search(original_table_html)
        open_tag = open_m.group(0) if open_m else "<table>"
        colgroup_m = COLGROUP_RE.search(original_table_html)
        thead_m = THEAD_RE.search(original_table_html)
        colgroup_html = colgroup_m.group(0) if colgroup_m else ""
        thead_html = thead_m.group(0) if thead_m else ""
        body_html = "<tbody>" + "".join(rows_html) + "</tbody>"
        return f"{open_tag}{colgroup_html}{thead_html}{body_html}</table>"

    units = _split_units_preserve_blocks(text)

    items: list[tuple[str, str]] = []  # ('text'|'table'|'block_formula', content)
    for typ, content in units:
        if typ == 'text':
            for sent in _split_sentences(content):
                if sent:
                    items.append(('text', sent))
        elif typ == 'block_formula':
            items.append(('block_formula', content.strip()))
        else:  # 'table'
            table_html = content.strip()

            # Ưu tiên lấy các hàng bên trong <tbody>
            tbody_m = TBODY_RE.search(table_html)
            if tbody_m:
                tbody_html = tbody_m.group(0)
                rows = TR_RE.findall(tbody_html)
            else:
                # Fallback: loại <colgroup> và <thead> trước khi lấy <tr>
                tmp = COLGROUP_RE.sub("", table_html)
                tmp = THEAD_RE.sub("", tmp)
                rows = TR_RE.findall(tmp)

            if not rows:
                rows = [table_html]  # fallback cuối cùng

            # Gom hàng vào các “lát” theo chunk_size (dựa trên số từ hữu ích)
            cur_rows: list[str] = []
            cur_words = 0
            i = 0
            n = len(rows)
            while i < n:
                row_html = rows[i]
                row_words = _count_words_table_rows([row_html])
                # Nếu hàng quá dài > chunk_size, cứ để hàng này thành một lát riêng
                if row_words > chunk_size and not cur_rows:
                    mini = _wrap_rows_as_table(table_html, [row_html])
                    items.append(('table', mini))
                    i += 1
                    continue

                if cur_words + row_words <= chunk_size:
                    cur_rows.append(row_html)
                    cur_words += row_words
                    i += 1
                else:
                    # flush nhóm hàng hiện tại
                    if cur_rows:
                        mini = _wrap_rows_as_table(table_html, cur_rows)
                        items.append(('table', mini))
                        cur_rows = []
                        cur_words = 0
                    else:
                        # Không có gì trong cur_rows mà vẫn vượt -> ép hàng hiện tại vào lát riêng
                        mini = _wrap_rows_as_table(table_html, [row_html])
                        items.append(('table', mini))
                        i += 1

            if cur_rows:
                mini = _wrap_rows_as_table(table_html, cur_rows)
                items.append(('table', mini))


    chunks: list[str] = []
    cur_parts: list[str] = []
    cur_words = 0

    def flush_with_overlap():
        nonlocal cur_parts, cur_words
        if not cur_parts:
            return
        chunk_text = "\n".join(cur_parts).strip()
        if chunk_text:
            chunks.append(chunk_text)
        # overlap: chỉ lấy từ của phần text ở cuối chunk
        if overlap > 0:
            # tìm phần text cuối cùng trong cur_parts
            tail_text_words: list[str] = []
            for part in reversed(cur_parts):
                # chỉ tính overlap từ TEXT (đừng lấy table/block_formula)
                if part.startswith("<table") or part.startswith("$$"):
                    continue
                w = part.split()
                if w:
                    tail_text_words = w + tail_text_words
                if len(tail_text_words) >= overlap:
                    break
            tail_text_words = tail_text_words[-overlap:]
            cur_parts = [" ".join(tail_text_words)] if tail_text_words else []
            cur_words = len(tail_text_words)
        else:
            cur_parts = []
            cur_words = 0

    # VÒNG LẶP THỨ HAI: chỉ ráp chunk
    for typ, content in items:
        if typ == 'text':
            w = content.split()
            if cur_words + len(w) <= chunk_size:
                cur_parts.append(content)
                cur_words += len(w)
            else:
                flush_with_overlap()
                cur_parts.append(content)
                cur_words = len(w)
        elif typ == 'table':
            # Đếm số từ hữu ích của mini-table
            row_list = TR_RE.findall(content) or []
            table_words = _count_words_table_rows(row_list) if row_list else _count_words_text(content)
            if cur_words > 0 and cur_words + table_words > chunk_size:
                flush_with_overlap()
            # Nếu mini-table vẫn vượt chunk_size, đặt riêng 1 chunk
            if table_words > chunk_size:
                chunks.append(content)
                cur_parts = []
                cur_words = 0
            else:
                # có thể gộp cùng text hiện tại
                cur_parts.append(content)
                cur_words += table_words
                # để tránh overlap kéo theo table => flush ngay cho sạch biên
                flush_with_overlap()

        else:  # 'block_formula'
            # Giữ atomic; nếu không vừa thì flush trước để nằm chunk riêng
            wlen = _count_words_text(ALL_FORMULAS_RE.sub(" ", content))
            if cur_words > 0 and cur_words + wlen > chunk_size:
                flush_with_overlap()
            cur_parts.append(content)
            cur_words += wlen
            # flush để không dính overlap với công thức
            flush_with_overlap()

    if cur_parts:
        chunks.append("\n".join(cur_parts).strip())

    return [c for c in chunks if c.strip()]

def _strip_formulas(text: str) -> str:
    """Bỏ mọi công thức (inline + block) khỏi text."""
    return ALL_FORMULAS_RE.sub("", text)

def _normalize_ws(s: str) -> str:
    # chuẩn hoá khoảng trắng
    return re.sub(r"\s+", " ", s).strip()

def _is_numeric_cell(words: list[str]) -> bool:
    # toàn bộ words là số (cho phép ., , %, /, - trong biểu diễn)
    if not words:
        return False
    return all(re.fullmatch(r"[+-]?\d+(?:[.,]\d+)?(?:[%/])?", w) for w in words)

def _extract_table_text_for_bm25(html: str) -> str:
    """
    Lấy text theo CỤM Ô:
        - Bỏ công thức (inline + block) trong từng ô
        - Bóc text (bỏ tag), unescape entity
        - Chuẩn hoá khoảng trắng & ký tự nối (– — - / • ·) -> ' '
        - Đếm SỐ TỪ (split)
        - Giữ ô nếu số từ > 3 và không phải toàn số
    """
    kept_cells: list[str] = []

    for m in CELL_RE.finditer(html):
        cell_html = m.group(1)

        # 1) bỏ mọi công thức trong ô
        cell_no_math = ALL_FORMULAS_RE.sub("", cell_html)

        # 2) bỏ tag -> text, unescape entity
        cell_text = TAG_RE.sub(" ", cell_no_math)
        cell_text = _html.unescape(cell_text)

        # 3) chuẩn hoá các ký tự nối & whitespace
        #    (đưa các dấu nối phổ biến về space để split() cho ổn định)
        cell_text = re.sub(r"[–—\-•·/]", " ", cell_text)
        cell_text = _normalize_ws(cell_text)

        if not cell_text:
            continue

        # 4) đếm số từ theo split()
        words = cell_text.split()

        # 5) loại ô toàn số
        if _is_numeric_cell(words):
            continue

        # 6) lọc theo "độ dài cụm = SỐ TỪ"
        if len(words) <= 3:
            continue

        kept_cells.append(cell_text)

    return " ".join(kept_cells).strip()

def _strip_headers_and_images(text: str) -> str:
    """
    - Gỡ các dấu # ở đầu dòng header (giữ nguyên chữ sau #)
    - Xoá placeholder ảnh |<image_n>|
    - Chuẩn hoá khoảng trắng dư
    """
    # 1) bỏ dấu # ở đầu header nhưng giữ lại phần chữ
    text = HEADER_HASH_PREFIX_RE.sub("", text)
    # 2) bỏ placeholder ảnh
    text = IMAGE_PLACEHOLDER_RE.sub(" ", text)
    # 3) gọn khoảng trắng
    text = re.sub(r"[ \t]+\n", "\n", text)          # space trước newline
    text = re.sub(r"\n{3,}", "\n\n", text)          # nhiều newline -> 2
    text = re.sub(r"[ \t]{2,}", " ", text)          # nhiều space -> 1
    return text.strip()

def _strip_punctuation_for_bm25(text: str) -> str:
    """
    - Chuyển các dấu gạch/dấu bullet phổ biến thành khoảng trắng (tránh dính chữ).
    - Loại các dấu câu/biểu tượng còn lại (trừ ký tự chữ/số/_ và khoảng trắng).
    - Chuẩn hoá khoảng trắng.
    """
    text = DASHES_BULLETS_RE.sub(" ", text)
    text = NONWORD_PUNCT_TO_SPACE_RE.sub(" ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text

def _process_text_for_bm25(text: str) -> str:
    """
    Dùng cho 'content'/'parent_text':
        - với vùng <table>...</table>: thay bằng text đã lọc (độ dài >3, bỏ số, bỏ công thức)
        - phần còn lại: bỏ công thức.
    """
    text = unicodedata.normalize("NFC", text)
    text = _strip_headers_and_images(text)
    out = []
    i = 0
    for m in TABLE_RE.finditer(text):
        # phần trước bảng: bỏ công thức
        if m.start() > i:
            out.append(_strip_formulas(text[i:m.start()]))
        # phần bảng: lọc theo rule
        out.append(_extract_table_text_for_bm25(m.group(0)))
        i = m.end()
    if i < len(text):
        out.append(_strip_formulas(text[i:]))

    merged = " ".join(s.strip() for s in out if s and s.strip()).strip()

    merged = _strip_punctuation_for_bm25(merged)
    return merged

def _process_text_for_raw(text: str) -> str:
    """
    Làm sạch nội dung các cells trong bảng:
    Loại bỏ <p>...</p>, <br> và xuống dòng trong <td>/<th>.
    Trả lại <td>...<td> với content đã gọn thành một chuỗi.
    """
    if not text:
        return text

    text = unicodedata.normalize("NFC", text)
    text = merge_adjacent_tables(text)

    def process_table(table_match):
        table_html = table_match.group(0)

        def replace_cell(cell_match):
            full_match = cell_match.group(0)   # <td...>content</td> hoặc <th...>...</th>
            cell_content = cell_match.group(1) # content bên trong

            # Tách opening/closing tag để giữ nguyên thuộc tính
            opening_tag_end = full_match.find('>')
            opening_tag = full_match[:opening_tag_end + 1]
            closing_tag_start = full_match.rfind('</')
            closing_tag = full_match[closing_tag_start:]

            # Làm sạch bên trong cell
            cleaned = cell_content
            cleaned = re.sub(r"</?p\b[^>]*>", " ", cleaned, flags=re.I)
            cleaned = re.sub(r"<br\s*/?>", " ", cleaned, flags=re.I)
            cleaned = _html.unescape(cleaned)
            cleaned = re.sub(r'\s+', ' ', cleaned).strip()

            return f"{opening_tag}{cleaned}{closing_tag}"

        return CELL_RE.sub(replace_cell, table_html)

    return TABLE_RE.sub(process_table, text)

@dataclass
class _Section:
    level: int
    title: str
    start: int
    body_start: int
    body_end: int
    text: str
    path: list[str]
    path_levels: list[tuple[int, str]]
    own_text: str
    children_titles: list[str]
    children_levels: list[int]

def _parse_sections_tree(doc_text: str) -> list[_Section]:
    headers = []
    for m in HEADER_RE.finditer(doc_text):
        level = len(m.group("hashes"))
        title = m.group("title").strip()
        headers.append({"level": level, "title": title, "start": m.start(), "body_start": m.end()})
    if not headers:
        return [_Section(1, "", 0, 0, len(doc_text), doc_text, [""], [(1, "")], doc_text, [], [])]

    first_header_start = headers[0]["start"]
    if first_header_start > 0:
        headers.insert(0, {
            "level": 1,
            "title": "Overview",
            "start": 0,
            "body_start": 0
        })

    for i, h in enumerate(headers):
        end = len(doc_text)
        for j in range(i + 1, len(headers)):
            if headers[j]["level"] <= h["level"]:
                end = headers[j]["start"]
                break
        h["body_end"] = end

    sections, stack = [], []
    for i, h in enumerate(headers):
        while stack and stack[-1][0] >= h["level"]:
            stack.pop()
        path_levels = stack + [(h["level"], h["title"])]
        path = [t for _, t in path_levels]
        children, children_levels, first_child_start = [], [], h["body_end"]
        for j in range(i + 1, len(headers)):
            hj = headers[j]
            if hj["level"] <= h["level"]:
                break
            if hj["level"] == h["level"] + 1:
                children.append(hj)
                children_levels.append(hj["level"])
                first_child_start = min(first_child_start, hj["start"])
        own_end = first_child_start
        own_text = doc_text[h["body_start"] : own_end].strip()
        sections.append(
            _Section(
                level=h["level"],
                title=h["title"],
                start=h["start"],
                body_start=h["body_start"],
                body_end=h["body_end"],
                text=doc_text[h["body_start"] : h["body_end"]].strip(),
                path=path,
                path_levels=path_levels,
                own_text=own_text,
                children_titles=[c["title"] for c in children],
                children_levels=children_levels,
            )
        )
        stack.append((h["level"], h["title"]))
    return sections

def _format_header_line(level: int, title: str) -> str:
    return f"{'#' * level} {title}".strip()

def _make_header_path_str_with_hashes(path_levels: list[tuple[int, str]]) -> str:
    return "\n".join(_format_header_line(lv, t) for lv, t in path_levels).strip()

def _build_parent_text(header_path: str, sec: _Section, all_sections: list[_Section]) -> str:
    """
    Parent mở rộng: bao gồm toàn bộ header con (mọi cấp) nằm trong phạm vi body của section.
    """
    lines = [header_path]
    if sec.own_text:
        lines.append(sec.own_text)
    subheaders = [s for s in all_sections if s.start > sec.body_start and s.start < sec.body_end]
    for s in subheaders:
        lines.append(_format_header_line(s.level, s.title))
    return "\n".join(lines).strip()

def _parse_and_chunk_markdown_for_bm25(md_path: str, chunk_size: int = 300, overlap: int = 30) -> list[dict]:
    """
    Đọc markdown, tách doc (# Public_001...), build sections theo header tree,
    chunk trong phạm vi mỗi section. Mỗi chunk con mang theo:
      - header_path (breadcrumb)
      - content_raw = "{breadcrumb}\n{chunk_text}"
      - parent_text_raw = "{breadcrumb}\n{full_section_text}"
    """
    with open(md_path, "r", encoding="utf-8") as f:
        raw = f.read()
    # Cắt theo "TASK EXTRACT" nếu có
    try:
        text = extract_task_section(md_content=raw, section_name="TASK EXTRACT", end_section_name="TASK QA")
    except Exception:
        text = raw

    documents = _split_markdown_documents(text)
    results = []
    global_chunk_counter = 0

    for doc_name, content in documents.items():
        # Loại bỏ các thẻ bố cục
        cleaned = re.sub(r"</?p\b[^>]*>", " ", content, flags=re.I)
        cleaned = re.sub(r"<br\s*/?>", " ", cleaned, flags=re.I)
        cleaned = re.sub(r"</?div\b[^>]*>", " ", cleaned, flags=re.I)

        # Loại bỏ các thẻ định dạng
        cleaned = re.sub(r"</?(strong|b|em|i|u|mark)\b[^>]*>", "", cleaned, flags=re.I)

        cleaned = _html.unescape(cleaned)

        # Loại bỏ _**, **_, ** (pipeline task 1)
        cleaned = re.sub(r"_\*\*", " ", cleaned)
        cleaned = re.sub(r"\*\*_", " ", cleaned)
        cleaned = re.sub(r"\*\*", " ", cleaned)
        
        content = cleaned
    
        sections = _parse_sections_tree(content)
        for sec in sections:
            header_path = _make_header_path_str_with_hashes(sec.path_levels)
            parent_text_raw = _build_parent_text(header_path, sec, sections)
            text_for_chunking = (sec.own_text or "").strip()
            if not text_for_chunking:
                continue
            child_chunks = _chunk_by_sentence_with_word_budget(text_for_chunking, chunk_size=chunk_size, overlap=overlap)
            section_id = str(uuid.uuid5(uuid.NAMESPACE_URL, f"{doc_name}::{header_path}"))
            for local_idx, child in enumerate(child_chunks, start=1):
                global_chunk_counter += 1
                content_raw = f"{header_path}\n{child}".strip()
                results.append(
                    {
                        "doc_name": doc_name,
                        "section_id": section_id,
                        "section_level": sec.level,
                        "header_path": header_path,
                        "header_path_list": sec.path,
                        "chunk_id": local_idx,
                        "global_order": global_chunk_counter,
                        "content_raw": content_raw,
                        "parent_text_raw": parent_text_raw,
                    }
                )
    return results

# ---------------------------------------------------------------------
# Public Function 1: Index Titles
# ---------------------------------------------------------------------
def index_titles_to_es(
    pdf_files: Optional[list[str]] = None,
    *,
    es_client: Optional[Elasticsearch] = None,
    index_name: Optional[str] = None,
) -> int:
    """
    Đọc tiêu đề từ trang đầu PDF và index vào Elasticsearch.
    - pdf_files: nếu None sẽ auto lấy từ settings.input_dir
    - es_client: truyền sẵn nếu muốn tái sử dụng connection
    - index_name: mặc định settings.es_index_title
    Trả về: số lượng record đã push.
    """
    ensure_dirs()
    if pdf_files is None:
        pdf_files = list_pdfs(settings.input_dir)
    if not pdf_files:
        raise FileNotFoundError("Không tìm thấy PDF nào để index titles.")

    es = _get_es(es_client)
    index = index_name or settings.es_index_title

    _create_titles_index(es, index)

    headers = _extract_headers_from_pdfs(pdf_files)

    actions = []
    for item in headers:
        doc_name = item["name"]
        doc_name_infile = item["doc_name_infile"]
        title_raw = (item["header"] or "").strip()
        title_processed = _vn_segment_or_identity(title_raw.lower())

        doc_id = str(uuid.uuid5(uuid.NAMESPACE_URL, title_raw or doc_name))
        actions.append(
            {
                "_index": index,
                "_id": doc_id,
                "_source": {
                    "doc_name": doc_name,
                    "doc_name_infile": doc_name_infile,
                    "title": title_processed,
                    "title_raw": title_raw,
                },
            }
        )

    bulk_client = es.options(request_timeout=120, retry_on_timeout=True, max_retries=3)
    helpers.bulk(bulk_client, actions)
    es.indices.refresh(index=index)
    logger.info(f"Pushed {len(actions)} title docs into {index}")

# ---------------------------------------------------------------------
# Public Function 2: Index Keyword Chunks (BM25)
# ---------------------------------------------------------------------
async def process_chunk(c, index):
    doc_name = c["doc_name"]
    section_id = c["section_id"]
    chunk_id = c["chunk_id"]

    header_path_raw = c["header_path"]
    header_path_text = await _vn_segment_or_identity_async(header_path_raw)

    content_raw = _process_text_for_raw(c["content_raw"].strip())
    parent_text_raw = _process_text_for_raw(c["parent_text_raw"].strip())

    # tạo bản đã xử lý cho BM25: bỏ formula, và lọc bảng chỉ giữ lại text dài hơn 3 từ
    content_bm25 = _process_text_for_bm25(content_raw)
    parent_text_bm25 = _process_text_for_bm25(parent_text_raw)
    content = await _vn_segment_or_identity_async(content_bm25)
    parent_text = await _vn_segment_or_identity_async(parent_text_bm25)

    _id = str(uuid.uuid5(uuid.NAMESPACE_URL, f"{doc_name}::{section_id}::{chunk_id}"))
    return {
        "_index": index,
        "_id": _id,
        "_source": {
            "doc_name": doc_name,
            "section_id": section_id,
            "section_level": c["section_level"],
            "chunk_id": chunk_id,
            "global_order": c["global_order"],
            "header_path_raw": header_path_raw,
            "header_path_text": header_path_text,
            "content_raw": content_raw,
            "content": content,
            "parent_text_raw": parent_text_raw,
            "parent_text": parent_text,
        },
    }

async def index_keyword_chunks_to_es(
    md_path: Optional[str] = None,
    *,
    chunk_size: int = 300,
    overlap: int = 30,
    es_client: Optional[Elasticsearch] = None,
    index_name: Optional[str] = None,
) -> int:
    """
    Parse markdown chứa nhiều '# PublicXXX', chunk theo câu (BM25-friendly),
    kèm breadcrumb/parent_text; index vào Elasticsearch.
    - md_path: nếu None, lấy file .md đầu tiên trong settings.output_dir
    - chunk_size/overlap: ngân sách từ cho chunking
    - es_client: truyền sẵn nếu muốn tái sử dụng connection
    - index_name: mặc định settings.es_index_content
    Trả về: số lượng chunks đã push.
    """
    if md_path is None:
        answer_path = settings.output_dir / "answer.md"
        if not answer_path.exists():
            raise FileNotFoundError(f"Không tìm thấy file answer.md trong {settings.output_dir}")
        md_path = answer_path

    es = _get_es(es_client)
    index = index_name or settings.es_index_content

    _create_chunks_index(es, index)

    chunks = _parse_and_chunk_markdown_for_bm25(md_path, chunk_size=chunk_size, overlap=overlap)

    actions = []
    tasks = [process_chunk(c, index) for c in chunks]
    for coro in asyncio.as_completed(tasks):
        res = await coro
        actions.append(res)

    bulk_client = es.options(request_timeout=120, retry_on_timeout=True, max_retries=3)
    helpers.bulk(bulk_client, actions)
    es.indices.refresh(index=index)
    logger.info(f"Pushed {len(actions)} chunks into {index}")

def index_to_es() -> None:
    index_titles_to_es()
    asyncio.run(index_keyword_chunks_to_es())

if __name__ == "__main__":
    index_to_es()