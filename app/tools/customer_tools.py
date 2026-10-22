
from langchain_core.tools import tool

from app.database.repository import get_customer_by_code


@tool
def get_customer(customer_code: str) -> dict:
    """根据客户编号查询客户基本信息。

    当用户询问客户名称、客户等级、联系方式或服务状态时调用。
    customer_code 必须是已知的客户编号，例如 CUST001。
    """
    customer = get_customer_by_code(customer_code)

    if customer is None:
        return {
            "success": False,
            "message": f"未找到客户：{customer_code}",
            "customer": None,
        }

    return {
        "success": True,
        "message": "客户查询成功",
        "customer": {
            "customer_code": customer.customer_code,
            "name": customer.name,
            "email": customer.email,
            "level": customer.level,
            "service_status": customer.service_status,
        },
    }
