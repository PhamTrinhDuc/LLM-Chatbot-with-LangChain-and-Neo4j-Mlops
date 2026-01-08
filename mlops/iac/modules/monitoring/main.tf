# Monitoring Module - Placeholder
# TODO: Implement monitoring stack configuration

resource "kubernetes_namespace" "monitoring" {
  metadata {
    name = var.namespace
    labels = {
      "app.kubernetes.io/name" = "monitoring"
      environment              = var.environment
    }
  }
}


resource "helm_release" "monitoring" {
  name = "kube-prometheus-stack"
  repository = "https://prometheus-community.github.io/helm-charts"
  chart = "kube-prometheus-stack"
  namespace = kubernetes_namespace.monitoring.metadata[0].name

  values = [
    file("${path.module}/monitoring-values.yaml")
  ]
  depends_on = [kubernetes_namespace.monitoring]
}