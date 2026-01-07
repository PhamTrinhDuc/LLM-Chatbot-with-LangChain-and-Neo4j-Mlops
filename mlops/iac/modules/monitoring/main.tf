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
