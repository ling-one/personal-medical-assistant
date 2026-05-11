"""对话持久化服务 - 按用户+成员隔离，JSON 文件存储"""
import json
import os
import time
import uuid
from typing import Any

from server.config import settings

# 会话超时时间（秒）：30分钟
SESSION_TIMEOUT = 1800


class ConversationService:
    """对话持久化服务"""

    def __init__(self):
        self._base_dir = os.path.join(settings.user_data_dir, "conversations")
        os.makedirs(self._base_dir, exist_ok=True)

    def _user_index_path(self, user_id: str) -> str:
        return os.path.join(self._base_dir, f"{user_id}_index.json")

    def _conversation_path(self, conversation_id: str) -> str:
        return os.path.join(self._base_dir, f"{conversation_id}.json")

    def _read_json(self, path: str) -> dict[str, Any] | None:
        if not os.path.exists(path):
            return None
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            return None

    def _write_json(self, path: str, data: dict[str, Any]) -> None:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def get_or_create_conversation(self, user_id: str, member_id: str | None = None) -> tuple[str, bool]:
        """
        获取或创建对话。
        按 (user_id, member_id) 隔离，30分钟超时自动创建新对话。
        返回 (conversation_id, is_new)
        """
        index = self._read_json(self._user_index_path(user_id)) or {}
        key = member_id or "__default__"
        now = time.time()

        existing = index.get(key)
        if existing:
            conv_id = existing.get("conversation_id")
            last_active = existing.get("last_active", 0)

            if conv_id and (now - last_active) < SESSION_TIMEOUT:
                conv = self._read_json(self._conversation_path(conv_id))
                if conv is not None:
                    existing["last_active"] = now
                    self._write_json(self._user_index_path(user_id), index)
                    return conv_id, False

        # 创建新对话
        conv_id = str(uuid.uuid4())
        index[key] = {
            "conversation_id": conv_id,
            "member_id": member_id,
            "created_at": now,
            "last_active": now,
        }
        self._write_json(self._user_index_path(user_id), index)

        conv_data = {
            "conversation_id": conv_id,
            "user_id": user_id,
            "member_id": member_id,
            "created_at": now,
            "updated_at": now,
            "messages": [],
        }
        self._write_json(self._conversation_path(conv_id), conv_data)

        return conv_id, True

    def add_message(self, conversation_id: str, role: str, content: str, metadata: dict[str, Any] | None = None) -> None:
        """添加消息到对话"""
        conv = self._read_json(self._conversation_path(conversation_id))
        if conv is None:
            return

        conv["messages"].append({
            "role": role,
            "content": content,
            "timestamp": time.time(),
            "metadata": metadata or {},
        })
        conv["updated_at"] = time.time()
        self._write_json(self._conversation_path(conversation_id), conv)

        # 更新索引活跃时间
        user_id = conv.get("user_id")
        member_id = conv.get("member_id")
        if user_id:
            index = self._read_json(self._user_index_path(user_id)) or {}
            key = member_id or "__default__"
            if key in index and index[key].get("conversation_id") == conversation_id:
                index[key]["last_active"] = time.time()
                self._write_json(self._user_index_path(user_id), index)

    def get_messages(self, conversation_id: str) -> list[dict[str, Any]]:
        """获取对话消息列表（按时间升序）"""
        conv = self._read_json(self._conversation_path(conversation_id))
        if conv is None:
            return []
        return conv.get("messages", [])

    def list_conversations(self, user_id: str) -> list[dict[str, Any]]:
        """列出用户的所有对话（按最近活跃降序）"""
        index = self._read_json(self._user_index_path(user_id)) or {}
        result = []
        for key, info in index.items():
            conv_id = info.get("conversation_id")
            conv = self._read_json(self._conversation_path(conv_id))
            if conv is None:
                continue
            result.append({
                "conversation_id": conv_id,
                "member_id": info.get("member_id"),
                "created_at": info.get("created_at"),
                "last_active": info.get("last_active"),
                "message_count": len(conv.get("messages", [])),
            })
        result.sort(key=lambda x: x.get("last_active", 0), reverse=True)
        return result

    def clear_conversation(self, user_id: str, member_id: str | None = None) -> bool:
        """清除指定成员的对话（删除索引和对话文件）"""
        index = self._read_json(self._user_index_path(user_id)) or {}
        key = member_id or "__default__"

        if key not in index:
            return False

        conv_id = index[key].get("conversation_id")
        if conv_id:
            conv_path = self._conversation_path(conv_id)
            if os.path.exists(conv_path):
                os.remove(conv_path)

        del index[key]
        self._write_json(self._user_index_path(user_id), index)
        return True

    def get_conversation_id_by_member(self, user_id: str, member_id: str | None = None) -> str | None:
        """获取指定成员当前有效的对话ID（未超时）"""
        index = self._read_json(self._user_index_path(user_id)) or {}
        key = member_id or "__default__"
        info = index.get(key)
        if not info:
            return None

        conv_id = info.get("conversation_id")
        last_active = info.get("last_active", 0)
        now = time.time()

        if conv_id and (now - last_active) < SESSION_TIMEOUT:
            if self._read_json(self._conversation_path(conv_id)) is not None:
                return conv_id
        return None

    def conversation_exists(self, conversation_id: str) -> bool:
        """检查对话是否存在"""
        return self._read_json(self._conversation_path(conversation_id)) is not None


conversation_service = ConversationService()
