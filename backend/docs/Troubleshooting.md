# TROUBLESHOOTING 
>Ghi các vấn đề khi xây dựng dự án

### 1.  Section_queue không lưu đúng title của các mục: 
#### Problem: Giả sử section_id
- 1 xuất hiện 2 nơi trong PDF => section_id: 1 đầu tiên sẽ bị ghi đè => Nếu build_context_headers cho toàn bộ chunks sau khi đã tạo chunks xong thì section_id: 1 sẽ không còn đúng
#### Giải pháp: 
- thay vì build lại sau khi đã tạo xong chunks thì tạo luôn cho từng chunk lúc tạo chunk đó. 


### 2. Context khi dùng vector search không khớp với query
#### Problem: Sử dụng 2 loại model embedding cho 2 tác vụ
- 1. Sử dụng model BGE từ Hf_API khi indexing vào Elasticsearch
- 2. Sử dụng openai hoặc google embedding model khi Elastichsearch inference
>Dẫn đến 2 vector embedding khác nhau => context không chuẩn
#### Giải pháp: Chỉ sử dụng 1 embedding model cho 2 tác vụ



### 3. Log không hiện trong container 
- Khi chạy trên localhost thì log từ app vẫn hiện dươi terminal. Nhưng trong container thì không hiện log 
- Vấn đề là ở tham số `enqueue=True` khi setup logging. Khi chạy trong Docker:
  - App bị stop nhanh
  - Worker thread chưa kịp flush log
  - Hoặc container dùng --restart, --healthcheck
> log chưa kịp đẩy ra stdout ⇒ Docker không ghi
- Sửa lại tham số `enqueue=False`