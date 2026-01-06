enviroment = "dev"

ingress_config = {
  frontend_host = "chatbot-medical.local"
  backend_host  = "api.chatbot-medical.local"
  frontend_port = 8501
  backend_port  = 8000
  frontend_svc  = "chatbot-frontend"
  backend_svc   = "chatbot-backend"
}