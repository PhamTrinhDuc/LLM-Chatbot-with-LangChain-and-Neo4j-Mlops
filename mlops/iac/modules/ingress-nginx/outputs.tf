# Ingress-Nginx Module - Outputs

output "namespace" {
  description = "Namespace where Ingress Nginx is deployed"
  value       = kubernetes_namespace.ingress.metadata[0].name
}

output "ingress_class_name" {
  description = "Ingress class name"
  value       = "nginx"
}

output "helm_release_name" {
  description = "Helm release name"
  value       = helm_release.nginx_ingress.metadata[0].name
}
