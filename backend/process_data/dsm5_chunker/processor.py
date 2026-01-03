import re

from utils import AppConfig, load_json, save_json


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


def split_by_sentence(content: str):
    sentences = re.split(AppConfig.SPLIT_SENTENCE_PATTERN, content)

    chunks = []
    curr_chunk = ""
    for sentence in sentences:
        curr_chunk = curr_chunk + " " + sentence if curr_chunk else sentence

        if len(curr_chunk) > AppConfig.MAX_CHUNK_SIZE:
            chunks.append(curr_chunk)
            curr_chunk = ""

    if curr_chunk:  # thêm nốt chunk cuối
        chunks.append(curr_chunk)
    return chunks


def merge_short_chunks(chunks: list[dict]):
    """
    Merge các chunk ngắn có cùng parent với nhau
    Tạo chunk mới được merge lấy thông tin  của chunk kế tiếp
    """
    chunk_merged = []
    index = 0
    while index < len(chunks):

        curr_chunk = chunks[index]

        if curr_chunk["metadata"].get("is_short", False) and index + 1 < len(chunks):
            next_chunk = chunks[index + 1]
            # nếu cùng parent
            if curr_chunk["parent_section_id"] == next_chunk["parent_section_id"]:
                combined_content = curr_chunk["content"] + "\n" + next_chunk["content"]

                if len(combined_content) < AppConfig.MAX_CHUNK_SIZE:
                    doc = {
                        **next_chunk,
                        "content": combined_content,
                        "title": curr_chunk["title"] + ". " + next_chunk["title"],
                        "metadata": {
                            **next_chunk["metadata"],
                            "char_count": len(combined_content),
                            "merged_from": [
                                curr_chunk["section_id"],
                                next_chunk["section_id"],
                            ],
                        },
                    }
                    chunk_merged.append(doc)
                    index += 2
                    continue

        chunk_merged.append(curr_chunk)
        index += 1

    return chunk_merged


def split_long_context(content: str) -> list[dict[str, any]]:
    """
    Split nội dung dài thành các chunks nhỏ hơn.
    Chiến lược:
    1. Ưu tiên split theo tiêu chí chẩn đoán (A., B., C., ...), fallback sang split sentences
    2. Nếu vẫn còn dài, split theo mục con (1., 2., 3., ...), fallback sang split sentences
    """
    sub_chunks = []

    # 1. split theo A., B., C.
    criteria_parts = re.split(AppConfig.CRITERIA_PATTERN, content)
    if len(criteria_parts) > 1:
        for part in criteria_parts:
            if not part.strip():
                continue
            part = part.replace(
                "\n", ""
            )  # loại bỏ kí tự \n trong \nA để pattern bắt đc
            # tìm label của tiêu chí (A, B, C)
            match = re.match(AppConfig.CRITERIA_LABEL_PATTERN, part)
            if match:
                label = match.group(1)
                sub_id = f"criteria_{label}"
                sub_title = f"Tiêu chí {label}"
            else:
                sub_id = ""
                sub_title = ""

            # nếu 1 phần vẫn còn quá dài thì split theo câu
            if len(part) > AppConfig.MAX_CHUNK_SIZE:
                sentences = split_by_sentence(content=part)
                for j, sentence in enumerate(sentences, start=1):
                    sub_chunks.append(
                        {
                            "sub_id": f"{sub_id}_p{j}",
                            "sub_title": f"{sub_title}_p{j}",
                            "content": sentence,
                        }
                    )
            # nếu 1 phần không quá dài thì append
            else:
                sub_chunks.append(
                    {"content": part, "sub_id": sub_id, "sub_title": sub_title}
                )

    else:
        # 2. split theo 1., 2., 3.
        sub_items = re.split(AppConfig.SUB_ITEM_PATTERN, content)
        if len(sub_items) > 1 and all(
            len(item) > 1 for item in sub_items
        ):  # kiểm tra xem có mục con không
            for item in sub_items:
                item = item.replace(
                    "\n", ""
                )  # loại bỏ kí tự \n trong \nA để pattern bắt đc
                # tìm label của item (1., 2., 3.)
                match = re.match(AppConfig.SUB_ITEM_PATTERN, item)
                if match:
                    label = match.group(1)
                    sub_id = f"item_{label}"
                    sub_title = f"Tiêu chí {label}"
                else:
                    sub_id = ""
                    sub_title = ""

                if len(item) > AppConfig.MAX_CHUNK_SIZE:  #
                    sentences = split_by_sentence(content=item)
                    for j, sentence in enumerate(sentences, start=1):
                        sub_chunks.append(
                            {
                                "sub_id": f"{sub_id}_p{j}",
                                "sub_title": f"{sub_title}_p{j}",
                                "content": sentence,
                            }
                        )
                else:
                    sub_chunks.append(
                        {"sub_id": sub_id, "sub_title": sub_title, "content": item}
                    )
            else:  # nếu không có mục con thì split theo câu
                sentences = split_by_sentence(content=content)
                for j, sentence in enumerate(sentences, start=1):
                    sub_chunks.append(
                        {
                            "sub_id": f"part_{j}",
                            "sub_title": f"Phần {j}",
                            "content": sentence,
                        }
                    )
    return sub_chunks


