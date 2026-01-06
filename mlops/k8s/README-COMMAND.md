> *Note: This is a file to practice manual commands. Later, it can be replaced with using Terraform for management.*


## I. Command usage
### 1. Deploy chart using Helm: 
```bash
helm install chatbot-backend . --namespace default
```
### 2. View detail pod
```bash
kubectl describe pod chatbot-backend-d7cd5cf97-gxbhd
```
### 3. View Service of Pod
```bash
kubectl get svc -o wide
```
### 4. Get all secrets
```bash
kubectl get secrets
```
### 5. Create secret
```bash
kubectl create secret generic <secret_name> \
  --from-literal=OPENAI_API_KEY="sk-proj" \
  --from-literal=GOOGLE_API_KEY="AIz" \
  --from-literal=GROQ_API_KEY="gsk_YHM" \
  --from-literal=ELS_HOST="elasticsearch" \
  --from-literal=ELS_PORT="9200" \
  --from-literal=ELASTIC_VERSION="8.4.1" \
  --from-literal=ELASTIC_PASSWORD='changeme'\
  --from-literal=LOGSTASH_INTERNAL_PASSWORD='changeme' \
  --from-literal=KIBANA_SYSTEM_PASSWORD="changeme" \
  --from-literal=JAEGER_HOST="jaeger" \
  --from-literal=JAEGER_PORT="6831" \
  --from-literal=NEO4J_URI="bolt://neo4j:7687"\
  --from-literal=NEO4J_USER="neo4j" \
  --from-literal=NEO4J_PASSWORD="bot-neo4j" \
  --from-literal=REDIS_URL="redis://bot-neo4j:bot-neo4j@redis:6379/0" \
  --from-literal=ENV_LOG="production" \
  --namespace <name_namespace>
```
### 6. Delete secret 
```bash
kubectl delete secret <secret_name>
```

### 7. Access to Backend-FastAPI
```bash
 # 1. Access in WSL (not Window)
minikube service chatbot-backend
# Terminal display url: http://127.0.0.1:42899
kubectl port-forward svc/chatbot-backend 8000:8000
# 2. Access in WSL 
curl http://192.168.49.2:32663/health # or brower in WSL
```

### 8. Upgrade Helm chart
```bash
cd mlops/k8s/charts/backend
helm upgrade chatbot-backend .
```

### 9. View list helm
```bash
helm list --all-namespaces
```

### 10. Switch namspaces 
```bash
# List namespaces 
kubens 
# Switch to specific namespace
kubens <namespace_name>
```
### 11. Debug YAML 
```bash
kubectl apply -f ingress.yaml --dry-run=client
kubectl explain ingress.spec
kubectl get ingress
kubectl describe ingress ingress-nginx
```

## II. Install Stacks PLG, Monitering, v.v. using Helm
### 1. Install Monitering (Promethues, Grafana, AlerManager, NodeExpoter, v.v.)
```bash
cd ./mlops/k8s

# 1. Add repo prometheus to Helm
helm repo add prometheus-community https://prometheus-community.github.io/helm-charts
helm repo update

# 2. Install combo to namspace "monitering"
helm install monitor prometheus-community/kube-prometheus-stack \
  -f monitoring-values.yaml \
  --namespace monitoring \
  --create-namespace

# 3. Access to Grafana
kubectl port-forward deployment/monitor-grafana 3000:3000 -n monitoring
# ID: 
# 15661 (Kubernetes / Compute Resources / Pod)
# 1860 (Node exporter full)

# 4. Delete stacks monitering 
helm uninstall monitor -n monitoring
kubectl delete crd alertmanagerconfigs.monitoring.coreos.com alertmanagers.monitoring.coreos.com podmonitors.monitoring.coreos.com probes.monitoring.coreos.com prometheuses.monitoring.coreos.com prometheusrules.monitoring.coreos.com servicemonitors.monitoring.coreos.com thanosrulers.monitoring.coreos.com
kubectl delete namespace monitoring
```

### 2. Install Centralized Logging (Promtail, Loki, Grafana)
```bash
# 1. Add repo
helm repo add grafana https://grafana.github.io/helm-charts
helm repo update

# 2. Install PLG
helm install loki-stack grafana/loki-stack \
  --set grafana.enabled=true \
  --set prometheus.enabled=true \
  --set prometheus.alertmanager.enabled=false \
  --set prometheus.server.retention=1d \
  --namespace logging --create-namespace

# 3. Get password Grafana 
kubectl get secret --namespace logging loki-stack-grafana -o jsonpath="{.data.admin-password}" | base64 --decode ; echo
# 4. Access to Grafana 
kubectl port-forward --namespace logging  service/loki-stack-grafana 3000:80

# 4. Gỡ stacks logging 
helm uninstall loki-stack -n logging
kubectl delete ns logging
```

### 3. Install Jaeger
```bash
# 1. Add repo jaegertracing
helm repo add jaegertracing https://jaegertracing.github.io/helm-charts
helm repo update

# 2. Install Jaeger All-in-one
helm install jaeger jaegertracing/jaeger \
  --set allInOne.enabled=true \
  --set storage.type=none \
  --namespace monitoring --create-namespace

# 3. Access to Jaeger 
kubectl port-forward -n monitoring <pod_name> 16686:16686

# 4. Pass var JAEGER_ENDPOINT on github secrets
# http://<service-name>.<namespace>.svc.cluster.local
http://jaeger.monitoring.svc.cluster.local:4317
```

## III. Setup Nginx Ingress
```bash
# install nginx
minikube addons enable ingress
# apply rule ingress for nginx controller
kubectl apply -f chatbot-ingress.yaml
# Get IP minikube: minikube ip
# Open file hosts (on Windows using Notepad with role Admin open C:\Windows\System32\drivers\etc\hosts. on Ubuntu: sudo nano /etc/hosts)
# Add new line: <IP_MINIKUBE> chatbot.local (Example: 192.168.49.2 chatbot.local).
```