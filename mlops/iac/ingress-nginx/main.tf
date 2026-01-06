terraform {
  required_version = ">= 1.0"
  required_providers {
    kubernetes = {
      source  = "hashicorp/kubernetes"
      version = "~> 2.20"
    }
    helm = {
      source  = "hashicorp/helm"
      version = "~> 2.10"
    }
  }
}

# 1. Khai báo Provider: Bảo TF kết nối với Minikube và Helm 
provider "kubernetes" {
  config_path = var.kubeconfig_path # lấy thông tin kết nối minikube từ file config mặc định 
}

provider "helm" {
  kubernetes {
    config_path= var.kubeconfig_path
  }
}

# 2. Create namespace
resource "namespace" "ingress" {
  name = var.namespace
  labels = {
    "app.kubernetes.io/name" = "ingress-nginx"
    environment = var.environment
  }
}


# 3. Deploy Nginx INgress Controller bằng Helm 
resource "helm_release" "nginx_ingress" {
  name = "ingress-nginx"
  repository = "https://kubernetes.github.io/ingress-nginx"
  chart = "ingress-nginx"
  namspace = "ingress-nginx"
  create_namespace = True # tự tạo namespace nếu chưa có 
  set {
    name = "controller.service.type"
    value = var.environment == "prod" ? "LoadBalancer": "NodePort"
  }

  set {
    name = "controller.resources.limits.cpu"
    value = var.environment = "prod" ? "500m" : "200m"
  }
}

# 4. Apply Ingress Rule (Sử dụng YAML)
resource "kubernetes_manifest" "ingress_nginx" {
  manifest = yamldecode(templatefile("${path.module}/ingress-nginx.yaml", {
    ingress_name = var.ingress_config.ingress_name
    frontend_host = var.ingress_config.frontend_host
    backend_host = var.ingress_config.backend_host
    frontend_port = var.ingress_config.frontend_port
    backend_port = var.ingress_config.backend_port
    frontend_svc = var.ingress_config.frontend_svc
    backend_svc = var.ingress_config.backend_svc
  }))

  # apply sau khi controller ready 
  depends_on = [helm_release.nginx_ingress]
}