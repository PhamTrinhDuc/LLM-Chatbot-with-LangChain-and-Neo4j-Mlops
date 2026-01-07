# Ingress-Nginx Module - Variables

variable "kubeconfig_path" {
  type        = string
  description = "Path to kubeconfig file"
}

variable "namespace" {
  description = "Kubernetes namespace for Nginx Ingress Controller"
  type        = string
  default     = "ingress-nginx"
}

variable "environment" {
  description = "Environment: dev, staging, prod"
  type        = string
  validation {
    condition     = contains(["dev", "staging", "prod"], var.environment)
    error_message = "Must be dev, staging, or prod"
  }
}

variable "ingress_config" {
  description = "Ingress configuration"
  type = object({
    ingress_name   = optional(string, "plg-ingress")
    frontend_host  = string
    backend_host   = string
    frontend_port  = number
    backend_port   = number
    frontend_svc   = string
    backend_svc    = string
  })
}
