
import asyncio

import pytest
from langchain_core.messages import AIMessage, HumanMessage
from langchain_core.tools import tool
from langgraph.checkpoint.memory import InMemorySaver

import app.agents.workflow as workflow_module
import app.memory.checkpointer as checkpointer_module

@tool
async def get_customer(customer_id: str) -> str:
    """查询客户信息。"""
    if customer_id == "FAIL":
        raise RuntimeError("模拟客户服务异常")
    return f"客户编号：{customer_id}，客户状态：正常"

@tool
async def query_customer_memories(customer_id: str) -> str:
    """查询客户的长期记忆。"""
    return f"客户 {customer_id} 暂无长期记忆"

@tool
async def query_tickets(customer_id: str) -> str:
    """查询客户工单列表。"""
    return f"客户 {customer_id} 的工单列表"


@tool
async def get_ticket(ticket_id: str) -> str:
    """查询指定工单详情。"""
    return f"工单编号：{ticket_id}"


@tool
async def create_business_ticket(
    customer_id: str,
    title: str,
    description: str,
) -> str:
    """创建业务工单。"""
    return f"工单创建成功：{title}"



class FakeLLM:
    """用于测试的模型替身，记录每次调用收到的消息。"""

    def __init__(self, responses):
        self.responses = list(responses)
        self.call_count = 0
        self.received_messages = []

    def bind_tools(self, tools, **kwargs):
        return self

    async def ainvoke(self, messages):
        self.call_count += 1
        self.received_messages.append(list(messages))

        if not self.responses:
            raise AssertionError("模型调用次数超出预期")

        return self.responses.pop(0)



def make_tool_call(customer_id: str) -> AIMessage:
    return AIMessage(
        content="",
        tool_calls=[
            {
                "name": "get_customer",
                "args": {"customer_id": customer_id},
                "id": "call-customer-001",
                "type": "tool_call",
            }
        ],
    )



async def setup_workflow(monkeypatch, fake_llm, checkpointer=None):
    """使用模拟工具、模型和可复用的内存检查点构建工作流。"""

    async def fake_get_mcp_tools():
        return [
            get_customer,
            query_customer_memories,
            query_tickets,
            get_ticket,
            create_business_ticket,
        ]

    async def fake_get_checkpointer():
        if checkpointer is not None:
            return checkpointer
        return InMemorySaver()

    monkeypatch.setattr(
        workflow_module,
        "get_mcp_tools",
        fake_get_mcp_tools,
    )
    monkeypatch.setattr(
        workflow_module,
        "get_llm",
        lambda: fake_llm,
    )
    monkeypatch.setattr(
        workflow_module,
        "get_checkpointer",
        fake_get_checkpointer,
    )

    monkeypatch.setattr(workflow_module, "_workflow", None)
    monkeypatch.setattr(
        workflow_module,
        "_workflow_lock",
        asyncio.Lock(),
    )

    return await workflow_module.get_workflow()



def test_workflow_executes_customer_tool_successfully(monkeypatch):
    """验证模型调用工具、Worker 执行、Supervisor 最终答复的完整路径。"""

    fake_llm = FakeLLM(
        [
            make_tool_call("C001"),
            AIMessage(content="客户 C001 查询完成，状态正常。"),
        ]
    )

    async def scenario():
        workflow = await setup_workflow(monkeypatch, fake_llm)

        result = await workflow.ainvoke(
            {
                "messages": [
                    HumanMessage(content="请查询客户 C001 的信息")
                ],
                "request_id": "test-success-001",
                "status": "running",
                "completed_steps": [],
                "last_error": None,
            },
            config={
                "configurable": {
                    "thread_id": "test-success-001",
                }
            },
        )

        return result

    result = asyncio.run(scenario())

    assert result["status"] == "completed"
    assert "customer_worker" in result["completed_steps"]
    assert isinstance(result["messages"][-1], AIMessage)
    assert result["messages"][-1].content == (
        "客户 C001 查询完成，状态正常。"
    )
    assert fake_llm.call_count == 2


