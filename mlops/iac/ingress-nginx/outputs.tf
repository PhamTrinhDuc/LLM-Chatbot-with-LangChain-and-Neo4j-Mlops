output "ingress_namespace" {
  description = "Kubernetes namespace for ingress"
  value       = kubernetes_namespace.ingress.metadata[0].name
}

output "helm_release_name" {
  description = "Helm release name"
  value       = helm_release.nginx_ingress.name
}

output "ingress_name" {
  description = "Ingress resource name"
  value       = kubernetes_manifest.ingress_nginx.manifest.metadata.name
}

# terraform output: hiển thị kết quả sau khi terraform apply