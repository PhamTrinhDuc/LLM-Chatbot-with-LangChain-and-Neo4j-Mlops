# Logging Module (PLG Stack: Prometheus, Loki, Grafana) - Main configuration
# Reference: https://aviitala.com/posts/deploy-plg-stack/

# 1. Create namespace
resource "kubernetes_namespace" "loki_stack" {
  metadata {
    name = var.namespace
    labels = {
      "app.kubernetes.io/name" = "loki-stack"
      environment              = var.environment
    }
  }
}

# 2. Deploy PLG Stack via Helm
resource "helm_release" "loki_stack" {
  name       = "loki-stack"
  repository = "https://grafana.github.io/helm-charts"
  chart      = "loki-stack"
  namespace  = kubernetes_namespace.loki_stack.metadata[0].name

  set {
    name  = "prometheus.service.type"
    value = var.environment == "prod" ? "LoadBalancer" : "NodePort"
  }

  set {
    name  = "grafana.enabled"
    value = "true"
  }

  set {
    name  = "prometheus.enabled"
    value = "true"
  }

  set {
    name  = "prometheus.alertmanager.enabled"
    value = "false"
  }

  set {
    name  = "prometheus.server.retention"
    value = "1d"
  }
}
