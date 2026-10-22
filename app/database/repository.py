
from typing import Optional
from uuid import uuid4

from app.database.connection import get_connection
from app.database.models import Customer, Ticket


def _to_customer(row) -> Optional[Customer]:
    if row is None:
        return None
    return Customer(**dict(row))


def _to_ticket(row) -> Optional[Ticket]:
    if row is None:
        return None
    return Ticket(**dict(row))


def get_customer_by_code(customer_code: str) -> Optional[Customer]:
    """按客户编号查询客户。"""
    conn = get_connection()
    try:
        row = conn.execute(
            """
            SELECT id, customer_code, name, email, level,
                   service_status, created_at
            FROM customers
            WHERE customer_code = ?
            """,
            (customer_code,),
        ).fetchone()

        return _to_customer(row)
    finally:
        conn.close()


def get_customer_by_id(customer_id: int) -> Optional[Customer]:
    """按数据库主键查询客户。"""
    conn = get_connection()
    try:
        row = conn.execute(
            """
            SELECT id, customer_code, name, email, level,
                   service_status, created_at
            FROM customers
            WHERE id = ?
            """,
            (customer_id,),
        ).fetchone()

        return _to_customer(row)
    finally:
        conn.close()


def list_tickets(
    customer_code: Optional[str] = None,
    status: Optional[str] = None,
) -> list[Ticket]:
    """查询工单，可按客户编号和工单状态筛选。"""
    conn = get_connection()
    try:
        sql = """
            SELECT t.id, t.ticket_code, t.customer_id, t.title,
                   t.description, t.priority, t.status, t.resolution,
                   t.created_at, t.updated_at
            FROM tickets AS t
            JOIN customers AS c ON c.id = t.customer_id
            WHERE 1 = 1
        """
        params = []

        if customer_code is not None:
            sql += " AND c.customer_code = ?"
            params.append(customer_code)

        if status is not None:
            sql += " AND t.status = ?"
            params.append(status)

        sql += " ORDER BY t.created_at DESC, t.id DESC"

        rows = conn.execute(sql, params).fetchall()
        return [_to_ticket(row) for row in rows]
    finally:
        conn.close()


def get_ticket_by_code(ticket_code: str) -> Optional[Ticket]:
    """按工单编号查询工单。"""
    conn = get_connection()
    try:
        row = conn.execute(
            """
            SELECT id, ticket_code, customer_id, title, description,
                   priority, status, resolution, created_at, updated_at
            FROM tickets
            WHERE ticket_code = ?
            """,
            (ticket_code,),
        ).fetchone()

        return _to_ticket(row)
    finally:
        conn.close()


def create_ticket(
    customer_code: str,
    title: str,
    description: str,
    priority: str = "medium",
) -> Ticket:
    """为指定客户创建工单。"""
    allowed_priorities = {"low", "medium", "high", "urgent"}

    if priority not in allowed_priorities:
        raise ValueError(
            f"无效的工单优先级：{priority}"
        )

    if not title.strip():
        raise ValueError("工单标题不能为空")

    if not description.strip():
        raise ValueError("工单描述不能为空")

    conn = get_connection()

    try:
        with conn:
            customer = conn.execute(
                """
                SELECT id, service_status
                FROM customers
                WHERE customer_code = ?
                """,
                (customer_code,),
            ).fetchone()

            if customer is None:
                raise ValueError(f"客户不存在：{customer_code}")

            if customer["service_status"] != "active":
                raise ValueError("客户当前服务状态异常，不能创建工单")

            ticket_code = f"TK-{uuid4().hex[:12].upper()}"

            cursor = conn.execute(
                """
                INSERT INTO tickets (
                    ticket_code, customer_id, title, description,
                    priority, status
                )
                VALUES (?, ?, ?, ?, ?, 'open')
                """,
                (
                    ticket_code,
                    customer["id"],
                    title.strip(),
                    description.strip(),
                    priority,
                ),
            )

            ticket_id = cursor.lastrowid

        ticket = get_ticket_by_code(ticket_code)
        if ticket is None:
            raise RuntimeError(f"工单创建后无法查询：{ticket_id}")

        return ticket
    finally:
        conn.close()


def update_ticket_status(
    ticket_code: str,
    new_status: str,
    resolution: Optional[str] = None,
) -> Ticket:
    """更新工单状态，必要时记录处理结果。"""
    allowed_statuses = {
        "open", "in_progress", "resolved", "closed"
    }

    if new_status not in allowed_statuses:
        raise ValueError(f"无效的工单状态：{new_status}")

    conn = get_connection()
    try:
        with conn:
            row = conn.execute(
                "SELECT id FROM tickets WHERE ticket_code = ?",
                (ticket_code,),
            ).fetchone()

            if row is None:
                raise ValueError(f"工单不存在：{ticket_code}")

            conn.execute(
                """
                UPDATE tickets
                SET status = ?,
                    resolution = COALESCE(?, resolution),
                    updated_at = CURRENT_TIMESTAMP
                WHERE ticket_code = ?
                """,
                (new_status, resolution, ticket_code),
            )

        ticket = get_ticket_by_code(ticket_code)
        if ticket is None:
            raise RuntimeError(f"工单更新后无法查询：{ticket_code}")

        return ticket
    finally:
        conn.close()
