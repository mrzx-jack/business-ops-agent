
import os
import sys
from pathlib import Path

from dotenv import load_dotenv
from langchain_mcp_adapters.client import MultiServerMCPClient


PROJECT_ROOT = Path(__file__).resolve().parents[2]
load_dotenv(PROJECT_ROOT / ".env")

SERVER_FILE = PROJECT_ROOT / "app" / "tools" / "mcp_server.py"

EXPECTED_TOOLS = {
    "get_customer",
    "query_tickets",
    "get_ticket",
    "create_business_ticket",
}

_client: MultiServerMCPClient | None = None
_tools: list | None = None


def _build_server_env() -> dict[str, str]:
    """构建 MCP Server 子进程需要的环境变量。"""
    allowed_keys = {
        "PATH",
        "SYSTEMROOT",
        "WINDIR",
        "TEMP",
        "TMP",
        "HOME",
        "DATABASE_PATH",
        "LOG_LEVEL",
    }

    return {
        key: value
        for key, value in os.environ.items()
        if key in allowed_keys
    }


async def get_mcp_client() -> MultiServerMCPClient:
    """获取进程内复用的 MCP Client。"""
    global _client

    if _client is not None:
        return _client

    python_exe = Path(sys.executable)

    if not python_exe.exists():
        raise FileNotFoundError(
            f"未找到当前 Python 解释器：{python_exe}"
        )

    if not SERVER_FILE.exists():
        raise FileNotFoundError(
            f"未找到 MCP Server：{SERVER_FILE}"
        )

    _client = MultiServerMCPClient(
        {
            "business_ops": {
                "transport": "stdio",
                "command": sys.executable,
                "args": [
                    "-u",
                    "-m",
                    "app.tools.mcp_server",
                ],
                "cwd": str(PROJECT_ROOT),
                "env": _build_server_env(),
            }
        }
    )

    return _client


async def get_mcp_tools() -> list:
    """加载并缓存 MCP Server 暴露的业务工具。"""
    global _tools

    if _tools is not None:
        return _tools

    client = await get_mcp_client()
    tools = await client.get_tools()

    tool_map = {tool.name: tool for tool in tools}
    missing_tools = EXPECTED_TOOLS - set(tool_map)

    if missing_tools:
        raise RuntimeError(
            f"MCP 工具缺失：{sorted(missing_tools)}"
        )

    _tools = tools
    return _tools