def test_workflow_preserves_failed_status_when_tool_raises(monkeypatch):
    """验证工具异常不会被误报为成功，并且失败后不会再次调用模型。"""

    fake_llm = FakeLLM([make_tool_call("FAIL")])

    async def scenario():
        workflow = await setup_workflow(monkeypatch, fake_llm)

        result = await workflow.ainvoke(
            {
                "messages": [
                    HumanMessage(content="请查询客户 FAIL 的信息")
                ],
                "request_id": "test-failure-001",
                "status": "running",
                "completed_steps": [],
                "last_error": None,
            },
            config={
                "configurable": {
                    "thread_id": "test-failure-001",
                }
            },
        )

        return result

    result = asyncio.run(scenario())

    assert result["status"] == "failed"
    assert result["last_error"] is not None
    assert "customer_worker" not in result["completed_steps"]
    assert isinstance(result["messages"][-1], AIMessage)
    assert "未能完成" in result["messages"][-1].content
    assert fake_llm.call_count == 1


def test_workflow_preserves_messages_across_turns(monkeypatch):
    """同一个 thread_id 的第二轮调用应包含第一轮对话历史。"""

    fake_llm = FakeLLM(
        [
            AIMessage(content="第一轮：客户 C001 的状态正常。"),
            AIMessage(content="第二轮：根据前文，客户编号是 C001。"),
        ]
    )

    async def scenario():
        shared_checkpointer = InMemorySaver()
        workflow = await setup_workflow(
            monkeypatch,
            fake_llm,
            checkpointer=shared_checkpointer,
        )

        config = {
            "configurable": {
                "thread_id": "memory-test-shared",
            }
        }

        first_result = await workflow.ainvoke(
            {
                "messages": [
                    HumanMessage(content="请查询客户 C001")
                ],
                "request_id": "memory-turn-1",
                "status": "running",
                "completed_steps": [],
                "last_error": None,
            },
            config=config,
        )

        second_result = await workflow.ainvoke(
            {
                "messages": [
                    HumanMessage(content="那这个客户的编号是什么？")
                ],
                "request_id": "memory-turn-2",
                "status": "running",
                "completed_steps": [],
                "last_error": None,
            },
            config=config,
        )

        return first_result, second_result

    first_result, second_result = asyncio.run(scenario())

    assert first_result["status"] == "completed"
    assert second_result["status"] == "completed"

    second_call_messages = fake_llm.received_messages[1]
    message_contents = [
        message.content
        for message in second_call_messages
        if hasattr(message, "content")
    ]

    assert "请查询客户 C001" in message_contents
    assert "第一轮：客户 C001 的状态正常。" in message_contents
    assert "那这个客户的编号是什么？" in message_contents

    assert second_result["messages"][-1].content == (
        "第二轮：根据前文，客户编号是 C001。"
    )


def test_workflow_isolates_different_threads(monkeypatch):
    """不同 thread_id 的对话历史不应互相混入。"""

    fake_llm = FakeLLM(
        [
            AIMessage(content="会话 A 的回答。"),
            AIMessage(content="会话 B 的回答。"),
        ]
    )

    async def scenario():
        shared_checkpointer = InMemorySaver()
        workflow = await setup_workflow(
            monkeypatch,
            fake_llm,
            checkpointer=shared_checkpointer,
        )

        for thread_id, user_text, request_id in [
            ("memory-thread-A", "这是会话 A 的秘密内容", "thread-A"),
            ("memory-thread-B", "这是会话 B 的独立问题", "thread-B"),
        ]:
            await workflow.ainvoke(
                {
                    "messages": [HumanMessage(content=user_text)],
                    "request_id": request_id,
                    "status": "running",
                    "completed_steps": [],
                    "last_error": None,
                },
                config={
                    "configurable": {
                        "thread_id": thread_id,
                    }
                },
            )

    asyncio.run(scenario())

    second_call_messages = fake_llm.received_messages[1]
    second_call_contents = [
        message.content
        for message in second_call_messages
        if hasattr(message, "content")
    ]

    assert "这是会话 B 的独立问题" in second_call_contents
    assert "这是会话 A 的秘密内容" not in second_call_contents
    assert "会话 A 的回答。" not in second_call_contents


