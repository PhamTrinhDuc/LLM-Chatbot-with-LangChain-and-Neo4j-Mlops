# Logging Module - Outputs

output "namespace" {
  description = "Namespace where PLG stack is deployed"
  value       = kubernetes_namespace.loki_stack.metadata[0].name
}

output "helm_release_name" {
  description = "Helm release name"
  value       = helm_release.loki_stack.metadata[0].name
}

output "grafana_service" {
  description = "Grafana service name"
  value       = "${helm_release.loki_stack.metadata[0].name}-grafana"
}

output "prometheus_service" {
  description = "Prometheus service name"
  value       = "${helm_release.loki_stack.metadata[0].name}-prometheus-server"
}

output "loki_service" {
  description = "Loki service name"
  value       = "${helm_release.loki_stack.metadata[0].name}"
}
