
import os
import sqlite3
from pathlib import Path


# 项目根目录：business-ops-agent/
PROJECT_ROOT = Path(__file__).resolve().parents[2]

# 默认数据库存放在项目根目录的 data/ 下
DEFAULT_DATABASE_PATH = PROJECT_ROOT / "data" / "business_ops.db"


def get_database_path() -> Path:
    """获取数据库路径，优先使用环境变量配置。"""
    configured_path = os.getenv("DATABASE_PATH")

    if configured_path:
        path = Path(configured_path)
        if not path.is_absolute():
            path = PROJECT_ROOT / path
    else:
        path = DEFAULT_DATABASE_PATH

    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def get_connection() -> sqlite3.Connection:
    """创建并返回一个 SQLite 数据库连接。"""
    database_path = get_database_path()

    conn = sqlite3.connect(
        str(database_path),
        timeout=10,
    )
    conn.row_factory = sqlite3.Row

    # 开启外键约束，防止工单关联不存在的客户
    conn.execute("PRAGMA foreign_keys = ON")

    return conn
