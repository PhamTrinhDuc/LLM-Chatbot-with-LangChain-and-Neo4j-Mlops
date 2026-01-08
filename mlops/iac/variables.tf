variable "kubeconfig_path" {
  type        = string
  default     = "~/.kube/config"
  description = "Path to kubeconfig file"
}

variable "environment" {
  description = "Environment: dev, staging, prod"
  type        = string
  validation {
    condition     = contains(["dev", "staging", "prod"], var.environment)
    error_message = "Must be dev, staging, or prod"
  }
}

# Ingress-Nginx specific variables
variable "ingress_nginx_namespace" {
  description = "Kubernetes namespace for Nginx Ingress Controller"
  type        = string
  default     = "ingress-nginx"
}

# Logging (PLG Stack) specific variables
variable "logging_namespace" {
  description = "Kubernetes namespace for Logging Stack (Loki, Prometheus, Grafana)"
  type        = string
  default     = "loki-stack"
}

# Monitoring specific variables (for future use)
variable "monitoring_namespace" {
  description = "Kubernetes namespace for Monitoring"
  type        = string
  default     = "monitoring"
}

# Jaeger specific variables (for future use)
variable "jaeger_namespace" {
  description = "Kubernetes namespace for Jaeger"
  type        = string
  default     = "jaeger"
}


variable "ingress_config" {
  description = "Ingress configuration"
  type = object({
    app_namespace  = string
    jaeger_namespace = string
    
    frontend_host  = string
    backend_host   = string
    jaeger_host    = string
    
    frontend_port  = number
    backend_port   = number
    jaeger_port    = number
    
    frontend_svc   = string
    backend_svc    = string
    jaeger_svc     = string
  })
}