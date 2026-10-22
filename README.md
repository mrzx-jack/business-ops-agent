# 智能业务运营与工单处理 Agent 系统

基于大语言模型的企业业务运营与工单处理 Agent 项目，面向客户服务场景，实现客户信息查询、工单检索、业务工单创建和多轮对话。通过 LangGraph 管理 Agent 工作流，使用 MCP 暴露业务工具，并通过 SQLite 持久化业务数据和会话检查点。

## 一、项目简介

企业客服和运营场景中，用户的问题往往涉及客户信息、历史工单、当前处理状态等多个业务数据源。传统方式需要人工查询不同系统，再汇总信息并执行后续操作。

本项目构建了一个基于 Qwen 的业务处理 Agent，通过 Supervisor 识别用户意图、决定是否调用业务工具，并将工具执行结果组织为自然语言回答。

项目重点实践：

- 基于 LangGraph 的状态化 Agent 工作流与任务路由
- 基于 Function Calling 的工具选择和参数传递
- 基于 MCP 的业务工具封装与调用
- 基于 SQLite 的客户、工单数据管理
- 基于 LangGraph SQLite Checkpointer 的多轮对话状态持久化
- 基于 FastAPI 的 HTTP API 和 Swagger 接口文档
- 基于 Docker Compose 的容器化部署

## 二、核心技术栈

| 类别 | 技术 |
|---|---|
| 开发语言 | Python 3.11 |
| 大语言模型 | 通义千问 Qwen，通过 DashScope 兼容接口调用 |
| Agent 框架 | LangChain、LangGraph |
| 工具调用 | Function Calling、Tool Calling |
| 工具协议 | Model Context Protocol（MCP） |
| 数据校验 | Pydantic |
| 数据存储 | SQLite |
| 后端接口 | FastAPI、Uvicorn |
| 会话状态 | LangGraph Checkpointer、SQLite |
| 部署 | Docker、Docker Compose |
| 测试与调试 | pytest、FastAPI Swagger UI、日志记录 |

## 三、系统架构

```text
用户 / API 客户端
        |
        v
  FastAPI /chat
        |
        v
  LangGraph 工作流
        |
        v
    Supervisor
  理解意图、选择工具
        |
        v
  MCP Client / Tool Router
        |
        v
      MCP Server
        |
        +--> get_customer
        +--> query_tickets
        +--> get_ticket
        +--> create_business_ticket
        |
        v
  SQLite 业务数据库
        |
        v
  工具执行结果返回模型
        |
        v
  生成最终回答并返回 API
```

会话状态由 LangGraph SQLite Checkpointer 独立持久化，通过 `thread_id` 标识对话线程。业务数据和会话检查点使用不同的数据库文件。

## 四、主要功能

### 1. Supervisor-Worker 工作流

Supervisor 结合当前会话消息和用户意图，决定直接回答还是调用业务工具，并根据工具名称将任务路由到对应的 Worker。

当前业务工具包括：

| 工具 | 功能 |
|---|---|
| `get_customer` | 查询客户信息 |
| `query_tickets` | 查询工单列表及状态 |
| `get_ticket` | 查询指定工单详情 |
| `create_business_ticket` | 创建业务工单 |

工具通过 MCP Server 暴露，由 MCP Client 接入 LangGraph 工作流。Worker 负责执行具体工具并返回结果。

### 2. 业务数据管理

使用 SQLite 存储客户和工单数据，通过数据访问层封装查询及写入操作。

支持的典型业务流程包括：

- 查询客户基本信息
- 查询客户的历史工单
- 查询工单详情及处理状态
- 根据用户明确提出的需求创建工单
- 根据工具的真实执行结果反馈处理情况

Agent 的系统提示词要求其依据工具返回的数据回答问题；当必要参数缺失时应追问，不应自行编造业务数据。

### 3. 多轮对话与状态持久化

使用 LangGraph SQLite Checkpointer 保存工作流检查点。

通过相同的 `thread_id` 恢复对应会话的历史状态，使 Agent 能够理解“刚才那张工单”“这个客户”等依赖上下文的表达。

已验证的场景包括：

- 同一会话连续发送多轮请求
- 第二轮对话引用第一轮约定的测试关键词
- 重启 Docker 容器后，使用相同 `thread_id` 恢复此前的会话上下文

当前实现属于会话级状态持久化，不等同于跨用户的长期画像记忆或语义记忆系统。

### 4. FastAPI 接口

项目通过 FastAPI 提供 HTTP 接口。

| 接口 | 用途 |
|---|---|
| `GET /health` | 健康检查 |
| `POST /chat` | Agent 对话入口 |
| `GET /docs` | Swagger 交互式 API 文档 |

`POST /chat` 接收用户消息和会话 ID，返回请求 ID、会话 ID 和 Agent 回答。

## 五、项目目录

