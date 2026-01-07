output "ingress_nginx" {
  description = "Ingress Nginx outputs"
  value       = module.ingress_nginx
}

output "logging" {
  description = "Logging stack outputs"
  value       = module.logging
}
