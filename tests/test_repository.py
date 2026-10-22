
import pytest

from app.database.init_db import init_db
from app.database.repository import (
    create_ticket,
    get_customer_by_code,
    get_ticket_by_code,
    list_tickets,
    update_ticket_status,
)


@pytest.fixture(autouse=True)
def prepare_database():
    # 使用当前开发数据库进行基础验证。
    # 后续会再升级为独立的临时测试数据库。
    init_db()


def test_get_existing_customer():
    customer = get_customer_by_code("CUST001")

    assert customer is not None
    assert customer.name == "星河科技"
    assert customer.level == "enterprise"



def test_list_customer_tickets():
    tickets = list_tickets(customer_code="CUST001")

    ticket_codes = {t.ticket_code for t in tickets}

    # 验证初始化时的两条工单仍然存在
    assert "TK202610001" in ticket_codes
    assert "TK202610002" in ticket_codes
    assert all(t.customer_id > 0 for t in tickets)



def test_create_ticket():
    ticket = create_ticket(
        customer_code="CUST001",
        title="测试工单",
        description="验证工单创建功能",
        priority="high",
    )

    assert ticket.ticket_code.startswith("TK-")
    assert ticket.title == "测试工单"
    assert ticket.status == "open"

    saved_ticket = get_ticket_by_code(ticket.ticket_code)
    assert saved_ticket is not None


def test_update_ticket_status():
    ticket = create_ticket(
        customer_code="CUST001",
        title="状态更新测试",
        description="验证工单状态更新",
    )

    updated = update_ticket_status(
        ticket.ticket_code,
        "resolved",
        resolution="问题已处理",
    )

    assert updated.status == "resolved"
    assert updated.resolution == "问题已处理"


def test_reject_suspended_customer():
    with pytest.raises(ValueError, match="服务状态异常"):
        create_ticket(
            customer_code="CUST003",
            title="暂停服务客户工单",
            description="该操作应该被拒绝",
        )


def test_reject_invalid_priority():
    with pytest.raises(ValueError, match="优先级"):
        create_ticket(
            customer_code="CUST001",
            title="非法优先级测试",
            description="验证参数校验",
            priority="super_urgent",
        )
