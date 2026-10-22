
from dataclasses import dataclass
from typing import Optional


@dataclass
class Customer:
    id: int
    customer_code: str
    name: str
    email: str
    level: str
    service_status: str
    created_at: str


@dataclass
class Ticket:
    id: int
    ticket_code: str
    customer_id: int
    title: str
    description: str
    priority: str
    status: str
    resolution: Optional[str]
    created_at: str
    updated_at: str
