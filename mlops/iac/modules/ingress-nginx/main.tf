# Ingress-Nginx Module - Main configuration

# 1. Create namespace
resource "kubernetes_namespace" "ingress" {
  metadata {
    name = var.namespace
    labels = {
      "app.kubernetes.io/name" = "ingress-nginx"
      environment              = var.environment
    }
  }
}

# 2. Deploy Nginx Ingress Controller via Helm
resource "helm_release" "nginx_ingress" {
  name       = "ingress-nginx"
  repository = "https://kubernetes.github.io/ingress-nginx"
  chart      = "ingress-nginx"
  namespace  = kubernetes_namespace.ingress.metadata[0].name

  set {
    name  = "controller.service.type"
    value = var.environment == "prod" ? "LoadBalancer" : "NodePort"
  }

  set {
    name  = "controller.resources.limits.cpu"
    value = var.environment == "prod" ? "500m" : "200m"
  }
}

# 3. Apply Ingress Rule from YAML template
resource "kubernetes_manifest" "ingress_rule" {
  manifest = yamldecode(templatefile("${path.module}/ingress-nginx.yaml", {
    ingress_name    = var.ingress_config.ingress_name
    frontend_host   = var.ingress_config.frontend_host
    backend_host    = var.ingress_config.backend_host
    frontend_port   = var.ingress_config.frontend_port
    backend_port    = var.ingress_config.backend_port
    frontend_svc    = var.ingress_config.frontend_svc
    backend_svc     = var.ingress_config.backend_svc
  }))

  depends_on = [helm_release.nginx_ingress]
}
