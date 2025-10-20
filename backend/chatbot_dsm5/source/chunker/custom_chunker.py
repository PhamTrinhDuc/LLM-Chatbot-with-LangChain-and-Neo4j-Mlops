import pdfplumber
import re
import os
from langchain.schema import Document

def smart_join_lines(lines: list[str]) -> str: 
    """
    Ghép các dòng PDF thành các đoạn logic:
    - Không ghép nếu dòng trước kết thúc bằng dấu câu (. ! ? : ) …
    - Không ghép nếu dòng sau bắt đầu bằng tiêu chí (A., 1., v.v.)
    - Ngược lại: ghép với khoảng trắng
    """
    # print("Start joining with lines: ", lines)

    paragraphs = []
    current_para = lines[0]

    for i in range(1, len(lines)): 
        prev_line = current_para.strip()
        curr_line = lines[i].strip()

        # Nếu dòng trước kết thúc bằng dấu kết thúc => ngắt đoạn
        if re.search(r'[.!?…:)]$', prev_line.strip()):
            paragraphs.append(current_para)
            current_para = curr_line

        # Nếu dòng sau bắt đầu bằng tiêu chí => ngắt (A., B., 1., 2., v.v.)
        elif re.match(r'^[A-Z0-9]\.', curr_line.strip()):
            paragraphs.append(current_para)
            current_para = curr_line

        else: # ngược lại thì join 
            current_para += ' ' + curr_line

    paragraphs.append(current_para)
    return "\n".join(paragraphs)

def add_parent_title(chunks: list[dict]): 
    chunk_map = {c["section_id"]: c for c in chunks} # {'1.1': chunk_of_1.1}
    for chunk in chunks: 
        pid = chunk.get("parent_id") # lấy parent của chunk hiện tại
        if pid and pid in chunk_map: 
            chunk['parent_title'] = chunk_map[pid]['title'] # thêm title của chunk parent vừa lấy vào chunk hiện tại
        else: 
            chunk['parent_title'] = None

    return chunks

def clean_text(text: str) -> str:
        """
        Clean and normalize text.
        
        Args:
            text: Raw text to clean
            
        Returns:
            Cleaned and normalized text
        """
        if not text or not isinstance(text, str):
            return ""
            
        # Remove extra whitespace
        text = re.sub(r'\s+', ' ', text)
        # Remove special characters but keep Vietnamese
        text = re.sub(r'[^\w\s\u00C0-\u1EF9.,;:!?()-]', '', text)
        return text.strip().lower()

def convert_to_documents(chunks: list[dict]) -> list[Document]:
  """Chuyển đổi chunks thành LangChain Documents."""
  documents = []
  
  for i, chunk in enumerate(chunks, 1):
      content = f"{chunk['title']}\n{chunk['text']}"
      cleaned_content = clean_text(content)
      
      metadata = {
          "section_id": chunk['section_id'],
          "level": chunk['level'],
          "parent_id": chunk.get('parent_id'),
          "parent_title": chunk.get('parent_title'),
          "page_start": chunk['page_start'],
          "source": chunk['source'],
          "document_index": i,
          "original_len": len(content),
          "cleaned_len": len(cleaned_content)
      }
      
      doc = Document(page_content=cleaned_content, metadata=metadata)
      documents.append(doc)
  
  return documents

def extract_dsm_chunk_hiearchical(pdf_path) -> list[dict]:
    """
    Trích xuất và chunk tài liệu DSM-5 tiếng Việt theo cấu trúc phân cấp.
    Mỗi chunk = 1 rối loạn (ví dụ: 14.2.6), bao gồm toàn bộ tiêu chí.
    """

    chunks = []
    current_chunk = None
    buffer_lines = [] # Lưu các dòng nội dung của 1 tiêu chí (các nội dung xuyên suốt các trang nên cần lưu qua các trang)

    section_pattern = re.compile(r'^(\d+(?:\.\d+)*)\s+[A-ZÀ-Ỹ]')
    # section_pattern = re.compile(r'^(\d+(?:\.\d+)*)\s+(.+)')

    last_section_at_level = {} # Lưu mục gần nhất ở mỗi cấp độ để truy vấn lại cha của 1 cấp độ: {1: "1", 2: "1.1", 3: "1.1.1", ...}

    with pdfplumber.open(pdf_path) as pdf: 
      for page_num, page in enumerate(pdf.pages, 1): 
        text = page.extract_text(x_tolerance=1, y_tolerance=1)
        if not text or not text.strip(): continue

        lines = text.split('\n')
                    
        for line in lines: 
          line = line.strip()
          if not line: continue

          matched = section_pattern.match(line) # kiểm tra xem dòng đó có phải tiêu đề không
          if matched: 
            # kiểm tra xem trước đó có chunk không ? 
            if current_chunk is not None:
              if buffer_lines: 
                  current_chunk['text'] = smart_join_lines(buffer_lines)
              chunks.append(current_chunk)
              buffer_lines = []

            section_id = matched.group(1) # match dạng: level: content
            level = len(section_id.split('.')) # 1.1 => cấp 2, 1.1.1 => cấp 3 

            last_section_at_level[level] = section_id # {2: '1.1', 3: '1.1.1'}

            # keys_to_remove = [k for k in last_section_at_level if k > level]
            # for k in keys_to_remove:
            #     del last_section_at_level[k]

            parent_id = None
            for l in range(level-1, 0, -1): # duyệt ngược lại các level phía trước
              if l in last_section_at_level: # nếu level đó ở trong last_section thì nó là cha của level hiện tại luôn
                parent_id = last_section_at_level[l]
                break

            current_chunk = {
              "section_id": section_id, 
              "level": level,
              "parent_id": parent_id,
              "title": line, 
              "text": "", # sẽ được thêm vào khi buffer đã có đủ nội dung
              "page_start": page_num, 
              'source':  os.path.abspath(pdf_path)
            }

          else: # không phải là title thì đưa hết nội dung vào buffer
            if current_chunk is not None:
              buffer_lines.append(line)

        # print("lines:", lines)
        # print("buffer:", buffer_lines)


      # xử lý cho phần title cuối cùng
      if current_chunk is not None:
        current_chunk['text'] = smart_join_lines(buffer_lines)
        chunks.append(current_chunk)

      chunks = add_parent_title(chunks=chunks)
      documents = convert_to_documents(chunks=chunks)

    return documents

if __name__ == "__main__": 
    PDF_PATH = "/home/ducpham/workspace/LLM-Chatbot-with-LangChain-and-Neo4j/data/dsm-5-cac-tieu-chuan-chan-doan.pdf"

    chunks = extract_dsm_chunk_hiearchical(PDF_PATH)
    for chunk in chunks[:10]: 
        print(chunk)

    # import json
    # with open("dsm5_chunks.json", "w", encoding="utf-8") as f:
    #     json.dump(chunks, f, ensure_ascii=False, indent=2)


    # print(f"Đã trích xuất {len(chunks)} chunks")
    # ex = chunks[0]
    # print(f"ID: {ex['section_id']}")
    # print(f"Tiêu đề: {ex['title']}")
    # print(f"Cha: {ex.get('parent_title', 'Không có')}")
    # print(f"Nội dung (100 ký tự đầu): {ex['text'][:100]}...")
    # print(f"Trang bắt đầu: {ex['page_start']}")
