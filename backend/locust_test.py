import random
from locust import HttpUser, task, between


class ChatMockUser(HttpUser):
    wait_time = between(0.5, 2)  # user nghĩ giữa các request

    @task
    def chat_mock(self):
        payload = {
            "user_id": f"user_{random.randint(1, 1000)}",
            "query": "Hello, this is a load test",
        }

        headers = {
            "Content-Type": "application/json",
            "X-Load-Test": "true",  # rất quan trọng
        }

        self.client.post(
            "/chat/mock-test", json=payload, headers=headers, name="/chat/mock-test"
        )


# locust -f locustfile.py --host https://myapp.com

# Users:      100 # số lượng user đồng thời
# Ramp up:    1–2 users/s # tốc độ tăng user (mỗi giây tăng 1-2 user)
# Run time:   5–10m # thời gian chạy bài test
# Host:       ingress domain # địa chỉ host của ứng dụng cần test
