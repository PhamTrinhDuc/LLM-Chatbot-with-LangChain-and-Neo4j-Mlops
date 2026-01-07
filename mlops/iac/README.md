# Infrastructure as Code (IaC) - Terraform

Cấu trúc Terraform refactored sử dụng **Root Module + Child Modules pattern** để tối ưu hóa code reusability và maintainability.

## Cấu trúc thư mục

```
iac/
├── main.tf                 # Root module: providers + module calls
├── variables.tf            # Root variables (centralized)
├── terraform.tfvars        # Root values (environment-specific)
├── outputs.tf              # Root outputs
├── modules/
│   ├── ingress-nginx/      # Nginx Ingress Controller module
│   │   ├── main.tf
│   │   ├── variables.tf
│   │   ├── outputs.tf
│   │   └── ingress-nginx.yaml
│   ├── logging/            # Logging Stack (Prometheus, Loki, Grafana)
│   │   ├── main.tf
│   │   ├── variables.tf
│   │   └── outputs.tf
│   ├── monitoring/         # Monitoring module (placeholder)
│   │   ├── main.tf
│   │   ├── variables.tf
│   │   └── outputs.tf
│   └── jaeger/             # Jaeger tracing module (placeholder)
│       ├── main.tf
│       ├── variables.tf
│       └── outputs.tf
└── README.md
```

## Cách sử dụng

### 1. Initialize Terraform
```bash
cd /path/to/iac
terraform init
```

### 2. Plan deployment
```bash
terraform plan -out=tfplan
```

### 3. Apply deployment
```bash
terraform apply tfplan
```
### 4. For specific module 
```bash
terraform plan -target=module.<name_module>
terraform apply -target=module.<name_module>
```

### 5. Enable/Disable Modules
Để enable module chưa implement (monitoring, jaeger), uncomment tương ứng trong `main.tf`:

```tf
# Uncomment when monitoring module is ready
module "monitoring" {
  source = "./modules/monitoring"
  
  kubeconfig_path = var.kubeconfig_path
  namespace       = var.monitoring_namespace
  environment     = var.environment
}
```

### 6. Destroy all Infa
```bash
terraform destroy
```

### 7. Deploy specific module
```bash
terraform apply -target=module.ingress_nginx
terraform apply -target=module.logging
terraform destroy -target=module.logging
```

## Variables (terraform.tfvars)

Tất cả configuration được centralize ở `terraform.tfvars`:

```hcl
environment = "dev"  # dev, staging, prod

# Ingress Nginx
ingress_nginx_namespace = "ingress-nginx"

# Logging (PLG Stack)
logging_namespace = "loki-stack"

# Ingress routing configuration
ingress_config = {
  ingress_name   = "plg-ingress"
  frontend_host  = "chatbot-medical.local"
  backend_host   = "api.chatbot-medical.local"
  frontend_port  = 8501
  backend_port   = 8000
  frontend_svc   = "chatbot-frontend"
  backend_svc    = "chatbot-backend"
}
```
## Troubleshooting

### Provider version conflicts
Nếu gặp provider version issue, sửa `terraform` block ở `main.tf`:
```tf
terraform {
  required_providers {
    kubernetes = {
      version = "~> 2.20"  # Adjust as needed
    }
  }
}
```

### Module not found
Đảm bảo bạn ở trong `/iac` directory trước khi chạy terraform commands.

## Next Steps

1. Implement monitoring stack configuration
2. Implement Jaeger tracing configuration
3. Add terraform remote state (S3, Terraform Cloud)
4. Setup CI/CD pipeline với Terraform
5. Add policy-as-code (Sentinel hoặc OPA)
