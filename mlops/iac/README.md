# Infrastructure as Code (IaC) - Terraform

Refactored Terraform structure using **Root Module + Child Modules pattern** to optimize deployment reusability and maintainability.

## Directory Structure

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

## Usage

### 1. Initialize Terraform
```bash
cd /path/to/iac
terraform init
```

### 2. Plan deployment
```bash
terraform plan -out=tfplan
# for specific module 
terraform plan -target=module.<name_module> 
```

### 3. Validate command 
```bash
tarraform validate 
# for specific module 
cd modules/<name_module> 
tarraform validate
```

### 4. Apply deployment
```bash
terraform apply tfplan
# for specific module 
terraform apply -target=module.<name_module>
```

### 5. Destroy all Infrastructure
```bash
terraform destroy
# for specific module 
terraform destroy -target=module.logging

```

## Variables (terraform.tfvars)

All configuration is centralized in `terraform.tfvars`:

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
If you encounter provider version issues, modify the `terraform` block in `main.tf`:
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
Make sure you are in the `/iac` directory before running terraform commands.


### Confusion between modules and module
When running commands like `terraform apply -target=module.jearger`
- `module` here is the keyword in the `main.tf` file in the root folder
- Not the `modules` folder

## Next Steps

1. Implement monitoring stack configuration
2. Implement Jaeger tracing configuration
3. Add terraform remote state (S3, Terraform Cloud)
4. Setup CI/CD pipeline with Terraform
5. Add policy-as-code (Sentinel or OPA)
