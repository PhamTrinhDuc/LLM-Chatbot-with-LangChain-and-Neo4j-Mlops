# Hướng dẫn Load Testing với Locust

## 1. Thông số cấu hình test

Những tham số này quyết định test sẽ chạy như thế nào. Hãy cấu hình rõ ràng trước khi bắt đầu:

| Thông số | Ví dụ | Giải thích |
|----------|-------|-----------|
| **Endpoint** | `/chat/mock-test` | Chọn endpoint nào để test: agent thật, mock, hay qua ingress |
| **Environment** | `dev / staging / prod` | Mỗi env khác nhau: dev không rate-limit, prod có WAF |
| **Host** | `http://api.medical:8000` | URL backend để Locust gửi request |
| **Peak Users** | `100` | Số user tối đa sẽ tăng đến (ví dụ: từ 0 → 100 user) |
| **Ramp-up Rate** | `5 users/s` | Tốc độ tăng user (5 users/s = sau 20s có 100 users) |
| **Test duration** | `10 min` | Bao lâu thì dừng test (lâu hơn để thấy pattern ổn định) |
| **Agent mode** | `real / mock` | Thật = gọi LLM, mock = fake response (để test infrastructure) |
| **Rate-limit** | `on / off` | Có bật rate-limit hay không (để tìm bottleneck đúng) |

---

## 2. Bảng chỉ số chính trong Locust

Khi test chạy, bạn sẽ thấy những con số này. Dưới đây là ý nghĩa và cách đọc từng cái:

| Metric | Giá trị | Cách đọc | Lưu ý |
|--------|--------|---------|-------|
| **Requests** | `5000` | Tổng request đã gửi trong test | Nếu < 1000 = test chưa lâu, kết quả chưa đáng tin |
| **Fails** | `50` | Số request thất bại (lỗi, timeout, reject) | Không nên > 0, nếu có hãy check error type |
| **Current RPS** | `50 req/s` | Tốc độ request mỗi giây ngay lúc này | So với target RPS xem đạt được không |
| **Median (ms)** | `200ms` | 50% user nhanh hơn, 50% chậm hơn | Đây là "user bình thường" |
| **Average (ms)** | `250ms` | Tính trung bình tất cả request | Dễ bị đẩy cao bởi 1-2 request siêu chậm |
| **95%ile (ms)** | `500ms` | 95% user nhanh hơn giá trị này | Dùng cho SLA, nếu cao = nhiều user tệ |
| **99%ile (ms)** | `1000ms` | 99% user nhanh hơn giá trị này | Worst case, dùng để set alert |
| **Min (ms)** | `10ms` | Request nhanh nhất | < 20ms có thể cache/ingress đang bypass |
| **Max (ms)** | `5000ms` | Request chậm nhất | Nguy hiểm, có thể cold start hoặc crash |
| **Avg Size (bytes)** | `2048` | Kích thước response trung bình | Lớn quá = network overhead, có thể tối ưu |

---

## 3. Dấu hiệu báo động & cách xác định vấn đề

Khi nhìn kết quả, hãy check những dấu hiệu này:

| Dấu hiệu | Điều đó có nghĩa là... | Cách kiểm tra |
|----------|----------------------|--------------|
| **Latency < 20ms** | Chưa thật sự vào backend (bị cache hoặc ingress block) | Check ingress logs, cache config |
| **Fail = Requests (100%)** | Tất cả request đều fail, WAF/ingress chặn | Check WAF rules, API key, rate-limit policy |
| **P95 ≫ Median (gấp 5-10 lần)** | Latency rất không ổn định, có spike | Check LLM API, database query, network |
| **RPS tăng không lên dù users tăng** | Backend saturated (đã đạt giới hạn tài nguyên) | Scale thêm pod, hoặc optimize code |
| **Max latency tăng dần theo thời gian** | Memory leak hoặc queue stack up | Check memory usage, connection pool |
| **Fail tăng khi RPS tăng** | Một service nào đó là bottleneck | Profile code, check database, LLM API |

---

## 4. Mapping sang Grafana/Jaeger

Để hiểu rõ hơn, hãy cross-check với Grafana (máy chủ) và Jaeger (ứng dụng):

### Grafana - Xem tài nguyên máy chủ

| Metric | Kỳ vọng | Nếu không đúng thì... |
|--------|--------|----------------------|
| **CPU** | Tăng đều theo RPS (linear) | Nếu flat = I/O bound, nếu đột ngột tăng = thread block |
| **Memory** | Ổn định (không tăng liên tục) | Nếu tăng liên tục = memory leak, check logging/cache |
| **Network bytes/s** | Tăng đều theo payload size | Nếu cao bất thường = response quá lớn, tối ưu schema |
| **Pod Restart** | 0 (không restart) | Nếu > 0 = OOMKilled hoặc crash, tăng resource limit |

### Jaeger - Xem mỗi bước trong ứng dụng

| Span | Ý nghĩa | Bottleneck hay gặp |
|-----|---------|-------------------|
| **ingress → backend** | Thời gian từ load balancer tới backend | Rate-limit, WAF delay |
| **fastapi handler** | Parse request, validate schema | Request body quá lớn, validation phức tạp |
| **agent.invoke** | Chạy agent logic (think, decide tool) | Agent re-planning nhiều, tool gọi liên tiếp |
| **llm.call** | Gọi OpenAI API chờ response | **Đây là bottleneck số 1 (thường 1-3s)** |
| **tool.call** | Gọi Neo4j, Elasticsearch, API khác | Query database chậm, API timeout |

---

## 5. Workflow kiểm tra khi có vấn đề

Làm theo thứ tự này khi kết quả test không tốt:

1. **Bước 1**: Nhìn Locust → Fail % cao không? Latency quá cao không?
2. **Bước 2**: Mở Grafana → CPU/Memory có bình thường không? Có pod restart không?
3. **Bước 3**: Mở Jaeger → Span nào chậm nhất? (thường là `llm.call`)
4. **Bước 4**: Check logs backend → Có error, timeout, warning không?
5. **Bước 5**: Điều chỉnh config → Rate-limit, timeout, concurrency pool
6. **Bước 6**: Chạy lại test → So sánh kết quả trước/sau

