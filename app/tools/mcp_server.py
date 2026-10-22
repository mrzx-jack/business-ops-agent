
import logging
from typing import Any

from mcp.server.fastmcp import FastMCP

from app.database import repository

from dataclasses import asdict, is_dataclass
from datetime import date, datetime
from enum import Enum
from pathlib import Path

# 使用 logging，不要在 stdio 服务中直接 print，
# 因为标准输出承载 MCP 协议消息。
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("business_ops_mcp")

mcp = FastMCP("business-ops-tools")


def to_jsonable(value: Any) -> Any:
    """将数据库实体和常见 Python 对象转换为 JSON 兼容数据。"""

    if value is None:
        return None

    # Pydantic 模型
    if hasattr(value, "model_dump") and callable(value.model_dump):
        return to_jsonable(value.model_dump(mode="python"))

    # dataclass 实体，例如 Customer、Ticket
    if is_dataclass(value) and not isinstance(value, type):
        return to_jsonable(asdict(value))

    # 枚举
    if isinstance(value, Enum):
        return to_jsonable(value.value)

    # 日期和时间
    if isinstance(value, (datetime, date)):
        return value.isoformat(sep=" ") if isinstance(value, datetime) else value.isoformat()

    # 字典
    if isinstance(value, dict):
        return {
            str(key): to_jsonable(item)
            for key, item in value.items()
        }

    # 列表、元组
    if isinstance(value, (list, tuple)):
        return [to_jsonable(item) for item in value]

    # sqlite3.Row 等支持 keys() 的对象
    if hasattr(value, "keys") and callable(value.keys):
        return {
            str(key): to_jsonable(value[key])
            for key in value.keys()
        }

    # JSON 原生类型
    if isinstance(value, (str, int, float, bool)):
        return value

    # 路径等其他特殊类型
    if isinstance(value, Path):
        return str(value)

    return str(value)


def success_result(message: str, data: Any = None) -> dict:
    return {
        "success": True,
        "message": message,
        "data": to_jsonable(data),
    }


def error_result(message: str, exc: Exception) -> dict:
    logger.exception("%s", message)
    return {
        "success": False,
        "message": message,
        "error_code": type(exc).__name__,
    }


@mcp.tool()
def get_customer(customer_code: str) -> dict:
    """根据客户编号查询客户资料。需要客户编号，例如 CUST001。"""
    try:
        customer = repository.get_customer_by_code(customer_code)

        if customer is None:
            return {
                "success": False,
                "message": f"未找到客户：{customer_code}",
                "error_code": "CUSTOMER_NOT_FOUND",
            }

        return success_result("客户查询成功", customer)

    except Exception as exc:
        return error_result("客户查询失败", exc)


@mcp.tool()
def query_tickets(
    customer_code: str | None = None,
    status: str | None = None,
) -> dict:
    """查询工单，可按客户编号和工单状态筛选；不传参数时查询全部工单。"""
    try:
        tickets = repository.list_tickets(
            customer_code=customer_code,
            status=status,
        )
        return success_result("工单列表查询成功", tickets)

    except Exception as exc:
        return error_result("工单列表查询失败", exc)


@mcp.tool()
def get_ticket(ticket_code: str) -> dict:
    """根据工单编号查询单个工单，例如 TK202610001。"""
    try:
        ticket = repository.get_ticket_by_code(ticket_code)

        if ticket is None:
            return {
                "success": False,
                "message": f"未找到工单：{ticket_code}",
                "error_code": "TICKET_NOT_FOUND",
            }

        return success_result("工单查询成功", ticket)

    except Exception as exc:
        return error_result("工单查询失败", exc)


@mcp.tool()
def create_business_ticket(
    customer_code: str,
    title: str,
    description: str,
    priority: str = "medium",
) -> dict:
    """为指定客户创建业务工单。优先级可使用 low、medium、high、urgent。"""
    try:
        ticket = repository.create_ticket(
            customer_code=customer_code,
            title=title,
            description=description,
            priority=priority,
        )
        return success_result("工单创建成功", ticket)

    except (ValueError, LookupError) as exc:
        # 业务校验失败：返回可理解的错误，不让整个 Agent 崩溃
        return {
            "success": False,
            "message": str(exc),
            "error_code": type(exc).__name__,
        }

    except Exception as exc:
        return error_result("工单创建失败", exc)


if __name__ == "__main__":
    logger.info("Starting business-ops MCP server")
    mcp.run(transport="stdio")