```text
business-ops-agent/
├── app/
│   ├── agents/
│   │   ├── llm.py
│   │   ├── state.py
│   │   ├── workflow.py
│   │   ├── logging_config.py
│   │   └── test_*.py
│   ├── api/
│   │   └── main.py
│   ├── database/
│   │   ├── connection.py
│   │   ├── init_db.py
│   │   ├── models.py
│   │   └── repository.py
│   ├── memory/
│   │   └── checkpointer.py
│   ├── schemas/
│   │   └── tool_result.py
│   ├── services/
│   └── tools/
│       ├── customer_tools.py
│       ├── ticket_tools.py
│       ├── mcp_client.py
│       └── mcp_server.py
├── data/
│   ├── business_ops.db
│   └── agent_checkpoints.db
├── tests/
├── .dockerignore
├── .env.example
├── .gitignore
├── Dockerfile
├── docker-compose.yml
├── requirements.txt
└── README.md
```

## 六、本地运行

### 1. 环境要求

- Python 3.11
- 可用的通义千问 API Key
- Git（可选）

### 2. 安装依赖

在项目根目录执行：

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

### 3. 配置环境变量

复制环境变量模板：

```powershell
Copy-Item .env.example .env
```

编辑 `.env`，填写真实的 API Key，并根据项目配置保留模型、数据库等参数。

示例：

```dotenv
DASHSCOPE_API_KEY=替换为自己的API密钥

QWEN_MODEL=qwen-plus
QWEN_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1

DATABASE_PATH=data/business_ops.db
CHECKPOINT_DATABASE_PATH=data/agent_checkpoints.db
```

请勿将真实 API Key 提交到 Git 仓库。

### 4. 启动服务

```powershell
python -m uvicorn app.api.main:app --host 127.0.0.1 --port 8000
```

打开浏览器访问：

- API 文档：`http://127.0.0.1:8000/docs`
- 健康检查：`http://127.0.0.1:8000/health`

注意：如果数据库已经包含业务数据，不要为了启动服务而随意重新初始化数据库或覆盖现有文件。

## 七、Docker 部署

### 1. 环境准备

确保已安装并启动 Docker Desktop。

在项目根目录准备 `.env`，其中包含有效的 `DASHSCOPE_API_KEY` 等配置。

### 2. 启动容器

```powershell
docker compose config --quiet
docker compose up -d --build
```

查看容器状态：

```powershell
docker compose ps
```

查看应用日志：

```powershell
docker compose logs --tail 100 business-ops-agent
```

### 3. 访问服务

- 健康检查：`http://127.0.0.1:8000/health`
- Swagger 文档：`http://127.0.0.1:8000/docs`

### 4. 数据持久化

Docker 部署使用命名卷保存 SQLite 数据，避免容器直接在 Windows 挂载目录中运行 SQLite。

当前 Compose 配置使用已有命名卷：

```yaml
volumes:
  business_ops_data:
    external: true
    name: business-ops-agent_business_ops_data
```

容器中的数据库路径：

```text
/app/data/business_ops.db
/app/data/agent_checkpoints.db
```

业务数据库用于存储客户和工单；检查点数据库用于恢复 LangGraph 会话状态。

注意：

- 命名卷中的数据独立于本地 `data/` 目录。
- 普通容器重启不会删除命名卷数据。
- 不要随意执行 `docker compose down -v`，否则可能删除 Compose 管理的卷。
- 更换部署环境前，应先备份数据库并确认恢复流程。
- `.env` 中的密钥不得打包进镜像或提交到公开仓库。

## 八、API 测试示例

### 1. 多轮对话测试

在 Swagger 的 `POST /chat` 接口中执行请求。

第一轮请求：

```json
{
  "thread_id": "demo-session-001",
  "message": "请记住本次测试关键词是蓝色鲸鱼，暂时不要创建工单。"
}
```

第二轮请求使用相同的 `thread_id`：

```json
{
  "thread_id": "demo-session-001",
  "message": "刚才约定的测试关键词是什么？"
}
```

如果返回的回答能够正确引用第一轮的关键词，则说明当前会话的上下文恢复正常。

还可以重启容器后，再次使用相同的 `thread_id` 进行提问，以验证检查点持久化。

### 2. 业务工具测试

可以在 Swagger 中逐步测试以下场景：

1. 查询指定客户的信息。
2. 查询客户的历史工单及状态。
3. 查询一张具体工单的详情。
4. 在明确提供必要信息并要求创建工单后，验证工单是否写入数据库。
5. 使用工具返回的数据核对 Agent 的最终回答。

建议先使用测试数据进行写入操作，避免在验证时误创建实际业务工单。

## 九、测试与验证

项目包含工作流、MCP、模型连接及 Checkpointer 相关测试脚本，并使用 FastAPI 测试接口。

已实际验证的部署结果：

- Docker 镜像构建成功，容器能够启动。
- MCP Server 正常启动，四个业务工具成功加载。
- `/health` 和 `/docs` 可以正常访问。
- 业务数据库迁移后通过 SQLite