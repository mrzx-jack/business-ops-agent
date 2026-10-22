
import logging
from contextlib import asynccontextmanager
from uuid import uuid4

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from app.agents.workflow import async_run_agent, get_workflow
from app.memory.checkpointer import close_checkpointer

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """管理 Agent 工作流及 Checkpointer 的生命周期。"""
    logger.info("正在初始化业务运营 Agent API")

    try:
        # 初始化并缓存工作流，同时建立 Checkpointer 连接。
        await get_workflow()
        logger.info("业务运营 Agent API 初始化成功")
        yield
    except Exception:
        logger.exception("业务运营 Agent API 初始化或运行失败")
        raise
    finally:
        # 关闭 Checkpointer，避免 SQLite 连接资源泄漏。
        await close_checkpointer()
        logger.info("业务运营 Agent API 已关闭")


app = FastAPI(
    title="智能业务运营与工单处理 Agent API",
    description="通过 HTTP 接口调用基于 LangGraph 和 MCP 的业务运营 Agent。",
    version="1.0.0",
    lifespan=lifespan,
)


class ChatRequest(BaseModel):
    """Agent 对话请求。"""

    message: str = Field(
        ...,
        min_length=1,
        max_length=5000,
        description="用户输入的问题或业务指令",
    )
    thread_id: str = Field(
        ...,
        min_length=1,
        max_length=128,
        description="会话 ID；相同 ID 用于延续同一会话",
    )


class ChatResponse(BaseModel):
    """Agent 对话响应。"""

    request_id: str = Field(..., description="本次请求的唯一标识")
    thread_id: str = Field(..., description="当前会话 ID")
    answer: str = Field(..., description="Agent 返回的回答")


class HealthResponse(BaseModel):
    status: str
    service: str


@app.get("/health", response_model=HealthResponse, tags=["健康检查"])
async def health_check() -> HealthResponse:
    """检查 API 进程是否可以响应请求。"""
    return HealthResponse(
        status="ok",
        service="business-ops-agent",
    )


@app.post("/chat", response_model=ChatResponse, tags=["Agent 对话"])
async def chat(request: ChatRequest) -> ChatResponse:
    """接收用户问题并调用现有 Agent 工作流。"""
    message = request.message.strip()
    thread_id = request.thread_id.strip()

    if not message:
        raise HTTPException(
            status_code=422,
            detail="message 不能为空或仅包含空白字符",
        )

    if not thread_id:
        raise HTTPException(
            status_code=422,
            detail="thread_id 不能为空或仅包含空白字符",
        )

    request_id = uuid4().hex

    logger.info(
        "收到 API 请求 request_id=%s thread_id=%s",
        request_id,
        thread_id,
    )

    try:
        answer = await async_run_agent(
            user_input=message,
            thread_id=thread_id,
            request_id=request_id,
        )

        return ChatResponse(
            request_id=request_id,
            thread_id=thread_id,
            answer=answer,
        )

    except ValueError as exc:
        raise HTTPException(
            status_code=422,
            detail=str(exc),
        ) from exc

    except Exception as exc:
        logger.exception(
            "API 调用 Agent 失败 request_id=%s",
            request_id,
        )
        raise HTTPException(
            status_code=500,
            detail=f"Agent 服务暂时不可用，请提供请求编号：{request_id}",
        ) from exc
