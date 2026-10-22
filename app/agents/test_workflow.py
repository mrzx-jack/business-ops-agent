
import asyncio

from app.agents.workflow import async_run_agent
from app.memory.checkpointer import close_checkpointer


async def main():
    print("=" * 60)
    print("智能业务运营与工单处理 Agent")
    print("输入 /new 开始新会话，输入 exit 退出")
    print("=" * 60)

    thread_id = input(
        "请输入会话 ID（直接回车使用默认会话 demo-session）："
    ).strip() or "demo-session"

    print(f"\n当前会话 ID：{thread_id}")
    print("若想在程序重启后恢复会话，请再次输入相同 ID。")

    try:
        while True:
            try:
                user_input = input("\n用户：").strip()
            except (EOFError, KeyboardInterrupt):
                print("\n正在退出...")
                break

            if not user_input:
                continue

            if user_input.lower() in {"exit", "quit"}:
                print("已退出。")
                break

            if user_input == "/new":
                thread_id = input("请输入新的会话 ID：").strip()
                if not thread_id:
                    print("会话 ID 不能为空。")
                    thread_id = "demo-session"
                print(f"已切换到会话：{thread_id}")
                continue

            answer = await async_run_agent(
                user_input=user_input,
                thread_id=thread_id,
            )
            print(f"\nAgent：{answer}")

    finally:
        await close_checkpointer()


if __name__ == "__main__":
    asyncio.run(main())
