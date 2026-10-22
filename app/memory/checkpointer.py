
import os
from contextlib import AsyncExitStack
from pathlib import Path

from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CHECKPOINT_DB_PATH = PROJECT_ROOT / "data" / "agent_checkpoints.db"


def get_checkpoint_database_path() -> Path:
    """获取 Checkpointer 数据库路径，优先使用环境变量配置。"""
    configured_path = os.getenv("CHECKPOINT_DATABASE_PATH")

    if configured_path:
        path = Path(configured_path)
        if not path.is_absolute():
            path = PROJECT_ROOT / path
    else:
        path = DEFAULT_CHECKPOINT_DB_PATH

    path.parent.mkdir(parents=True, exist_ok=True)
    return path


_exit_stack: AsyncExitStack | None = None
checkpointer: AsyncSqliteSaver | None = None


async def get_checkpointer() -> AsyncSqliteSaver:
    """异步初始化并复用 SQLite Checkpointer。"""
    global _exit_stack, checkpointer

    if checkpointer is not None:
        return checkpointer

    checkpoint_db_path = get_checkpoint_database_path()
    exit_stack = AsyncExitStack()

    try:
        saver = await exit_stack.enter_async_context(
            AsyncSqliteSaver.from_conn_string(
                str(checkpoint_db_path)
            )
        )

        await saver.setup()

        _exit_stack = exit_stack
        checkpointer = saver

        return saver

    except Exception:
        await exit_stack.aclose()
        raise


async def close_checkpointer() -> None:
    """关闭 SQLite Checkpointer 并释放数据库连接。"""
    global _exit_stack, checkpointer

    if _exit_stack is not None:
        await _exit_stack.aclose()

    _exit_stack = None
    checkpointer = None
