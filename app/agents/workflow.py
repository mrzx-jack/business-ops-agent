
import asyncio
import logging
import time
from uuid import uuid4

from langchain_core.messages import (
    AIMessage,
    HumanMessage,
    SystemMessage,
    ToolMessage,
)
from langgraph.graph import END, START, StateGraph
from langgraph.prebuilt import ToolNode

from app.agents.llm import get_llm
from app.agents.logging_config import setup_logging
from app.agents.state import AgentState
from app.memory.checkpointer import get_checkpointer
from app.tools.mcp_client import get_mcp_tools


setup_logging()
logger = logging.getLogger(__name__)


SYSTEM_PROMPT = """
你是企业智能业务运营与工单处理系统的 Supervisor，负责理解用户需求，
选择合适的业务工具，并根据工具返回的真实结果组织回答。

你可以使用以下 MCP 业务工具：
1. get_customer：查询客户信息。
2. query_tickets：查询工单列表，可按客户编号、工单状态筛选。
3. get_ticket：查询指定工单详情。
4. create_business_ticket：创建业务工单。

工作规则：
1. 必须依据工具返回的数据回答，不得编造客户、工单或业务状态。
2. 用户使用“这个客户”“他的工单”“刚才那张工单”等指代时，
   应结合当前会话历史理解。
3. 创建工单前，必须确认客户编号、标题和问题描述等必要信息。
4. 只有用户明确要求创建、提交或登记工单时，才允许调用创建工单工具。
5. 工具返回业务错误时，向用户解释原因，不要伪造成功结果。
6. 避免重复调用已经明确失败的工具。
7. 回答应简洁、清楚，优先使用中文。
8. 查询工单时，以工具返回的数据为准；无法确认总数时，不要自行推算。
9. 如果工具执行失败，应明确告知用户本次操作未能完成。
"""


TOOL_NODE_NAMES = {
    "get_customer": "customer_worker",
    "query_tickets": "ticket_worker",
    "get_ticket": "ticket_worker",
    "create_business_ticket": "create_ticket_worker",
}

# 使用稳定的唯一 Worker 名称，避免重复添加图边。
WORKER_NAMES = tuple(dict.fromkeys(TOOL_NODE_NAMES.values()))

_workflow = None
_workflow_lock = asyncio.Lock()


async def get_workflow():
    """异步初始化并缓存 LangGraph 工作流。"""
    global _workflow

    if _workflow is not None:
        return _workflow

    async with _workflow_lock:
        if _workflow is not None:
            return _workflow

        tools = await get_mcp_tools()
        tool_map = {tool.name: tool for tool in tools}

        missing = set(TOOL_NODE_NAMES) - set(tool_map)
        if missing:
            raise RuntimeError(f"缺少必要的 MCP 工具：{sorted(missing)}")

        selected_tools = [
            tool_map[name]
            for name in TOOL_NODE_NAMES
        ]

        supervisor_llm = get_llm().bind_tools(
            selected_tools,
            parallel_tool_calls=False,
        )

        async def supervisor(state: AgentState) -> dict:
            """分析当前消息，决定调用业务工具或直接回答。"""
            messages = [
                SystemMessage(content=SYSTEM_PROMPT),
                *state["messages"],
            ]

            response = await supervisor_llm.ainvoke(messages)
            tool_calls = getattr(response, "tool_calls", []) or []

            current_worker = None

            if tool_calls:
                tool_name = tool_calls[0]["name"]
                current_worker = TOOL_NODE_NAMES.get(tool_name)

                if current_worker is None:
                    logger.warning(
                        "模型请求了未知工具 tool_name=%s request_id=%s",
                        tool_name,
                        state.get("request_id", "unknown"),
                    )

            return {
                "messages": [response],
                "current_worker": current_worker,
                "status": "running",
            }

        def route_from_supervisor(state: AgentState) -> str:
            """根据 Supervisor 的输出决定下一节点。"""
            messages = state.get("messages", [])

            if not messages:
                return END

            last_message = messages[-1]

            if isinstance(last_message, AIMessage):
                tool_calls = getattr(last_message, "tool_calls", []) or []

                if tool_calls:
                    tool_name = tool_calls[0]["name"]
                    worker_name = TOOL_NODE_NAMES.get(tool_name)

                    if worker_name:
                        return worker_name

                    logger.warning(
                        "无法路由模型请求的工具 tool_name=%s",
                        tool_name,
                    )

            return END

        async def make_worker(
            tool_names: list[str],
            worker_name: str,
        ):
            """创建一个执行 MCP 工具的异步 Worker。"""
            tool_node = ToolNode(
                [tool_map[name] for name in tool_names],
                handle_tool_errors=True,
            )

            async def worker(state: AgentState) -> dict:
                started = time.perf_counter()
                request_id = state.get("request_id", "unknown")

                try:
                    result = await tool_node.ainvoke(state)
                    elapsed = round(time.perf_counter() - started, 3)

                    logger.info(
                        "MCP Worker 执行结束 request_id=%s "
                        "worker=%s elapsed=%s",
                        request_id,
                        worker_name,
                        elapsed,
                    )

                    completed_steps = list(
                        state.get("completed_steps", [])
                    )
                    completed_steps.append(worker_name)

                    return {
                        **result,
                        "current_worker": worker_name,
                        "completed_steps": completed_steps,
                        "status": "running",
                        "last_error": None,
                    }

                except Exception as exc:
                    elapsed = round(time.perf_counter() - started, 3)

                    logger.exception(
                        "MCP Worker 执行异常 request_id=%s "
                        "worker=%s elapsed=%s",
                        request_id,
                        worker_name,
                        elapsed,
                    )

                    messages = state.get("messages", [])
                    last_message = messages[-1] if messages else None
                    tool_calls = getattr(
                        last_message,
                        "tool_calls",
                        [],
                    ) or []

                    error_messages = [
                        ToolMessage(
                            content=(
                                "工具执行失败，请向用户说明本次操作未能完成，"
                                "不要声称操作成功。"
                            ),
                            tool_call_id=call["id"],
                        )
                        for call in tool_calls
                        if call.get("name") in tool_names
                    ]

                    result = {
                        "current_worker": worker_name,
                        "status": "failed",
                        "last_error": (
                            f"{worker_name} 执行失败："
                            f"{type(exc).__name__}"
                        ),
                    }

                    if error_messages:
                        result["messages"] = error_messages

                    return result

            return worker

        async def finalize(state: AgentState) -> dict:
            """
            结束当前工作流。

            completed 表示工作流已走到最终答复阶段，
            不代表所有业务操作都成功。
            """
            if state.get("status") == "failed":
                logger.warning(
                    "工作流结束时存在失败状态 request_id=%s error=%s",
                    state.get("request_id", "unknown"),
                    state.get("last_error"),
                )

            return {
                "status": "completed",
                "current_worker": None,
            }

        builder = StateGraph(AgentState)

        builder.add_node("supervisor", supervisor)

        customer_worker = await make_worker(
            ["get_customer"],
            "customer_worker",
        )

        ticket_worker = await make_worker(
            ["query_tickets", "get_ticket"],
            "ticket_worker",
        )

        create_ticket_worker = await make_worker(
            ["create_business_ticket"],
            "create_ticket_worker",
        )

        builder.add_node("customer_worker", customer_worker)
        builder.add_node("ticket_worker", ticket_worker)
        builder.add_node("create_ticket_worker", create_ticket_worker)
        builder.add_node("finalize", finalize)

        builder.add_edge(START, "supervisor")

        builder.add_conditional_edges(
            "supervisor",
            route_from_supervisor,
            {
                "customer_worker": "customer_worker",
                "ticket_worker": "ticket_worker",
                "create_ticket_worker": "create_ticket_worker",
                END: "finalize",
            },
        )

        for worker_name in WORKER_NAMES:
            builder.add_edge(worker_name, "supervisor")

        builder.add_edge("finalize", END)

        checkpointer = await get_checkpointer()
        _workflow = builder.compile(checkpointer=checkpointer)

        logger.info(
            "LangGraph 工作流初始化成功，已接入 MCP 工具：%s",
            sorted(TOOL_NODE_NAMES),
        )

        return _workflow


