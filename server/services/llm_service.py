"""LLM 服务"""
import os
import json
import logging
from typing import Any

from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, SystemMessage, AIMessage

from server.config import settings
from server.services.trace_service import trace_service

logger = logging.getLogger(__name__)


class LLMService:
    """大语言模型服务 (小米大模型 / OpenAI 兼容)"""

    def __init__(self):
        self._client: ChatOpenAI | None = None
        self._langfuse: Any = None
        self._prompt_cache: dict[str, str] = {}

    def _init_langfuse_prompts(self):
        """初始化 Langfuse Prompt 客户端"""
        if self._langfuse is not None:
            return
        try:
            from langfuse import Langfuse
            secret_key = os.getenv("LANGFUSE_SECRET_KEY")
            public_key = os.getenv("LANGFUSE_PUBLIC_KEY")
            base_url = os.getenv("LANGFUSE_BASE_URL", "http://localhost:3000")
            if secret_key and public_key:
                self._langfuse = Langfuse(
                    secret_key=secret_key,
                    public_key=public_key,
                    host=base_url,
                )
                logger.info("Langfuse Prompt 客户端已初始化")
        except Exception as e:
            logger.warning("Langfuse Prompt 初始化失败（将使用本地 fallback）: %s", e)

    def get_prompt(self, name: str, version: int | None = None) -> str | None:
        """从 Langfuse 获取 prompt 模板文本，失败返回 None"""
        cache_key = f"{name}:{version or 'latest'}"
        cached = self._prompt_cache.get(cache_key)
        if cached is not None:
            return cached

        self._init_langfuse_prompts()
        if self._langfuse is None:
            return None

        try:
            prompt = self._langfuse.get_prompt(name, version=version, cache_ttl_seconds=60)
            prompt_text = prompt.prompt
            self._prompt_cache[cache_key] = prompt_text
            logger.info("从 Langfuse 获取 prompt '%s' 成功", name)
            return prompt_text
        except Exception as e:
            logger.warning("获取 Langfuse prompt '%s' 失败: %s（使用本地 fallback）", name, e)
            return None

    def format_prompt(self, name: str, fallback: str, **variables) -> str:
        """从 Langfuse 获取 prompt 并用变量格式化，失败则使用 fallback。
        
        用法: llm_service.format_prompt("classify_prompt", CLASSIFY_PROMPT, message=...)
        """
        prompt_text = self.get_prompt(name)
        if prompt_text is None:
            prompt_text = fallback
        return prompt_text.format(**variables)
    
    @property
    def client(self) -> ChatOpenAI:
        """获取 LLM 客户端"""
        if self._client is None:
            api_key: str | None = settings.llm_api_key or os.getenv("LLM_API_KEY")
            self._client = ChatOpenAI(
                api_key=api_key,
                base_url=settings.llm_base_url,
                model=settings.llm_model,
                temperature=settings.llm_temperature,
                max_tokens=settings.llm_max_tokens,  # pyright: ignore[reportCallIssue]
            )
        return self._client
    
    def _create_langfuse_generation(
        self,
        input_text: str,
        output_text: str,
        model: str | None = None,
        usage: dict[str, int] | None = None,
    ):
        """手动创建 Langfuse Generation（SDK v4 API）"""
        trace_service.create_generation(
            input_text=input_text,
            output_text=output_text,
            model=model,
            usage=usage,
        )
    
    async def chat(
        self,
        messages: list[dict[str, str]],
        system: str | None = None,
        **kwargs
    ) -> str:
        """聊天"""
        langchain_messages: list[Any] = []
        
        # 添加系统消息
        if system:
            langchain_messages.append(SystemMessage(content=system))  
        
        # 添加对话历史
        for msg in messages:
            if msg["role"] == "user":
                langchain_messages.append(HumanMessage(content=msg["content"]))
            elif msg["role"] == "assistant":
                langchain_messages.append(AIMessage(content=msg["content"]))
        
        response = await self.client.agenerate([langchain_messages])
        result_text = response.generations[0][0].text

        # 手动上报到 Langfuse
        input_text = "\n".join(f"{m.type}: {m.content}" for m in langchain_messages)
        usage_dict = {}
        if hasattr(response, "llm_output") and response.llm_output:
            tok = response.llm_output.get("token_usage", {})
            if tok:
                usage_dict = {
                    "prompt_tokens": tok.get("prompt_tokens", 0),
                    "completion_tokens": tok.get("completion_tokens", 0),
                    "total_tokens": tok.get("total_tokens", 0),
                }
        self._create_langfuse_generation(
            input_text=input_text,
            output_text=result_text,
            model=response.llm_output.get("model_name") if response.llm_output else None,
            usage=usage_dict,
        )

        return result_text
    
    async def chat_stream(
        self,
        messages: list[dict[str, str]],
        system: str | None = None,
    ):
        """流式聊天"""
        langchain_messages = []
        
        if system:
            langchain_messages.append(SystemMessage(content=system))
        
        for msg in messages:
            if msg["role"] == "user":
                langchain_messages.append(HumanMessage(content=msg["content"]))
            elif msg["role"] == "assistant":
                langchain_messages.append(AIMessage(content=msg["content"]))
        
        full_content = ""
        async for chunk in self.client.astream(langchain_messages):
            yield chunk.content
            full_content += chunk.content

        # 流式结束后上报到 Langfuse
        if full_content:
            input_text = "\n".join(f"{m.type}: {m.content}" for m in langchain_messages)
            self._create_langfuse_generation(
                input_text=input_text,
                output_text=full_content,
            )
    
    async def extract_structured(
        self,
        prompt: str,
        schema: type,
        system: str | None = None
    ) -> dict[str, Any]:
        """结构化提取 (使用 LLM + Pydantic)"""
        full_prompt = f"""{prompt}

请以 JSON 格式返回结果，包含以下字段：
{schema.__doc__ or ''}
"""
        
        response = await self.chat(
            messages=[{"role": "user", "content": full_prompt}],
            system=system
        )
        
        # 简单解析 JSON
        import json
        try:
            return json.loads(response)
        except:
            return {}


llm_service = LLMService()
