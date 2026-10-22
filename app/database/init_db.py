
from app.database.connection import get_connection


def init_db() -> None:
    """创建数据库表，并插入初始模拟数据。"""
    conn = get_connection()

    try:
        with conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS customers (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    customer_code TEXT NOT NULL UNIQUE,
                    name TEXT NOT NULL,
                    email TEXT NOT NULL,
                    level TEXT NOT NULL
                        CHECK (level IN ('standard', 'premium', 'enterprise')),
                    service_status TEXT NOT NULL DEFAULT 'active'
                        CHECK (service_status IN ('active', 'suspended')),
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                );

                CREATE TABLE IF NOT EXISTS tickets (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    ticket_code TEXT NOT NULL UNIQUE,
                    customer_id INTEGER NOT NULL,
                    title TEXT NOT NULL,
                    description TEXT NOT NULL,
                    priority TEXT NOT NULL DEFAULT 'medium'
                        CHECK (priority IN ('low', 'medium', 'high', 'urgent')),
                    status TEXT NOT NULL DEFAULT 'open'
                        CHECK (status IN (
                            'open', 'in_progress', 'resolved', 'closed'
                        )),
                    resolution TEXT,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (customer_id)
                        REFERENCES customers(id)
                );
                """
            )

            customer_count = conn.execute(
                "SELECT COUNT(*) FROM customers"
            ).fetchone()[0]

            if customer_count == 0:
                conn.executemany(
                    """
                    INSERT INTO customers (
                        customer_code, name, email, level, service_status
                    )
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    [
                        (
                            "CUST001",
                            "星河科技",
                            "contact@xinghe.example",
                            "enterprise",
                            "active",
                        ),
                        (
                            "CUST002",
                            "远山贸易",
                            "support@yuanshan.example",
                            "premium",
                            "active",
                        ),
                        (
                            "CUST003",
                            "晨光零售",
                            "it@chenguang.example",
                            "standard",
                            "suspended",
                        ),
                    ],
                )

            ticket_count = conn.execute(
                "SELECT COUNT(*) FROM tickets"
            ).fetchone()[0]

            if ticket_count == 0:
                customer_ids = {
                    row["customer_code"]: row["id"]
                    for row in conn.execute(
                        "SELECT id, customer_code FROM customers"
                    ).fetchall()
                }

                conn.executemany(
                    """
                    INSERT INTO tickets (
                        ticket_code, customer_id, title, description,
                        priority, status, resolution
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    [
                        (
                            "TK202610001",
                            customer_ids["CUST001"],
                            "API 接口调用超时",
                            "调用订单查询接口时频繁出现超时。",
                            "high",
                            "open",
                            None,
                        ),
                        (
                            "TK202610002",
                            customer_ids["CUST001"],
                            "数据同步延迟",
                            "订单数据同步至业务平台存在延迟。",
                            "medium",
                            "in_progress",
                            None,
                        ),
                        (
                            "TK202610003",
                            customer_ids["CUST002"],
                            "账号登录异常",
                            "部分员工登录业务系统失败。",
                            "urgent",
                            "resolved",
                            "已重置相关账号状态并验证登录。",
                        ),
                    ],
                )

        print("数据库初始化成功。")

    finally:
        conn.close()


if __name__ == "__main__":
    init_db()
