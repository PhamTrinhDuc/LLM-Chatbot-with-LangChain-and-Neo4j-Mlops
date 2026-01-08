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
  timeout    = 600
  wait       = false  # ← Không đợi pod ready (tránh treo)

  set {
    name  = "controller.service.type"
    value = var.environment == "prod" ? "LoadBalancer" : "NodePort"
  }
  
  set {
    name  = "controller.hostNetwork"
    value = var.environment == "prod" ? "true" : "false"  # ← Lắng nghe trực tiếp port 80 trên host
  }

  set {
    name  = "controller.resources.limits.cpu"
    value = "500m"
  }
}

# 3. Create ExternalName services để reference service từ namespace khác
# resource "kubernetes_service" "frontend_external" {
#   metadata {
#     name      = "chatbot-frontend"
#     namespace = kubernetes_namespace.ingress.metadata[0].name
#   }
#   spec {
#     type          = "ExternalName"
#     external_name = "chatbot-frontend.default.svc.cluster.local"
#     port {
#       port        = var.ingress_config.frontend_port
#       target_port = var.ingress_config.frontend_port
#       protocol    = "TCP"
#     }
#   }
# }

# resource "kubernetes_service" "backend_external" {
#   metadata {
#     name      = "chatbot-backend"
#     namespace = kubernetes_namespace.ingress.metadata[0].name
#   }
#   spec {
#     type          = "ExternalName"
#     external_name = "chatbot-backend.default.svc.cluster.local"
#     port {
#       port        = var.ingress_config.backend_port
#       target_port = var.ingress_config.backend_port
#       protocol    = "TCP"
#     }
#   }
# }

# resource "kubernetes_service" "jaeger_external" {
#   metadata {
#     name      = "jaeger"
#     namespace = kubernetes_namespace.ingress.metadata[0].name
#   }
#   spec {
#     type          = "ExternalName"
#     external_name = "jaeger.jaeger.svc.cluster.local"
#     port {
#       port        = var.ingress_config.jaeger_port
#       target_port = var.ingress_config.jaeger_port
#       protocol    = "TCP"
#     }
#   }
# }

# 4. Wait for Nginx Controller to be ready
resource "time_sleep" "wait_for_nginx" {
  depends_on      = [helm_release.nginx_ingress]
  create_duration = "30s"  # Chờ 30s để pod ready
}

# 5. Apply Ingress Rule from YAML template
resource "kubernetes_manifest" "ingress_rules" {
  # Quét tất cả file .yaml trong thư mục templates
  for_each = fileset("${path.module}/templates", "*.yaml")

  manifest = yamldecode(templatefile("${path.module}/templates/${each.value}",  merge(var.ingress_config)))

  # manifest = yamldecode(templatefile("${path.module}/templates/${each.value}", merge(
  #   var.ingress_config, {app_namespace    = var.ingress_config.app_namespace}
  # )))

  depends_on = [time_sleep.wait_for_nginx]
}