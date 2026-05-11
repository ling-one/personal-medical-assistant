"""流式队列管理器 — 支持 SSE 逐 token 推送"""
import asyncio
from typing import Optional


class StreamManager:
    """管理每个 conversation 的流式队列"""

    def __init__(self):
        self._queues: dict[str, asyncio.Queue] = {}

    def create_queue(self, conversation_id: str) -> asyncio.Queue:
        queue: asyncio.Queue = asyncio.Queue(maxsize=1024)
        self._queues[conversation_id] = queue
        return queue

    def get_queue(self, conversation_id: str) -> Optional[asyncio.Queue]:
        return self._queues.get(conversation_id)

    def remove_queue(self, conversation_id: str):
        self._queues.pop(conversation_id, None)


stream_manager = StreamManager()
