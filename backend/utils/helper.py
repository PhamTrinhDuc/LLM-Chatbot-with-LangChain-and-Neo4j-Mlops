import sys
import os
import json
from datetime import timedelta
from contextvars import ContextVar
from loguru import logger

# ContextVar để lưu trace_id theo request
trace_id_ctx: ContextVar[str] = ContextVar("trace_id", default="none")

def json_serializer(record):
  """Chuyển log record thành JSON theo format mong muốn"""
  # Lấy trace_id từ context (an toàn)
  try:
      trace_id = trace_id_ctx.get()
  except LookupError:
      trace_id = "none"
  
  vietname_time = record['time'] + timedelta(hours=7)
  record["time"] = vietname_time.strftime("%Y-%m-%d %H:%M:%S")

  log_entry = {
      "timestamp": record["time"],
      "level": record["level"].name,
      "message": record["message"],
      "logger": record["name"],
      "function": record["function"],
      "line": record["line"],
      "trace_id": trace_id,
  }

  # Thêm các field từ `extra` (nếu có) vào body chính
  if record["extra"]:
      for key, value in record["extra"].items():
          if key != "trace_id":  # trace_id đã thêm rồi
              log_entry[key] = value

  return json.dumps(log_entry, ensure_ascii=False) + "\n"


def create_logger():
  logger.remove()
  env = os.getenv("ENV")

  if env == "production":
    def json_sink(message):
      # message.record chứa thông tin log record
      json_output = json_serializer(message.record)
      sys.stdout.write(json_output)
      sys.stdout.flush()
    
    logger.add(
      json_sink,  # Truyền function sink thay vì format
      level="INFO"
    )
    return logger
  else:
    logger.add(
        "../../logs/app.log",
        rotation="100 MB",
        retention="7 days",
        compression="zip",
        format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | "
                "<level>{level: <8}</level> | "
                "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - "
                "<level>{message}</level> - trace_id={extra[trace_id]}",
        level="DEBUG"
    )

    # Patch logger để tự động thêm trace_id từ context
    def add_trace_id(record):
        # Lấy trace_id từ context hiện tại
        try:
            trace_id = trace_id_ctx.get()
        except LookupError:
            trace_id = "none"
        
        record["extra"]["trace_id"] = trace_id

    patched_logger = logger.patch(add_trace_id)
    return patched_logger