
from langchain_core.tools import tool

from app.database.repository import (
    list_tickets,
    get_ticket_by_code,
    create_ticket,
)


def _ticket_to_dict(ticket) -> dict:
    """将 Ticket 数据对象转换为可供模型读取的字典。"""
    return {
        "ticket_code": ticket.ticket_code,
        "customer_id": ticket.customer_id,
        "title": ticket.title,
        "description": ticket.description,
        "priority": ticket.priority,
        "status": ticket.status,
        "resolution": ticket.resolution,
        "created_at": ticket.created_at,
        "updated_at": ticket.updated_at,
    }


@tool
def query_tickets(
    customer_code: str | None = None,
    status: str | None = None,
) -> dict:
    """按客户编号和工单状态查询工单列表。

    用户询问某客户的工单、未处理工单、处理中工单或已解决工单时调用。
    customer_code 是可选的客户编号，例如 CUST001。
    status 是可选的状态，只能是 open、in_progress、resolved、closed。
    """
    allowed_statuses = {
        "open",
        "in_progress",
        "resolved",
        "closed",
    }

    if status and status not in allowed_statuses:
        return {
            "success": False,
            "message": f"无效的工单状态：{status}",
            "tickets": [],
        }

    tickets = list_tickets(
        customer_code=customer_code,
        status=status,
    )

    return {
        "success": True,
        "count": len(tickets),
        "tickets": [_ticket_to_dict(ticket) for ticket in tickets],
    }


@tool
def get_ticket(ticket_code: str) -> dict:
    """根据工单编号查询单条工单的详细信息。

    用户明确询问某张工单的详情、处理状态或解决方案时调用。
    ticket_code 例如 TK202610001。
    """
    ticket = get_ticket_by_code(ticket_code)

    if ticket is None:
        return {
            "success": False,
            "message": f"未找到工单：{ticket_code}",
            "ticket": None,
        }

    return {
        "success": True,
        "ticket": _ticket_to_dict(ticket),
    }


@tool
def create_business_ticket(
    customer_code: str,
    title: str,
    description: str,
    priority: str = "medium",
) -> dict:
    """为指定客户创建业务工单。

    只有用户明确要求新建、提交或登记工单时才调用。
    customer_code 是客户编号，例如 CUST001。
    title 是工单标题，description 是问题描述。
    priority 只能是 low、medium、high、urgent。
    不要在用户没有提供足够信息时自行编造客户编号或问题内容。
    """
    try:
        ticket = create_ticket(
            customer_code=customer_code,
            title=title,
            description=description,
            priority=priority,
        )
    except (ValueError, LookupError) as exc:
        return {
            "success": False,
            "message": str(exc),
            "ticket": None,
        }

    return {
        "success": True,
        "message": "工单创建成功",
        "ticket": _ticket_to_dict(ticket),
    }
