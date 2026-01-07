# Jaeger Module - Outputs

output "namespace" {
  description = "Namespace where Jaeger is deployed"
  value       = kubernetes_namespace.jaeger.metadata[0].name
}
