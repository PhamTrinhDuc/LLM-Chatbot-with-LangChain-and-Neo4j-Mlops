import os
import sys
sys.path.append(os.path.join(os.path.dirname(__file__), ".."))
import socket
from fastapi import FastAPI
from opentelemetry.exporter.jaeger.thrift import JaegerExporter
from opentelemetry.sdk.resources import Resource, SERVICE_NAME
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor, ConsoleSpanExporter
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry import trace
from utils import logger

def _is_jaeger_available(host: str, port: int, timeout: int=2): 
  """Check if Jaeger agent is reachable"""
  try: 
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    socket.timeout(timeout)
    socket.getaddrinfo(host, port, socket.AF_INET, socket.SOCK_DGRAM)
    sock.close()
    return True
  except (socket.gaierror, socket.timeout, OSError) as e: 
    logger.warning(f"⚠️  Jaeger not available at {host}:{port} - {e}")
    return False

def setup_tracing(app: FastAPI, 
                  service_name: str = "llm-chatbot-langchain", 
                  jaeger_host: str="localhost", 
                  jaeger_port: int=6831): 
  
  logger.info(f"🚀 Setting up tracing for service: {service_name}")

  if not _is_jaeger_available(host=jaeger_host, port=jaeger_port): 
    logger.warning("⚠️  Jaeger unavailable - Tracing disabled")
    return

  # 1. Jaeger exporter
  try:
    jaeger_exporter = JaegerExporter(
      agent_host_name=jaeger_host, 
      agent_port=jaeger_port
    )
    
    # Console exporter để debug (in ra console)
    # console_exporter = ConsoleSpanExporter()

    # 2. Trace provider + resource
    resource = Resource(attributes={SERVICE_NAME: service_name})
    provider = TracerProvider(resource=resource)
    
    # 3. Thêm CẢ HAI processors (Jaeger + Console)
    provider.add_span_processor(BatchSpanProcessor(jaeger_exporter))
    # provider.add_span_processor(BatchSpanProcessor(console_exporter))  # Debug
    
    # 4. Đăng ký provider toàn cục
    trace.set_tracer_provider(provider)  

    # 5. Tự động instrument FastAPI app
    FastAPIInstrumentor.instrument_app(app)
    logger.info(f"✅ Tracing setup completed for {service_name}")
  except Exception as e:
    logger.error(f"❌ Error setting up tracing: {e}")