def test_sqlite_checkpointer_restores_history_after_reinitialization(
    monkeypatch,
    tmp_path,
):
    """重建工作流并重新打开 SQLite 后，同一会话仍能恢复历史。"""

    fake_llm = FakeLLM(
        [
            AIMessage(content="第一轮：客户 C001 的状态正常。"),
            AIMessage(content="第二轮：根据历史记录，客户编号是 C001。"),
        ]
    )

    async def scenario():
        database_path = tmp_path / "agent_checkpoints.db"

        # 使用 pytest 临时目录，避免污染项目中的真实数据库。
        monkeypatch.setenv(
            "CHECKPOINT_DATABASE_PATH",
            str(database_path),
        )

        # 清理可能残留的模块级 Checkpointer 状态。
        await checkpointer_module.close_checkpointer()

        async def fake_get_mcp_tools():
            return [
                get_customer,
                query_customer_memories,
                query_tickets,
                get_ticket,
                create_business_ticket,
            ]

        monkeypatch.setattr(
            workflow_module,
            "get_mcp_tools",
            fake_get_mcp_tools,
        )
        monkeypatch.setattr(
            workflow_module,
            "get_llm",
            lambda: fake_llm,
        )
        monkeypatch.setattr(
            workflow_module,
            "get_checkpointer",
            checkpointer_module.get_checkpointer,
        )

        thread_id = "sqlite-persistence-test"
        config = {
            "configurable": {
                "thread_id": thread_id,
            }
        }

        try:
            # 第一阶段：使用 SQLite 保存第一轮对话。
            monkeypatch.setattr(workflow_module, "_workflow", None)
            monkeypatch.setattr(
                workflow_module,
                "_workflow_lock",
                asyncio.Lock(),
            )

            first_workflow = await workflow_module.get_workflow()

            first_result = await first_workflow.ainvoke(
                {
                    "messages": [
                        HumanMessage(content="请查询客户 C001")
                    ],
                    "request_id": "sqlite-turn-1",
                    "status": "running",
                    "completed_steps": [],
                    "last_error": None,
                },
                config=config,
            )

            assert first_result["status"] == "completed"
            assert database_path.exists()

            # 关闭 SQLite 连接，模拟资源重新初始化。
            await checkpointer_module.close_checkpointer()

            # 第二阶段：重新打开同一个数据库并构建新工作流。
            monkeypatch.setattr(workflow_module, "_workflow", None)
            monkeypatch.setattr(
                workflow_module,
                "_workflow_lock",
                asyncio.Lock(),
            )

            second_workflow = await workflow_module.get_workflow()

            second_result = await second_workflow.ainvoke(
                {
                    "messages": [
                        HumanMessage(
                            content="那这个客户的编号是什么？"
                        )
                    ],
                    "request_id": "sqlite-turn-2",
                    "status": "running",
                    "completed_steps": [],
                    "last_error": None,
                },
                config=config,
            )

            assert second_result["status"] == "completed"

            second_call_messages = fake_llm.received_messages[1]
            message_contents = [
                message.content
                for message in second_call_messages
                if hasattr(message, "content")
            ]

            assert "请查询客户 C001" in message_contents
            assert "第一轮：客户 C001 的状态正常。" in message_contents
            assert "那这个客户的编号是什么？" in message_contents

        finally:
            await checkpointer_module.close_checkpointer()
            monkeypatch.setattr(workflow_module, "_workflow", None)

    asyncio.run(scenario())

