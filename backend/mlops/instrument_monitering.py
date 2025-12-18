from opentelemetry import metrics
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader
from opentelemetry.exporter.prometheus import PrometheusMetricReader
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from prometheus_client import make_asgi_app
import time
from functools import wraps
from typing import Callable

# ============================================================
# OpenTelemetry Setup
# ============================================================

# Tạo Prometheus exporter
prometheus_reader = PrometheusMetricReader()

# Tạo MeterProvider với Prometheus exporter
meter_provider = MeterProvider(metric_readers=[prometheus_reader])
metrics.set_meter_provider(meter_provider)

# Tạo meter cho app (như một namespace)
meter = metrics.get_meter(
    name="chatbot.metrics",
    version="1.0.0"
)

# ============================================================
# Custom Metrics
# ============================================================

# Counter - Đếm requests
chat_requests_total = meter.create_counter(
    name="chat_requests_total",
    description="Total number of chat requests",
    unit="1"
)

# Histogram - Đo latency
chat_request_duration = meter.create_histogram(
    name="chat_request_duration_seconds",
    description="Duration of chat requests in seconds",
    unit="s"
)

# Counter - Đếm tokens
chat_token_total = meter.create_counter(
    name="chat_token_total",
    description="Total number of tokens processed in chat",
    unit="1"
)

# UpDownCounter - Active sessions (có thể tăng/giảm)
active_chat_sessions = meter.create_up_down_counter(
    name="active_chat_sessions",
    description="Number of active chat sessions",
    unit="1"
)

# Counter - Tool calls
agent_tool_calls = meter.create_counter(
    name="agent_tool_calls_total",
    description="Total number of agent tool calls",
    unit="1"
)

def monitor_endpoint(endpoint_name: str):
  """
  Decorator để theo dõi các endpoint cụ thể trong ứng dụng.
  
  Sử dụng OpenTelemetry để track:
  - Request count (success/error)
  - Request duration (latency)
  - Active sessions
  
  Usage:
      @monitor_endpoint("chat")
      async def chat_endpoint(...):
          ...
  """

  def decorator(func: Callable): 
    @wraps(func)
    async def wrapper(*args, **kwargs): 
      start_time = time.time()
      
      # Attributes (labels) cho metrics
      attributes = {"endpoint": endpoint_name}
      
      # Tăng active sessions
      active_chat_sessions.add(1, attributes)

      try: 
        # Execute function
        result = await func(*args, **kwargs)
        
        # Calculate duration
        duration = time.time() - start_time
        
        # Record metrics với attributes
        chat_request_duration.record(duration, attributes)
        chat_requests_total.add(1, {**attributes, "status": "success"})
        
        return result
        
      except Exception as e:
        # Record error
        chat_requests_total.add(1, {**attributes, "status": "error"})
        raise e
        
      finally: 
        # Giảm active sessions
        active_chat_sessions.add(-1, attributes)
        
    return wrapper
  return decorator

def track_tool_usage(result: dict): 
  """Track agent tool calls từ result."""
  for step in result.get("intermediate_steps", []): 
    if hasattr(step, "tool"): 
      agent_tool_calls.add(1, {"tool_name": step.tool})

def track_tokens_usage(result: dict, endpoint: str): 
  """Track token usage từ LLM response."""
  if "token_usage" in result:
    # Input tokens
    input_tokens = result["token_usage"].get("input", 0)
    if input_tokens > 0:
      chat_token_total.add(
        input_tokens, 
        {"endpoint": endpoint, "type": "input"}
      )
    
    # Output tokens
    output_tokens = result["token_usage"].get("output", 0)
    if output_tokens > 0:
      chat_token_total.add(
        output_tokens,
        {"endpoint": endpoint, "type": "output"}
      )

def setup_metrics(app): 
  """
  Thiết lập OpenTelemetry instrumentation cho FastAPI app.
  
  Features:
  - Auto-instrument tất cả HTTP requests (latency, status codes, etc.)
  - Expose /metrics endpoint cho Prometheus
  - Custom metrics đã define ở trên
  
  Gọi hàm này khi khởi tạo app:
      app = FastAPI()
      setup_metrics(app)
  """
  
  # Auto-instrument FastAPI với OpenTelemetry
  # Tự động track: request count, duration, status codes
  FastAPIInstrumentor.instrument_app(
    app,
    excluded_urls="/metrics,/health"  # Không track các endpoints này
  )
  
  # Mount Prometheus metrics endpoint
  # Prometheus sẽ scrape endpoint này để lấy metrics
  metrics_app = make_asgi_app()
  app.mount("/metrics", metrics_app)
  
  return app