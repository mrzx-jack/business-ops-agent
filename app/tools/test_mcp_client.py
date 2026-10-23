
import asyncio
import os
from pathlib import Path

from dotenv import load_dotenv
from langchain_mcp_adapters.client import MultiServerMCPClient

PROJECT_ROOT = Path(__file__).resolve().parents[2]
load_dotenv(PROJECT_ROOT / ".env")

PYTHON_EXE = str(PROJECT_ROOT / ".venv" / "Scripts" / "python.exe")
SERVER_FILE = str(PROJECT_ROOT / "app" / "tools" / "mcp_server.py")


async def main():
    if not Path(PYTHON_EXE).exists():
        raise FileNotFoundError(
            f"未找到项目虚拟环境 Python：{PYTHON_EXE}"
        )

    if not Path(SERVER_FILE).exists():
        raise FileNotFoundError(
            f"未找到 MCP Server：{SERVER_FILE}"
        )

    # stdio 会启动一个独立 Python 子进程。
    # 将必要环境变量传给子进程，确保它能访问 .env 中的数据库配置。
    server_env = {
        key: value
        for key, value in os.environ.items()
        if key in {
            "PATH",
            "SYSTEMROOT",
            "WINDIR",
            "TEMP",
            "TMP",
            "DATABASE_PATH",
            "LOG_LEVEL",
        }
    }

    client = MultiServerMCPClient(
        {
            "business_ops": {
                "transport": "stdio",
                "command": PYTHON_EXE,
                "args": ["-u", "-m", "app.tools.mcp_server"],
                "cwd": str(PROJECT_ROOT),
                "env": server_env,
            }
        }
    )

    print("\n========== 1. 发现 MCP 工具 ==========")
    tools = await client.get_tools()

    for tool in tools:
        print(f"- {tool.name}: {tool.description}")

    tool_map = {tool.name: tool for tool in tools}

    expected_tools = {
        "get_customer",
        "query_tickets",
        "get_ticket",
        "create_business_ticket",
        "save_customer_memory",
        "query_customer_memories",
        "deactivate_customer_memory",
    }

    missing_tools = expected_tools - set(tool_map)
    if missing_tools:
        raise RuntimeError(
            f"MCP 工具缺失：{sorted(missing_tools)}"
        )

    print("\n========== 2. 查询客户 ==========")
    customer_result = await tool_map["get_customer"].ainvoke(
        {"customer_code": "CUST001"}
    )
    print(customer_result)

    print("\n========== 3. 查询客户工单 ==========")
    tickets_result = await tool_map["query_tickets"].ainvoke(
        {"customer_code": "CUST001"}
    )
    print(tickets_result)

    print("\n========== 4. 查询单个工单 ==========")
    ticket_result = await tool_map["get_ticket"].ainvoke(
        {"ticket_code": "TK202610001"}
    )
    print(ticket_result)

    print("\n========== 5. 测试不存在的客户 ==========")
    missing_customer_result = await tool_map["get_customer"].ainvoke(
        {"customer_code": "CUST999"}
    )
    print(missing_customer_result)

    print("\n========== 6. 保存长期记忆 ==========")
    memory_result = await tool_map["save_customer_memory"].ainvoke(
        {
            "customer_code": "CUST001",
            "memory_type": "preference",
            "content": "MCP 长期记忆工具接入验证，测试后停用。",
        }
    )
    print(memory_result)

    # MCP 工具返回的是结构化结果，解析出记忆 ID 后继续验证。
    import json

    def parse_tool_result(result):
        if isinstance(result, dict):
            return result

        if isinstance(result, str):
            return json.loads(result)

        if isinstance(result, list):
            for item in result:
                if isinstance(item, dict) and "text" in item:
                    try:
                        return json.loads(item["text"])
                    except (ValueError, TypeError):
                        continue

        raise RuntimeError(f"无法解析 MCP 工具结果：{result!r}")

    parsed_memory = parse_tool_result(memory_result)

    if not parsed_memory.get("success"):
        raise RuntimeError(f"记忆保存失败：{parsed_memory}")

    memory_id = parsed_memory["data"]["id"]

    print("\n========== 7. 查询长期记忆 ==========")
    query_result = await tool_map["query_customer_memories"].ainvoke(
        {
            "customer_code": "CUST001",
            "memory_type": "preference",
        }
    )
    print(query_result)

    parsed_query = parse_tool_result(query_result)

    if not parsed_query.get("success"):
        raise RuntimeError(f"记忆查询失败：{parsed_query}")

    if not any(
        item["id"] == memory_id
        for item in parsed_query["data"]
    ):
        raise RuntimeError("未能查询到刚刚保存的长期记忆")

    print("\n========== 8. 停用测试记忆 ==========")
    deactivate_result = await tool_map[
        "deactivate_customer_memory"
    ].ainvoke({"memory_id": memory_id})
    print(deactivate_result)

    parsed_deactivate = parse_tool_result(deactivate_result)

    if not parsed_deactivate.get("success"):
        raise RuntimeError(f"记忆停用失败：{parsed_deactivate}")

    print("\n长期记忆 MCP 工具验证通过。")

    print("\n========== MCP Client 测试完成 ==========")


if __name__ == "__main__":
    asyncio.run(main())
