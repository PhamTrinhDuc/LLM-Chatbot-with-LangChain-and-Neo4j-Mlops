| Thành phần                      | Vai trò                                                                            |
| ------------------------------- | ---------------------------------------------------------------------------------- |
| **FastAPI App**                 | Định nghĩa endpoint `/chat`.                                                       |
| **Uvicorn Server**              | Chạy event loop (ASGI). Khi có request, tạo coroutine mới.                         |
| **Event Loop**                  | Giống như một “lịch” bất đồng bộ: chạy nhiều coroutine song song (không blocking). |
| **Coroutine A/B/C**             | Mỗi request `/chat` → 1 coroutine riêng → 1 instance độc lập của hàm `chat()`.     |
| **agent_A / agent_B / agent_C** | Các biến cục bộ trong từng coroutine (hoàn toàn tách biệt).                        |
| **Response Collector**          | Sau khi mỗi coroutine hoàn tất, FastAPI gom response trả lại từng user tương ứng.  |


```bash
                          ┌────────────────────────┐
                          │      FastAPI App       │
                          │  (route: /chat)        │
                          └──────────┬─────────────┘
                                     │
                                     │
                          ┌──────────▼─────────────┐
                          │     Uvicorn Server     │
                          │  (ASGI Event Loop)     │
                          └──────────┬─────────────┘
                                     │
                                     │ nhận 3 request gần như cùng lúc
                                     │
          ┌─────────────────────────────────────────────────────────────┐
          │                         Event Loop                          │
          │                                                             │
          │   ┌─────────────────────┬─────────────────────┬──────────┐  │
          │   │ Coroutine A         │ Coroutine B         │ Coroutine C│
          │   │ (for user_1)        │ (for user_2)        │ (for user_3)│
          │   │                     │                     │            │
          │   │  async def chat():  │  async def chat():  │  async def chat():│
          │   │   ├─ agent_A        │   ├─ agent_B        │   ├─ agent_C     │
          │   │   ├─ msg_A          │   ├─ msg_B          │   ├─ msg_C       │
          │   │   └─ return resp_A  │   └─ return resp_B  │   └─ return resp_C│
          │   └─────────────────────┴─────────────────────┴──────────┘  │
          └─────────────────────────────────────────────────────────────┘
                                     │
                                     │
                          ┌──────────▼─────────────┐
                          │   Response Collector   │
                          ├────────────────────────┤
                          │ user_1 → resp_A        │
                          │ user_2 → resp_B        │
                          │ user_3 → resp_C        │
                          └────────────────────────┘

```