"""Agent 状态模型 - 新增记忆字段"""
from typing import TypedDict, Any
from server.models.conversation import IntentType


class AgentState(TypedDict, total=False):
    """Agent 状态"""

    # 用户信息
    user_id: str
    conversation_id: str | None

    # 家庭组/成员信息
    group_id: str | None
    member_id: str | None
    member_profile: str | None

    # 对话
    messages: list[dict[str, str]]

    # 意图
    intent: IntentType | None
    intent_confidence: float | None

    # 上下文
    context: dict[str, Any]

    # 检索结果
    search_results: list[dict[str, Any]] | None
    retrieved_docs: list[str] | None
    user_memory_results: list[dict[str, Any]] | None

    # 记忆
    short_term_history: list[dict[str, str]]
    user_long_term_context: str | None

    # 分析结果
    analysis_result: dict[str, Any] | None

    # 响应
    response: str | None
    suggestions: list[str]

    # 错误
    error: str | None

    # 追踪
    trace_id: str | None

    # 内存控制标记
    _memory_loaded: bool
    _memory_updated: bool
