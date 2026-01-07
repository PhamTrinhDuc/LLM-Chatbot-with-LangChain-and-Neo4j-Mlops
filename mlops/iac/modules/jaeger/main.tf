# Jaeger Module - Placeholder
# TODO: Implement Jaeger (distributed tracing) configuration

resource "kubernetes_namespace" "jaeger" {
  metadata {
    name = var.namespace
    labels = {
      "app.kubernetes.io/name" = "jaeger"
      environment              = var.environment
    }
  }
}
