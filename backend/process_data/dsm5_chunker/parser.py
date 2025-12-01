import os
import sys
sys.path.append(os.path.join(os.path.dirname(__file__), "..", ".."))
import re
import json
import pdfplumber
from typing import Union
from utils import AppConfig, save_json, load_json

# ===================================
# HELPER FUNCTION
# ===================================

def get_section_header(line: str) -> Union[None, str]: 
  """
  Kiểm tra dòng đó là section thì lấy cấp mục của section đó
  """
  matched = re.compile(pattern=AppConfig.SECTION_PATTERN).match(line)
  if not matched: 
    return None
  else: 
    # example matched: <re.Match object; span=(0, 7), match='1.1.1 C'>
    return matched.group(1) # => 1.1.1


def get_level_section(section_id: str): 
  """
  Lấy ra level của section và chi tiết các cấp 
  """
  return len(section_id.split(".")), section_id.split(".")


def is_footer_line(line: str): 
  """
  Loại bỏ dòng dưới footer không cần thiết
  """
  # example: Chỉ sử dụng tài liệu vào mục đích học tập và nghiên cứu => TRUE
  matched = re.compile(AppConfig.PAGE_FOOTER_PATTERN).match(line)
  return matched


def smart_join_lines(lines: list[str]): 
  """
  Ngắt đoạn: 
  - Dòng trước kết thúc bằng ".!?..
  - Dòng sau bắt đầu bằng A, B, C, 1.1, 2.2
  Ngược lại thì nối tiếp
  """
  if not lines: 
    return ""
  
  # Lọc bỏ footer trang
  filtered_lines = [l for l in lines if not is_footer_line(l.strip())]
  if not filtered_lines:
      return ""
  
  paragraphs = []
  current_para = filtered_lines[0]

  for i in range(1, len(filtered_lines)): 
      prev_line = current_para.strip()
      curr_line = filtered_lines[i].strip()

      # Nếu dòng trước kết thúc bằng dấu kết thúc => ngắt đoạn
      if re.search(r'[.!?…:)]$', prev_line):
          paragraphs.append(current_para)
          current_para = curr_line

      # Nếu dòng sau bắt đầu bằng tiêu chí => ngắt (A., B., 1., 2., v.v.)
      elif re.match(r'^[A-Z]\.\s', curr_line) or re.match(r'^\d+\.\s', curr_line):
          paragraphs.append(current_para)
          current_para = curr_line

      else:
          current_para += ' ' + curr_line

  paragraphs.append(current_para)
  return "\n".join(paragraphs)


def build_context_headers(section_queue: dict) -> dict[str, list[str]]: 
  """
  Build toàn bộ cây cấp bậc cho 1 cấp bậc cụ thể
  Args: 
    section_queue: dict chứa {cấp mục: title cấp mục}
  Return: 
    {cấp mục cụ thể: [toàn bộ cấp mục]}
  Example: 
    {"1.2.1": [1.2.1 abc > 1.2 def > 1 ghk ]}
  """
  context_headers = {} # lưu context_header cho từng cấp (1.1: 1.1 > 1)
  for key, value in section_queue.items(): 
    level_number, level_details = get_level_section(section_id=key) # 3, [1, 1, 1]
    if level_number <=1 : 
      context_headers.update({key: f"{[section_queue[key]]}"})
    else: 
      context_header = []
      for i in range(len(level_details), 0, -1): 
        level = '.'.join(level_details[:i]) # 1.1.1, 1.1, 1
        context_header.append(section_queue[level]) 
      context_header = " > ".join(context_header)
      context_headers.update({key: f"[{context_header}]"})
  return context_headers

# ===================================
# MAIN FUNCTION 
# ===================================

def parse_pdf_to_chunk(pdf_path: str) -> list[dict]: 
  """
  Parses a PDF file and chunks its content into manageable pieces.

  Args:
      pdf_path (str): The path to the PDF file.
  Returns:
      list[dict]: A list of dictionaries, each containing a chunk of text and its metadata.
  """

  with pdfplumber.open(path_or_fp=pdf_path) as pdf: 
    chunks = [] # lưu kết quả các chunk
    section_queue = {} # lưu list các section => lấy ra cha của section hiện tại
    buffer_lines = [] # lưu các phần nội dung bên trong các cấp
    count_chunk = 0 # đếm chunk
    curr_chunk = None # lưu chunk hiện tại qua các page

    for page_num, page_content in enumerate(pdf.pages, start=1): 

      text = page_content.extract_text()
      lines = text.split("\n") # tách thành các dòng

      for line in lines: # xử lý từng dòng 
        if not line.strip(): # bỏ dòng trống
          continue

        if is_footer_line(line=line): # bỏ qua dòng footer
          continue

        section_id = get_section_header(line=line)
        if section_id:
          # 1. Thêm chunk 
          count_chunk += 1 
          if curr_chunk: # tránh lần đầu curr chunk bị None
            if buffer_lines: 
              curr_chunk['content'] = smart_join_lines(buffer_lines) # thêm nội dung của chunk hiện tại
            chunks.append(curr_chunk) # thêm chunk hiện tại vào list
            buffer_lines = [] # set lại buffer_lines cho các chunk kế tiếp

          # 2. Tạo parent chunk cho chunk hiện tại
          # 2.1 lấy section_parent từ section hiện tại
          level_number, _ = get_level_section(section_id) 
          section_parent_id = None
          section_parent_title = None
          for prev_section in reversed(section_queue.keys()):
            prev_level_number, _ = get_level_section(prev_section)
            if prev_level_number == level_number - 1: # nếu bằng cấp hiện tại trừ -1 => cha
              section_parent_id = prev_section
              section_parent_title = section_queue.get(section_parent_id)
              break
          
          section_queue[section_id] = line # tìm section parent trước rồi mới thêm section hiện tại vào
          
          # 3 Khởi tạo chunk mới làm curr chunk
          curr_chunk = {
            "chunk_idx": f"chunk-{count_chunk}",
            "section_id": section_id,
            "section_level": level_number,
            "title": line,
            "parent_section_id": section_parent_id, 
            "parent_section_title": section_parent_title,
            "context_headers": build_context_headers(section_queue=section_queue)[section_id],
            "content": None, # update khi gặp 1 section mới (hết 1 chunk)
            "metadata": {
              "page_start": page_num,
              "source": pdf_path, 
            }
          }      
          
        else: 
          buffer_lines.append(line) # không phải header thì là nội dung => thêm vào buffer

      # if page_num == 10: 
      #   break

    # Thêm chunk cuối cùng vào list 
    if curr_chunk: 
      curr_chunk['content'] = smart_join_lines(buffer_lines)
      chunks.append(curr_chunk)
    
  return chunks
  # return chunks, section_queue


if __name__ == "__main__": 
  chunks = parse_pdf_to_chunk(pdf_path=AppConfig.DSM5_PATH)
  save_json(data=chunks, output_path=AppConfig.DSM5_CHUNKS_PATH)
  # output_section_queue = "section_queue.json"
  # save_json(data=section_queue, output_path=output_section_queue)
  # section_queue = load_json(path="section_queue.json")
  # context_headers = build_context_headers(section_queue=section_queue)
  # print(context_headers)