async def async_run_agent(
    user_input: str,
    thread_id: str,
    request_id: str | None = None,
) -> str:
    """异步执行 Agent，适用于 FastAPI 等异步应用。"""
    if not isinstance(user_input, str) or not user_input.strip():
        raise ValueError("user_input 不能为空。")

    if not isinstance(thread_id, str) or not thread_id.strip():
        raise ValueError("thread_id 不能为空。")

    request_id = request_id or uuid4().hex
    started = time.perf_counter()

    config = {
        "configurable": {
            "thread_id": thread_id,
        },
        "metadata": {
            "request_id": request_id,
            "thread_id": thread_id,
        },
        "tags": [
            "business-ops-agent",
            "stage-7-mcp",
        ],
        "recursion_limit": 15,
    }

    try:
        workflow = await get_workflow()

        result = await workflow.ainvoke(
            {
                "messages": [
                    HumanMessage(content=user_input.strip()),
                ],
                "request_id": request_id,
                "status": "running",
                "completed_steps": [],
                "last_error": None,
            },
            config=config,
        )

        logger.info(
            "Agent 状态调试 request_id=%s keys=%s "
            "status=%s completed_steps=%s message_count=%s",
            request_id,
            list(result.keys()),
            result.get("status"),
            result.get("completed_steps"),
            len(result.get("messages", [])),
        )

        messages = result.get("messages", [])

        for message in reversed(messages):
            if (
                isinstance(message, AIMessage)
                and not getattr(message, "tool_calls", [])
            ):
                elapsed = round(time.perf_counter() - started, 3)

                logger.info(
                    "Agent 执行结束 request_id=%s status=%s "
                    "elapsed=%s steps=%s",
                    request_id,
                    result.get("status"),
                    elapsed,
                    result.get("completed_steps", []),
                )

                return str(message.content)

        logger.warning(
            "Agent 未找到最终答复 request_id=%s",
            request_id,
        )

        return "本次未能生成明确答复，请补充问题或稍后重试。"

    except Exception:
        logger.exception(
            "Agent 执行异常 request_id=%s",
            request_id,
        )
        raise



def run_agent(
    user_input: str,
    thread_id: str,
    request_id: str | None = None,
) -> str:
    """
    同步兼容入口。

    适用于没有运行事件循环的同步脚本。
    异步应用应直接调用 await async_run_agent(...)。
    """
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(
            async_run_agent(
                user_input=user_input,
                thread_id=thread_id,
                request_id=request_id,
            )
        )

    raise RuntimeError(
        "当前事件循环已经运行，请在异步代码中使用 "
        "await async_run_agent(...)。"
    )
