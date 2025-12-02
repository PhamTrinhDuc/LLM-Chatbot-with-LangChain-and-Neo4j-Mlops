# Hospital Chatbot Frontend

Giao diện Streamlit cho Hospital & DSM-5 Chatbot.

## Setup

```bash
pip install -r requirements.txt
```

## Run

```bash
streamlit run app.py
```

## Cấu trúc

```
frontend/
├── app.py              # Main entry point
├── requirements.txt
├── .env
└── src/
    ├── utils/
    │   ├── api_client.py   # API calls
    │   └── helpers.py      # Helper functions
    └── pages/
        ├── chat.py        # Chat page
        └── tools.py       # Tools page
```

## Features

- **Login/Register/Logout**: Quản lý tài khoản người dùng
- **Chat**: Trò chuyện với AI agent (streaming)
- **Tools**: Sử dụng tools riêng biệt (DSM-5, Hospital Query)
- **History**: Lưu lịch sử trò chuyện
