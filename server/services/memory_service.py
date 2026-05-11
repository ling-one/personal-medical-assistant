"""对话记忆服务 - 短期记忆管理（每用户独立）"""
import time
from typing import Any
from dataclasses import dataclass, field


@dataclass
class MemoryItem:
    """记忆项"""
    content: str
    role: str
    timestamp: float
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "content": self.content,
            "role": self.role,
            "timestamp": self.timestamp,
            "metadata": self.metadata,
        }


class ShortTermMemory:
    """短期记忆 - 最近 N 轮对话"""

    def __init__(self, max_turns: int = 10):
        self.max_turns = max_turns
        self._messages: list[MemoryItem] = []

    def add(self, content: str, role: str, metadata: dict[str, Any] | None = None) -> None:
        """添加消息"""
        self._messages.append(MemoryItem(
            content=content,
            role=role,
            timestamp=time.time(),
            metadata=metadata or {},
        ))
        # 限制长度：移除最早的消息对
        while len(self._messages) > self.max_turns * 2:
            self._messages.pop(0)

    def get_messages(self, max_tokens: int = 4000) -> list[dict[str, str]]:
        """获取格式化的消息列表（用于 LLM），最近的消息在后"""
        messages = []
        total_tokens = 0
        # 从最早到最新遍历
        for item in self._messages:
            tokens = len(item.content) // 4
            if total_tokens + tokens > max_tokens:
                break
            messages.append({"role": item.role, "content": item.content})
            total_tokens += tokens
        return messages

    def get_history_context(self, max_tokens: int = 2000) -> str:
        """获取历史对话文本（用于 prompt 拼接）"""
        parts = []
        total_tokens = 0
        for item in self._messages:
            tokens = len(item.content) // 4
            if total_tokens + tokens > max_tokens:
                break
            label = "用户" if item.role == "user" else "助手"
            parts.append(f"{label}: {item.content}")
            total_tokens += tokens
        return "\n".join(parts)

    @property
    def message_count(self) -> int:
        """当前消息数量"""
        return len(self._messages)

    @property
    def turn_count(self) -> int:
        """当前对话轮次数"""
        return len(self._messages) // 2

    def restore_from_turns(self, turns: list[dict[str, str]]) -> None:
        """从 FAISS 恢复的对话轮次重建短期记忆
        turns: [{"role": "user", "content": "..."}, {"role": "assistant", "content": "..."}, ...]
        """
        self.clear()
        for turn in turns:
            self.add(turn["content"], turn["role"])

    def clear(self):
        """清空短期记忆"""
        self._messages.clear()

    def to_dict(self) -> dict[str, Any]:
        return {
            "max_turns": self.max_turns,
            "message_count": len(self._messages),
            "messages": [m.to_dict() for m in self._messages],
        }


# ===== 全局短期记忆存储（内存，按 conversation_id 隔离） =====
_conversation_short_term_memories: dict[str, ShortTermMemory] = {}


def get_short_memory(conversation_id: str) -> ShortTermMemory:
    """获取或创建指定对话的短期记忆"""
    if conversation_id not in _conversation_short_term_memories:
        _conversation_short_term_memories[conversation_id] = ShortTermMemory(max_turns=10)
    return _conversation_short_term_memories[conversation_id]


def clear_short_memory(conversation_id: str):
    """清除指定对话的短期记忆"""
    if conversation_id in _conversation_short_term_memories:
        _conversation_short_term_memories[conversation_id].clear()
