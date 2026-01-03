# logger.py
import json
import os
import sys
from contextvars import ContextVar
from datetime import datetime, timedelta

from loguru import logger as _logger

from .config import AppConfig

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
        "@timestamp": timestamp,
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
    # Patch ngay sau khi remove để đảm bảo mọi log đều có trace_id
    patched_logger = _logger.patch(_add_trace_id)

    env = AppConfig.ENV_LOG
    log_dir = AppConfig.LOG_DIR
    os.makedirs(os.path.dirname(log_dir), exist_ok=True)
    print(
        f"[LOGGER SETUP] ENV_LOG={env}, LOG_DIR={log_dir}", file=sys.stderr, flush=True
    )

    if env == "production":

        def json_sink(message):
            try:
                output = _json_serializer(message.record)
                sys.stdout.write(output + "\n")
                sys.stdout.flush()
            except Exception as e:
                # Fallback: ghi lỗi log vào stderr (tránh silent fail)
                sys.stderr.write(f"LOG_SERIALIZE_ERROR: {e}\n")
                sys.stderr.flush()

        patched_logger.add(
            json_sink,
            level="INFO",
            enqueue=False,  # tắt
            backtrace=False,  # Tránh lộ stack trace nhạy cảm
            diagnose=False,
        )
    else:
        # Sử dụng custom format function để an toàn hơn
        def dev_format(record):
            trace_id = record["extra"].get("trace_id", "none")
            return (
                "<green>{time:YYYY-MM-DD HH:mm:ss}</green> | "
                "<level>{level: <8}</level> | "
                "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - "
                f"<level>{{message}}</level> - trace_id={trace_id}\n"
            )

        patched_logger.add(
            log_dir,
            rotation="50 MB",
            retention="3 days",
            compression="zip",
            format=dev_format,
            level="DEBUG",
            enqueue=False,
        )

    return patched_logger


# === 5. Export instance duy nhất ===
logger = _setup_logger()

# === 6. Export trace_id_ctx để có thể set từ middleware ===
__all__ = ["logger", "trace_id_ctx"]
