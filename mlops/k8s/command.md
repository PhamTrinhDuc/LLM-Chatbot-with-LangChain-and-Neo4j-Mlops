# 1. Deploy chart using Helm: 
```bash
helm install chatbot-backend . --namespace default
```
# 2. View detail pod
```bash
kubectl describe pod chatbot-backend-d7cd5cf97-gxbhd
```
# 3. View Service of Pod
```bash
kubectl get svc -o wide
```
# 4. Get all secrets
```bash
kubectl get secrets
```
# 5. Create secret
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
# 6. Delete secret 
```bash
kubectl delete secret <secret_name>
```

# 7. Access to Backend-FastAPI
```bash
 # 1. Access in WSL (not Window)
minikube service chatbot-backend
# Terminal display url: http://127.0.0.1:42899
# 2. Access in WSL 
curl http://192.168.49.2:32663/health # or brower in WSL
```

# 8. Upgrade Helm chart
```bash
cd mlops/k8s/charts/backend
helm upgrade chatbot-backend .
```

# 9. View list helm
```bash
helm list --all-namespaces
```