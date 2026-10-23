
import asyncio

from app.memory.checkpointer import (
    close_checkpointer,
    get_checkpoint_database_path,
    get_checkpointer,
)


async def main():
    try:
        saver = await get_checkpointer()

        print("异步 Checkpointer 初始化成功")
        print(f"数据库路径：{get_checkpoint_database_path()}")
        print(f"类型：{type(saver).__name__}")

        # 再次获取应当复用同一个实例。
        saver_again = await get_checkpointer()

        assert saver is saver_again
        print("实例复用验证成功")

    finally:
        await close_checkpointer()


if __name__ == "__main__":
    asyncio.run(main())
