from fastapi import FastAPI
from opentelemetry.exporter.jaeger.thrift import JaegerExporter
from opentelemetry.sdk.resources import Resource, SERVICE_NAME
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor, ConsoleSpanExporter
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry import trace
import logging

logging.basicConfig(level=logging.DEBUG)

def setup_tracing(app: FastAPI, 
                  service_name: str = "llm-chatbot-langchain", 
                  jaeger_host: str="localhost", 
                  jaeger_port: int=6831): 
  
  print(f"🚀 Setting up tracing for service: {service_name}")
  print(f"📡 Jaeger endpoint: {jaeger_host}:{jaeger_port}")

  # 1. Jaeger exporter
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
  print(f"✅ Tracing setup completed for {service_name}")