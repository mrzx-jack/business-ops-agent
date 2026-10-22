
import asyncio
from uuid import uuid4

from app.agents.workflow import async_run_agent
from app.memory.checkpointer import close_checkpointer


async def main():
    thread_id = f"mcp-test-{uuid4().hex[:8]}"

    test_cases = [
        "帮我查询客户编号 CUST001 的客户信息。",
        "查询一下这个客户的工单。",
        "查询工单 TK202610001 的详细信息。",
    ]

    try:
        for index, question in enumerate(test_cases, start=1):
            print("\n" + "=" * 60)
            print(f"测试 {index}: {question}")
            print("-" * 60)

            answer = await async_run_agent(
                user_input=question,
                thread_id=thread_id,
            )

            print("Agent 回答：")
            print(answer)

    finally:
        await close_checkpointer()


if __name__ == "__main__":
    asyncio.run(main())
