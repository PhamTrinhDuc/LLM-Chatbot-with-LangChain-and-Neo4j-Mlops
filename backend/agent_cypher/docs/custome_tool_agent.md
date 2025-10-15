## 1. Luồng dữ liệu trong AgentExecutor
- Khi bạn chạy:
```bash
result = agent_executor.invoke({"input": "Tìm bệnh nhân A"})
```
- LangChain thực hiện pipeline như sau 👇
```bash
User input
   ↓
LLM → sinh "tool call" (Action)
   ↓
Tool được gọi → trả output (Observation)
   ↓
Agent lưu (Action, Observation) vào intermediate_steps
   ↓
LLM đọc lại Observation để reasoning bước kế tiếp
   ↓
Trả kết quả cuối (output + intermediate_steps)
```

## 2. Cấu trúc thật sự của intermediate_steps
#### Mỗi bước trung gian được lưu trong danh sách:

```bash
intermediate_steps = [
    (AgentAction, observation),
    (AgentAction, observation),
    ...
]
```
- AgentAction: mô tả LLM đã chọn tool nào, với input gì.
- observation: chính là kết quả trả về từ tool của bạn.
```bash
Ví dụ:

[
  (
    AgentAction(tool='lookup_patient', tool_input='Nguyen Van A', log='...'),
    {
        "result": "Bệnh nhân Nguyen Van A bị tiểu đường",
        "metadata": {"source": "neo4j", "records_found": 3}
    }
  )
]
```
#### Vậy nên:
- Tool return → observation
- Observation → nằm trong intermediate_steps
- AgentExecutor cuối → gộp tất cả observation để reasoning