def process_chunks(chunks: list[dict]):
    """
    Load chunk đã parse.
    1. Split content cho mỗi chunk
    2. Merge các chunk ngắn cùng parent
    """
    chunks_results = []
    chunk_index_unique = 1

    for chunk in chunks:
        content = chunk["content"]
        title = chunk["title"]
        context_header = chunk["context_headers"]

        # split content
        if content and len(content) >= AppConfig.MAX_CHUNK_SIZE:
            sub_chunks = split_long_context(content=content)

            for sub_chunk in sub_chunks:
                sub_content = sub_chunk["content"]
                final_content = clean_text(
                    text=(
                        f"{title}\n{context_header}. {sub_content}"
                        if context_header
                        else sub_content
                    )
                )

                doc = {
                    **chunk,
                    "unique_id": chunk_index_unique,
                    "sub_id": sub_chunk["sub_id"],
                    "sub_title": sub_chunk["sub_title"],
                    "content": final_content,
                    "metadata": {
                        **chunk["metadata"],
                        "char_count": len(final_content),
                        "is_split": True,
                    },
                }
                chunks_results.append(doc)
                chunk_index_unique += 1

        # không split content
        else:
            final_content = clean_text(
                text=(
                    f"{title}\n{context_header}. {content}"
                    if context_header
                    else content
                )
            )
            is_short = len(final_content) < AppConfig.MIN_CHUNK_SIZE
            doc = {
                **chunk,
                "unique_id": chunk_index_unique,
                "content": final_content,
                "metadata": {
                    **chunk["metadata"],
                    "char_count": len(final_content),
                    "is_short": is_short,
                    "is_split": False,
                },
            }
            chunks_results.append(doc)
            chunk_index_unique += 1

    # merge các chunk ngắn lại
    chunks_results = merge_short_chunks(chunks=chunks_results)

    # Set lại index sau khi merge
    for i, chunk in enumerate(chunks_results, start=1):
        chunk["unique_id"] = i

    return chunks_results


if __name__ == "__main__":
    chunks = load_json(path=AppConfig.DSM5_CHUNKS_PATH)
    chunks = process_chunks(chunks=chunks)
    save_json(data=chunks, output_path=AppConfig.DSM5_CHUNKS_PATH)

    # content = None
    # for chunk in chunks:
    #   if chunk['section_id'] == '3.5':
    #     content = chunk['content']

    # sub_chunks = split_by_sentence(content=content)
    # for chunk in sub_chunks:
    #   print(chunk)
    #   print("="*100)
