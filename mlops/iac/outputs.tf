output "ingress_nginx" {
  description = "Ingress Nginx outputs"
  value       = module.ingress_nginx
}

output "logging" {
  description = "Logging stack outputs"
  value       = module.logging
}

output "monitoring" {
  description = "Monitoring stack outputs"
  value       = module.monitoring
}

output "jaeger" {
  description = "Jaeger (distributed tracing) outputs"
  value       = module.jaeger
}