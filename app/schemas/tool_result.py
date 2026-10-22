
from typing import Any

from pydantic import BaseModel, Field


class ToolResult(BaseModel):
    """供业务工具适配层和未来 MCP 层使用的统一结果结构。"""

    success: bool
    message: str
    data: Any = None
    error_code: str | None = None


def normalize_tool_result(raw: dict) -> dict:
    """将现有业务工具返回值转换为统一结果结构。"""
    success = bool(raw.get("success", True))

    if "message" in raw:
        message = str(raw["message"])
    else:
        message = "操作成功" if success else "操作失败"

    reserved_keys = {
        "success",
        "message",
        "error_code",
    }

    data = {
        key: value
        for key, value in raw.items()
        if key not in reserved_keys
    }

    result = ToolResult(
        success=success,
        message=message,
        data=data or None,
        error_code=raw.get("error_code"),
    )

    return result.model_dump(exclude_none=True)
