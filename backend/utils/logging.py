# logger.py
import os
import sys
import json
from datetime import timedelta, datetime
from contextvars import ContextVar
from loguru import logger as _logger
from config import AppConfig

# === 1. ContextVar — chỉ KHAI BÁO 1 LẦN ở global scope ===
trace_id_ctx: ContextVar[str] = ContextVar("trace_id", default="none")


# === 2. Patch function — inject trace_id vào extra (an toàn trong async) ===
def _add_trace_id(record):
    try:
        trace_id = trace_id_ctx.get()
    except LookupError:
        trace_id = "none"
    record["extra"]["trace_id"] = trace_id


# === 3. JSON serializer — KHÔNG dùng contextvar, chỉ dùng record["extra"] ===
def _json_serializer(record):
    # Convert time to UTC+7 (Vietnam)
    vietnam_time = record["time"].replace(tzinfo=None) + timedelta(hours=7)
    timestamp = vietnam_time.strftime("%Y-%m-%d %H:%M:%S")

    log_entry = {
        "timestamp": timestamp,
        "level": record["level"].name,
        "message": record["message"],
        "logger": record["name"],
        "function": record["function"],
        "line": record["line"],
        "trace_id": record["extra"].get("trace_id", "none"),
    }

    # Thêm các field từ extra (e.g., model, tokens, user_id...)
    for key, value in record["extra"].items():
        if key != "trace_id":
            # Đảm bảo giá trị JSON-serializable
            if isinstance(value, (datetime,)):
                value = value.isoformat()
            elif isinstance(value, (set, tuple)):
                value = list(value)
            log_entry[key] = value

    return json.dumps(log_entry, ensure_ascii=False) + "\n"


# === 4. Setup logger — chỉ chạy 1 lần ===
def _setup_logger():
    _logger.remove()  # Xóa default handler

    # Lấy config từ env (hoặc hardcode nếu chưa có AppConfig)
    env = AppConfig.ENV_LOG
    log_dir = AppConfig.LOG_DIR
    os.makedirs(os.path.dirname(log_dir), exist_ok=True)

    if env == "production":
        def json_sink(message):
            try:
                output = _json_serializer(message.record)
                sys.stdout.write(output)
                sys.stdout.flush()
            except Exception as e:
                # Fallback: ghi lỗi log vào stderr (tránh silent fail)
                sys.stderr.write(f"LOG_SERIALIZE_ERROR: {e}\n")
                sys.stderr.flush()

        _logger.add(
            json_sink,
            level="INFO",
            enqueue=True,        # Bắt buộc cho async production
            backtrace=False,     # Tránh lộ stack trace nhạy cảm
            diagnose=False,
        )
    else:
        # Dev mode: ghi file + màu mè
        _logger.add(
            log_dir,
            rotation="50 MB",
            retention="3 days",
            compression="zip",
            format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | "
                   "<level>{level: <8}</level> | "
                   "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - "
                   "<level>{message}</level> - trace_id={extra[trace_id]}",
            level="DEBUG",
            enqueue=False,
        )

    # Patch 1 lần duy nhất — đảm bảo trace_id được inject trước khi vào queue/thread
    return _logger.patch(_add_trace_id)


# === 5. Export instance duy nhất ===
logger = _setup_logger()