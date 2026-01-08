### 1. Vấn đề Namespace Scope (Quan trọng nhất)

* **Vấn đề:** Ingress Resource và Service mà nó trỏ tới **bắt buộc** phải nằm cùng một Namespace.
* **Biểu hiện:** Lỗi `503 Service Temporarily Unavailable` hoặc log Nginx báo `no object matching key`.
* **Giải pháp:** Tách Ingress thành nhiều file/resource. Ingress của App nằm ở namespace `default`, Ingress của Jaeger nằm ở namespace `jaeger`.

### 2. Định dạng Tên Service (DNS-1035)

* **Vấn đề:** Trường `service.name` trong Ingress chỉ nhận tên ngắn, không nhận FQDN (không được có dấu chấm).
* **Lỗi:** `a DNS-1035 label must consist of lower case alphanumeric characters or '-'`.
* **Giải pháp:** Dùng tên service thuần túy (VD: `chatbot-backend`), không dùng `chatbot-backend.default.svc...`.

### 3. Lỗi Validating Webhook (TLS Error)

* **Vấn đề:** Khi cài Nginx bằng Helm trên Minikube, cơ chế kiểm tra chứng chỉ (Admission Webhook) thường bị lỗi cert.
* **Lỗi:** `failed calling webhook... tls: failed to verify certificate`.
* **Giải pháp:** * Set `controller.admissionWebhooks.enabled = false` trong Helm chart.
* Xóa thủ công nếu bị kẹt: `kubectl delete validatingwebhookconfigurations ingress-nginx-admission`.



### 4. Cấu hình Websocket cho Streamlit

* **Vấn đề:** Streamlit (và các app chat) dùng Websocket, nếu không cấu hình Nginx sẽ ngắt kết nối sau 60s.
* **Giải pháp:** Thêm các Annotation:
* `nginx.ingress.kubernetes.io/websocket-services: "tên-service"`
* `nginx.ingress.kubernetes.io/proxy-read-timeout: "3600"`
* `nginx.ingress.kubernetes.io/proxy-http-version: "1.1"`



### 5. Lỗi 404 & Snippet Annotation

* **Vấn đề:** Sử dụng `configuration-snippet` có thể bị Nginx chặn vì lý do bảo mật, dẫn đến không nạp cấu hình (Address bị trống).
* **Giải pháp:** Ưu tiên dùng các Annotation chuẩn của Ingress Controller thay vì viết snippet thủ công. Nếu dùng snippet, phải enable `allow-snippet-annotations`.

### 6. Truy cập từ máy thật (Expose Port)

* **Vấn đề:** K8s chạy trong mạng ảo, máy thật không gọi vào được cổng 80 của IP Minikube.
* **Giải pháp:** * Sử dụng `hostNetwork: true` để Nginx chiếm cổng 80 của máy host (Minikube).
* Sử dụng `minikube tunnel` nếu dùng Service type `LoadBalancer`.



### 7. Cách Test "Pro" (Không cần sửa file hosts)

* **Cú pháp:** `curl -H "Host: <domain-của-bạn>" http://<IP-Minikube>/<path>`
* **Ý nghĩa:** Truyền trực tiếp tên miền vào Header để Nginx nhận diện được Virtual Host mà không cần thông qua hệ thống phân giải DNS của máy tính.

---

**Chốt lại luồng debug:**

1. Check `kubectl get ingress -A`: Có IP ở cột **Address** chưa?
2. Check `kubectl describe ingress`: Cột **Backends** có hiện IP của Pod chưa?
3. Check `kubectl logs`: Nginx có báo `reload failed` không?
4. Check `curl -v`: 404 là từ Nginx hay từ App Backend?