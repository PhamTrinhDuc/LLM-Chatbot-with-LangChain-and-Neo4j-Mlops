# Monitoring Module - Outputs

output "namespace" {
  description = "Namespace where monitoring is deployed"
  value       = kubernetes_namespace.monitoring.metadata[0].name
}
