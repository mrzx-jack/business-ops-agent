
import json

from langchain_core.messages import HumanMessage, SystemMessage, ToolMessage

from app.agents.llm import get_llm
from app.tools.customer_tools import get_customer


SYSTEM_PROMPT = """
你是企业客户服务助手。

你可以使用 get_customer 工具查询客户信息。
当用户明确询问某个客户的信息时，应优先调用该工具获取真实业务数据。
不要编造客户信息。
如果用户没有提供客户编号，先询问客户编号，不要猜测。
拿到工具返回结果后，再用中文向用户解释查询结果。
"""


def main():
    llm = get_llm()

    # 将 Python 工具的定义提供给模型
    tools = [get_customer]
    llm_with_tools = llm.bind_tools(tools)

    # 建立工具名称到实际 Python 工具的映射
    tool_map = {
        tool.name: tool
        for tool in tools
    }

    messages = [
        SystemMessage(content=SYSTEM_PROMPT),
        HumanMessage(
            content="请查询客户 CUST001 的基本信息，包括等级和服务状态。"
        ),
    ]

    # 最多允许 5 轮模型交互，避免工具调用无限循环
    for step in range(5):
        response = llm_with_tools.invoke(messages)
        messages.append(response)

        if not response.tool_calls:
            print("\n最终回答：")
            print(response.content)
            return

        for tool_call in response.tool_calls:
            tool_name = tool_call["name"]
            tool_args = tool_call["args"]
            tool_call_id = tool_call["id"]

            print(f"\n第 {step + 1} 轮工具调用")
            print("工具名称：", tool_name)
            print("工具参数：", tool_args)

            tool = tool_map.get(tool_name)

            if tool is None:
                result = {
                    "success": False,
                    "message": f"未知工具：{tool_name}",
                }
            else:
                try:
                    result = tool.invoke(tool_args)
                except Exception as exc:
                    # 向模型返回有限、可理解的错误信息。
                    # 生产环境还应记录详细异常日志。
                    result = {
                        "success": False,
                        "message": f"工具执行失败：{type(exc).__name__}",
                    }

            print("工具执行结果：", result)

            messages.append(
                ToolMessage(
                    content=json.dumps(
                        result,
                        ensure_ascii=False,
                        default=str,
                    ),
                    tool_call_id=tool_call_id,
                )
            )

    print("达到最大模型交互轮数，停止执行。")


if __name__ == "__main__":
    main()
