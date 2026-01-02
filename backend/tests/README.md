# Test Suite - Hospital Chatbot API

Bộ test case chuẩn cho CI/CD của Hospital Chatbot API.

## Cấu trúc

```
tests/
├── conftest.py              # Pytest fixtures và configuration
├── __init__.py              # Package init
├── requirements.txt         # Test dependencies
├── test_auth.py             # Authentication tests
├── test_conversations.py    # Conversation management tests
├── test_messages.py         # Message endpoint tests
├── test_dsm5.py             # DSM-5 tool tests
├── test_cypher.py           # Cypher query tests
├── test_health.py           # Health check tests
└── test_integration.py      # Integration tests
```

## Cài đặt

```bash
# Cài đặt dependencies
pip install -r tests/requirements.txt

# Hoặc cài vào environment hiện tại
pip install pytest pytest-asyncio pytest-cov httpx
```

## Chạy Tests

### Chạy tất cả tests
```bash
pytest
```

### Chạy tests với verbose output
```bash
pytest -v
```

### Chạy tests theo marker
```bash
# Chỉ authentication tests
pytest -m auth

# Chỉ conversation tests
pytest -m conversation

# Chỉ integration tests
pytest -m integration
```

### Chạy tests theo file
```bash
pytest tests/test_auth.py
```

### Chạy tests với coverage report
```bash
pytest --cov=backend --cov-report=html
```

### Chạy tests trong watch mode
```bash
pytest --looponfail
```

## Test Categories

### Authentication Tests (`test_auth.py`)
- ✅ User registration
- ✅ User login
- ✅ Invalid credentials
- ✅ Duplicate username

### Conversation Tests (`test_conversations.py`)
- ✅ Create conversation
- ✅ Get conversations
- ✅ Update title
- ✅ Delete conversation
- ✅ List ordering

### Message Tests (`test_messages.py`)
- ✅ Add messages
- ✅ Get messages
- ✅ Clear messages
- ✅ Message ordering
- ✅ Content preservation

### DSM-5 Tests (`test_dsm5.py`)
- ✅ Search functionality
- ✅ Hybrid search
- ✅ Criteria search
- ✅ Response structure

### Cypher Tests (`test_cypher.py`)
- ✅ Query endpoints
- ✅ Patient search
- ✅ Hospital statistics
- ✅ Cypher generation

### Integration Tests (`test_integration.py`)
- ✅ Complete user flow
- ✅ Conversation lifecycle
- ✅ Conversation isolation

## CI/CD Configuration

### GitHub Actions
```yaml
name: Tests
on: [push, pull_request]
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2
      - uses: actions/setup-python@v2
        with:
          python-version: 3.9
      - run: pip install -r tests/requirements.txt
      - run: pytest --cov=backend
```

### GitLab CI
```yaml
test:
  image: python:3.9
  script:
    - pip install -r tests/requirements.txt
    - pytest --cov=backend
  coverage: '/TOTAL.*\s+(\d+%)$/'
```

## Fixtures

### Database Fixtures
- `db`: Fresh in-memory database
- `client`: Test client with overridden DB

### User Fixtures
- `test_user`: Một user test
- `test_user_2`: User test thứ hai

### Data Fixtures
- `test_conversation`: Một conversation test
- `test_messages`: Messages test
- `mock_query_request`: Mock query payload

## Markers

Các markers để chạy tests cụ thể:

```bash
pytest -m "auth or conversation"
pytest -m "not slow"
pytest -m integration
```

## Best Practices

1. **Unit Tests**: Mỗi test chỉ test một feature
2. **Isolation**: Tests độc lập, không depend nhau
3. **Fixtures**: Dùng fixtures thay vì setUp/tearDown
4. **Assertions**: Có ít nhất 1 assertion per test
5. **Names**: Test names mô tả rõ chức năng

## Troubleshooting

### Import Errors
```bash
# Thêm backend vào PYTHONPATH
export PYTHONPATH="${PYTHONPATH}:$(pwd)/backend"
pytest
```

### Database Locks
```bash
# Dùng in-memory database trong tests (đã config)
# Không cần làm gì thêm
```

### Async Tests
```bash
# pytest-asyncio đã được config
pytest tests/test_async.py
```

## Coverage Goals

- **Minimum**: 70%
- **Target**: 85%+
- **Ignore**: Migrations, conftest

## Contributing

Khi viết tests mới:

1. Tạo file `test_*.py` trong `tests/`
2. Dùng fixtures từ `conftest.py`
3. Thêm appropriate marker
4. Thêm docstring cho tests
5. Chạy `pytest` để verify
