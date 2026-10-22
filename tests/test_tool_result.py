
from app.schemas.tool_result import normalize_tool_result


def test_normalize_success_result():
    result = normalize_tool_result(
        {
            "success": True,
            "count": 2,
            "tickets": [
                {"ticket_code": "TK001"},
                {"ticket_code": "TK002"},
            ],
        }
    )

    assert result["success"] is True
    assert result["message"] == "操作成功"
    assert result["data"]["count"] == 2
    assert len(result["data"]["tickets"]) == 2


def test_normalize_failure_result():
    result = normalize_tool_result(
        {
            "success": False,
            "message": "客户不存在",
            "customer": None,
            "error_code": "CUSTOMER_NOT_FOUND",
        }
    )

    assert result["success"] is False
    assert result["message"] == "客户不存在"
    assert result["error_code"] == "CUSTOMER_NOT_FOUND"
    assert result["data"]["customer"] is None
