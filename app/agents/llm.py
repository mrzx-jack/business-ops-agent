
import os

from dotenv import load_dotenv
from langchain_openai import ChatOpenAI


# 加载项目根目录中的 .env 文件
load_dotenv()


def get_llm() -> ChatOpenAI:
    """创建通义千问模型客户端。"""
    api_key = os.getenv("DASHSCOPE_API_KEY")
    model = os.getenv("QWEN_MODEL", "qwen-plus")
    base_url = os.getenv(
        "QWEN_BASE_URL",
        "https://dashscope.aliyuncs.com/compatible-mode/v1",
    )

    if not api_key:
        raise RuntimeError(
            "未配置 DASHSCOPE_API_KEY，请检查项目根目录下的 .env 文件。"
        )

    return ChatOpenAI(
        model=model,
        api_key=api_key,
        base_url=base_url,
        temperature=0,
        timeout=30,
        max_retries=2,
    )
