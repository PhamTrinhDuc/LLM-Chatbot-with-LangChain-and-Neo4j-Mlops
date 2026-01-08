## 1. Nhầm lẫn tên Chart khi viết Resource cho Terraform 
- Bug: could not download chart: chart "jaegertracing" not found in https://jaegertracing.github.io/helm-charts repository. Tên chart đang không chính xác 
- Từ 2 câu lệnh: 
```bash 
# add repo to helm
helm repo add jaegertracing https://jaegertracing.github.io/helm-charts
# install helm chart 
helm install jaeger jaegertracing/jaeger
``` 
- Ở đây: `jaegertracing` là tên của repo. `jaeger` là tên chart

## 2. Output khi apply của Jaeger lại là Loki-stack 
```bash
Outputs:
logging = {
  "grafana_service" = "loki-stack-grafana"
  "helm_release_name" = "loki-stack"
  "loki_service" = "loki-stack"
  "namespace" = "loki-stack"
  "prometheus_service" = "loki-stack-prometheus-server"
}
```
- Điều này là bởi trong file `outputs.tf` ở root folder chưa thêm output cho jaeger: 
```bash
# thêm vào file outputs.tf
output "jaeger" {
  description = "Jaeger (distributed tracing) outputs"
  value       = module.jaeger
}
``` 

## 3. Lỗi không có attribute khi terraform apply Nginx 
- Bug: │ This object does not have an attribute named "jaeger_svc".
- Điều này là bởi khi thêm biến jaeger_svc vào file `variables.tf` trong root folder `/iac` nhưng không thêm vào file `variables.tf` trong child module jaeger
- Khi thêm 1 biến cho module, cần thêm ở 2 files `variables.tf` ở sub module và root và thêm vào file `terraform.tfvars` (khá phiền phức)

## 4. Lỗi khi cấu hình Svc name trong variables.tfvars
- Khi cấu hình chỉ Service name như: chatbot-backend, chatbot-frontend, v.v... Nginx sẽ không biết các Service này vì chúng khác namespace: 
```bash
W0108 08:28:22.927995 7 controller.go:1126] Error obtaining Endpoints for Service "ingress-nginx/chatbot-frontend": no object matching key "ingress-nginx/chatbot-frontend" in local store
```

- Vậy ta sẽ cấu hình đầy đủ để cho Nginx biết cả Service name trong namespace nào. trong file `variables.tfvars` ta sửa Svc thành: `chatbot-frontend.default.svc.cluster.local  # ← FQDN đầy đủ`. Sau đó sẽ lại gặp bug tiếp khi terraform apply lại vì bị Kubernetes reject: 
```bash
│ Error: spec.rules[0].http.paths[0].backend.service.name
│ 
│   with module.ingress_nginx.kubernetes_manifest.ingress_rule,
│   on modules/ingress-nginx/main.tf line 36, in resource "kubernetes_manifest" "ingress_rule":
│   36: resource "kubernetes_manifest" "ingress_rule" {
│ 
│ Invalid value: "chatbot-frontend.default.svc.cluster.local": a DNS-1035 label must consist of lower case
│ alphanumeric characters or '-', start with an alphabetic character, and end with an alphanumeric character
│ (e.g. 'my-name',  or 'abc-123', regex used for validation is '[a-z]([-a-z0-9]*[a-z0-9])?')
╵
```
- **Giải pháp tốt nhất**: Dùng **ExternalName services** để tạo "aliases" trong namespace `ingress-nginx` pointing đến services ở namespaces khác:
```hcl
# Tạo ExternalName service
resource "kubernetes_service" "frontend_external" {
  metadata {
    name      = "chatbot-frontend"
    namespace = kubernetes_namespace.ingress.metadata[0].name
  }
  spec {
    type          = "ExternalName"
    external_name = "chatbot-frontend.default.svc.cluster.local"
    port {
      port        = 8501
      target_port = 8501
      protocol    = "TCP"
    }
  }
}
```

- Sau đó, trong `terraform.tfvars` dùng tên service đơn giản:
```hcl
frontend_svc   = "chatbot-frontend"  # ← Không FQDN
backend_svc    = "chatbot-backend"
jaeger_svc     = "jaeger"
```

- **Thêm `hostNetwork: true`** để Nginx lắng nghe trực tiếp port 80 trên host:
```hcl
set {
  name  = "controller.hostNetwork"
  value = "true"
}
```

## 5. Cross-Namespace Service Routing (ExternalName Pattern)
- **Vấn đề**: Ingress ở namespace `ingress-nginx`, nhưng backend services ở namespaces khác (default, jaeger)
- **Giải pháp**: ExternalName services hoạt động như "proxy" - tạo service aliases trong Nginx namespace pointing sang services ở namespaces khác
- Khi combine với `hostNetwork: true`, Nginx có thể lắng nghe port 80 trực tiếp và route qua ExternalName services tới backends