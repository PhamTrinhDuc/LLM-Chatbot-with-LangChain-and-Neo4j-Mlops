# Jaeger Module - Variables

variable "kubeconfig_path" {
  type        = string
  description = "Path to kubeconfig file"
}

variable "namespace" {
  description = "Kubernetes namespace for Jaeger"
  type        = string
  default     = "jaeger"
}

variable "environment" {
  description = "Environment: dev, staging, prod"
  type        = string
  validation {
    condition     = contains(["dev", "staging", "prod"], var.environment)
    error_message = "Must be dev, staging, or prod"
  }
}
