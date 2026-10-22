
import asyncio

from app.tools.mcp_client import get_mcp_tools


async def main():
    print("========== 加载 MCP 工具 ==========")

    tools = await get_mcp_tools()

    for tool in tools:
        print(f"- {tool.name}: {tool.description}")

    tool_map = {tool.name: tool for tool in tools}

    print("\n========== 查询客户 CUST001 ==========")

    result = await tool_map["get_customer"].ainvoke(
        {"customer_code": "CUST001"}
    )
    print(result)

    print("\n========== 查询客户工单 ==========")

    result = await tool_map["query_tickets"].ainvoke(
        {"customer_code": "CUST001"}
    )
    print(result)

    print("\nMCP 模块验证完成。")


if __name__ == "__main__":
    asyncio.run(main())
