
from fastapi.testclient import TestClient

from app.api.main import app


def test_health_check():
    """健康检查接口应返回成功状态。"""
    with TestClient(app) as client:
        response = client.get("/health")

    assert response.status_code == 200
    assert response.json()["status"] == "ok"
    assert response.json()["service"] == "business-ops-agent"


def test_chat_success(monkeypatch):
    """正常请求应返回回答和会话标识，不调用真实 Agent。"""
    async def fake_run_agent(
        user_input: str,
        thread_id: str,
        request_id: str | None = None,
    ) -> str:
        assert user_input == "查询客户 CUST001"
        assert thread_id == "api-unit-test"
        assert request_id
        return "模拟回答：客户 CUST001 查询成功"

    monkeypatch.setattr(
        "app.api.main.async_run_agent",
        fake_run_agent,
    )

    with TestClient(app) as client:
        response = client.post(
            "/chat",
            json={
                "message": "查询客户 CUST001",
                "thread_id": "api-unit-test",
            },
        )

    assert response.status_code == 200

    data = response.json()
    assert data["request_id"]
    assert data["thread_id"] == "api-unit-test"
    assert data["answer"] == "模拟回答：客户 CUST001 查询成功"


def test_chat_rejects_blank_message():
    """仅包含空白字符的消息应被拒绝。"""
    with TestClient(app) as client:
        response = client.post(
            "/chat",
            json={
                "message": "   ",
                "thread_id": "api-validation-test",
            },
        )

    assert response.status_code == 422


def test_chat_rejects_missing_thread_id():
    """缺少会话 ID 时应被拒绝。"""
    with TestClient(app) as client:
        response = client.post(
            "/chat",
            json={
                "message": "查询客户 CUST001",
            },
        )

    assert response.status_code == 422


def test_chat_rejects_oversized_message():
    """超过 5000 字符的消息应被 Pydantic 拒绝。"""
    with TestClient(app) as client:
        response = client.post(
            "/chat",
            json={
                "message": "a" * 5001,
                "thread_id": "api-validation-test",
            },
        )

    assert response.status_code == 422
