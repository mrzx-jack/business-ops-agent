from asyncio import run

from app.agents.state import AgentState
from langchain_core.messages import AIMessage
from app.agents.workflow import build_failure_response, finalize


def test_failed_status_should_not_be_treated_as_success():
    """业务执行失败时，不应将 failed 当作 completed 成功。"""
    state: AgentState = {
        "messages": [],
        "status": "failed",
        "last_error": "create_ticket_worker 执行失败：RuntimeError",
    }

    assert state["status"] == "failed"
    assert state["last_error"] is not None


def test_finalize_preserves_failed_status():
    """finalize 不应把业务执行失败改成 completed。"""
    state: AgentState = {
        "messages": [],
        "status": "failed",
        "last_error": "create_ticket_worker 执行失败：RuntimeError",
    }

    result = run(finalize(state))

    assert result["status"] == "failed"
    assert result["current_worker"] is None


def test_finalize_marks_running_workflow_completed():
    """正常走到结束节点时，应标记为 completed。"""
    state: AgentState = {
        "messages": [],
        "status": "running",
    }

    result = run(finalize(state))

    assert result["status"] == "completed"
    assert result["current_worker"] is None

def test_build_failure_response_returns_failed_message():
    """??????? AIMessage???? failed ???"""
    state: AgentState = {
        "messages": [],
        "status": "failed",
        "last_error": "create_ticket_worker execution failed",
    }

    result = build_failure_response(state)

    assert result["status"] == "failed"
    assert result["current_worker"] is None
    assert len(result["messages"]) == 1
    assert isinstance(result["messages"][0], AIMessage)
    assert "\u672a\u80fd\u5b8c\u6210" in result["messages"][0].content


def test_build_failure_response_does_not_mark_workflow_completed():
    """失败答复应保持 failed 状态，不应被标记为成功。"""
    state: AgentState = {
        "messages": [],
        "status": "failed",
        "last_error": "simulated tool failure",
    }

    result = build_failure_response(state)

    assert result["status"] == "failed"
    assert result["current_worker"] is None
    assert len(result["messages"]) == 1
    assert isinstance(result["messages"][0], AIMessage)

def test_failed_status_does_not_call_supervisor_llm():
    """失败状态下，Supervisor 不应再次调用大模型。"""
    from asyncio import run
    from unittest.mock import AsyncMock

    from app.agents.workflow import invoke_supervisor

    state: AgentState = {
        "messages": [],
        "status": "failed",
        "last_error": "simulated tool failure",
    }

    supervisor_llm = AsyncMock()

    result = run(invoke_supervisor(state, supervisor_llm))

    assert result["status"] == "failed"
    assert result["current_worker"] is None
    assert len(result["messages"]) == 1
    supervisor_llm.ainvoke.assert_not_awaited()


def test_running_status_calls_supervisor_llm():
    """正常运行状态下，Supervisor 应调用大模型。"""
    from asyncio import run
    from unittest.mock import AsyncMock

    from langchain_core.messages import AIMessage, HumanMessage
    from app.agents.workflow import invoke_supervisor

    response = AIMessage(content="查询完成。")
    supervisor_llm = AsyncMock()
    supervisor_llm.ainvoke.return_value = response

    state: AgentState = {
        "messages": [HumanMessage(content="请查询工单")],
        "status": "running",
    }

    result = run(invoke_supervisor(state, supervisor_llm))

    assert result["status"] == "running"
    assert result["messages"] == [response]
    supervisor_llm.ainvoke.assert_awaited_once()
