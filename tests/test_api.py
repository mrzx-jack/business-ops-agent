
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



def test_chat_returns_500_when_agent_raises(monkeypatch):
    """Agent 抛出未预期异常时，API 应返回 500 且不泄露内部错误。"""

    async def failing_run_agent(
        user_input: str,
        thread_id: str,
        request_id: str | None = None,
    ) -> str:
        raise RuntimeError("internal test failure")

    async def fake_get_workflow():
        return None

    async def fake_close_checkpointer():
        return None

    monkeypatch.setattr(
        "app.api.main.async_run_agent",
        failing_run_agent,
    )
    monkeypatch.setattr(
        "app.api.main.get_workflow",
        fake_get_workflow,
    )
    monkeypatch.setattr(
        "app.api.main.close_checkpointer",
        fake_close_checkpointer,
    )

    with TestClient(app) as client:
        response = client.post(
            "/chat",
            json={
                "message": "触发异常测试",
                "thread_id": "api-error-test",
            },
        )

    assert response.status_code == 500
    assert "internal test failure" not in response.text
    assert response.json()["detail"]
