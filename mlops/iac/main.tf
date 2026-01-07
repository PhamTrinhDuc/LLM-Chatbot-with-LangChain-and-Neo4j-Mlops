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

provider "kubernetes" {
  config_path = var.kubeconfig_path
}

provider "helm" {
  kubernetes {
    config_path = var.kubeconfig_path
  }
}

# Import modules
module "ingress_nginx" {
  source = "./modules/ingress-nginx"
  
  kubeconfig_path = var.kubeconfig_path
  namespace       = var.ingress_nginx_namespace
  environment     = var.environment
  ingress_config  = var.ingress_config
}

module "logging" {
  source = "./modules/logging"
  
  kubeconfig_path = var.kubeconfig_path
  namespace       = var.logging_namespace
  environment     = var.environment
}

# Uncomment when monitoring module is ready
# module "monitoring" {
#   source = "./modules/monitoring"
#   
#   kubeconfig_path = var.kubeconfig_path
#   namespace       = var.monitoring_namespace
#   environment     = var.environment
# }

# Uncomment when jaeger module is ready
# module "jaeger" {
#   source = "./modules/jaeger"
#   
#   kubeconfig_path = var.kubeconfig_path
#   namespace       = var.jaeger_namespace
#   environment     = var.environment
# }
