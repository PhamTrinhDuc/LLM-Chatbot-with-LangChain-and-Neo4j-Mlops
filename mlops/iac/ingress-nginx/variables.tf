variable "kubeconfig_path" {
  type        = string
  default     = "~/.kube/config"
  description = "Path to kubeconfig file"
}

variable "namespace" {
  description = "Kubenetes namespace for Nginx"
  type = "string"
  default = "ingress-nginx"
}

variable "environment" {
  description = "Environment: dev, staging, prod"
  type = string
  validation {
    condition     = contains(["dev", "staging", "prod"], var.environment)
    error_message = "Must be dev, staging, or prod"
  }
}

variable "ingress_config" {
  description = "Ingress configuration"
  type = object({
    frontend_host = string
    backend_host = string 
    frontend_port = string
    backend_port = number 
    frontend_svc = number
    backend_svc = string
  })
}