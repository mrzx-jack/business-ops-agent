
import pytest

from app.database.init_db import init_db
from app.database.repository import (
    deactivate_customer_memory,
    list_customer_memories,
    save_customer_memory,
)


@pytest.fixture(autouse=True)
def prepare_database(tmp_path, monkeypatch):
    test_db_path = tmp_path / "test_business_ops.db"
    monkeypatch.setenv("DATABASE_PATH", str(test_db_path))
    init_db()


def test_save_and_list_customer_memory():
    saved = save_customer_memory(
        customer_code="CUST001",
        memory_type="issue_history",
        content="客户曾反馈订单查询接口调用超时。",
        source_ticket_code="TK202610001",
    )

    memories = list_customer_memories("CUST001")

    assert saved["id"] > 0
    assert len(memories) == 1
    assert memories[0]["content"] == "客户曾反馈订单查询接口调用超时。"
    assert memories[0]["source_ticket_code"] == "TK202610001"


def test_memories_are_isolated_by_customer():
    save_customer_memory(
        customer_code="CUST001",
        memory_type="preference",
        content="客户偏好邮件反馈。",
    )

    assert list_customer_memories("CUST002") == []


def test_filter_memories_by_type():
    save_customer_memory(
        customer_code="CUST001",
        memory_type="issue_history",
        content="历史问题记录。",
    )
    save_customer_memory(
        customer_code="CUST001",
        memory_type="preference",
        content="客户偏好记录。",
    )

    memories = list_customer_memories(
        "CUST001",
        memory_type="preference",
    )

    assert len(memories) == 1
    assert memories[0]["memory_type"] == "preference"


def test_deactivate_memory():
    saved = save_customer_memory(
        customer_code="CUST001",
        memory_type="pending_followup",
        content="待确认接口超时问题是否解决。",
    )

    assert deactivate_customer_memory(saved["id"]) is True
    assert list_customer_memories("CUST001") == []

    inactive = list_customer_memories(
        "CUST001",
        include_inactive=True,
    )
    assert len(inactive) == 1
    assert inactive[0]["is_active"] == 0

    assert deactivate_customer_memory(saved["id"]) is False


def test_reject_invalid_memory_type():
    with pytest.raises(ValueError, match="无效的记忆类型"):
        save_customer_memory(
            customer_code="CUST001",
            memory_type="unknown",
            content="测试内容",
        )


def test_reject_empty_memory_content():
    with pytest.raises(ValueError, match="记忆内容不能为空"):
        save_customer_memory(
            customer_code="CUST001",
            memory_type="issue_history",
            content="   ",
        )


def test_reject_memory_for_unknown_customer():
    with pytest.raises(ValueError, match="客户不存在"):
        save_customer_memory(
            customer_code="UNKNOWN",
            memory_type="issue_history",
            content="测试内容",
        )


def test_reject_ticket_belonging_to_another_customer():
    with pytest.raises(ValueError, match="工单不存在或不属于该客户"):
        save_customer_memory(
            customer_code="CUST001",
            memory_type="resolution",
            content="不应该关联到其他客户的工单。",
            source_ticket_code="TK202610003",
        )


def test_reject_invalid_limit():
    with pytest.raises(ValueError, match="limit 必须在 1 到 100 之间"):
        list_customer_memories("CUST001", limit=0)
