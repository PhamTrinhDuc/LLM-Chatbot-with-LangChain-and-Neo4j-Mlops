environment = "dev"

ingress_nginx_namespace = "ingress-nginx"
logging_namespace       = "loki-stack"

ingress_config = {
  ingress_name   = "plg-ingress"
  frontend_host  = "chatbot-medical.local"
  backend_host   = "api.chatbot-medical.local"
  frontend_port  = 8501
  backend_port   = 8000
  frontend_svc   = "chatbot-frontend"
  backend_svc    = "chatbot-backend"
}
