
from typing import Literal
from typing_extensions import TypedDict

from langgraph.graph import MessagesState


ExecutionStatus = Literal[
    "running",
    "completed",
    "failed",
]


class AgentState(MessagesState, total=False):
    """Agent 工作流的运行状态。"""

    request_id: str
    status: ExecutionStatus
    current_worker: str
    completed_steps: list[str]
    last_error: str | None
