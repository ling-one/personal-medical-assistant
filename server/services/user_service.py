"""用户管理服务 - JSON 文件存储"""
import json
import os
import uuid
import time
from typing import Any

from server.config import settings

# 会话超时时间（秒）：30分钟
SESSION_TIMEOUT = 1800


class UserService:
    """用户管理服务"""

    def __init__(self):
        self._users_dir = settings.user_data_dir
        os.makedirs(self._users_dir, exist_ok=True)

    def _user_path(self, user_id: str) -> str:
        return os.path.join(self._users_dir, f"{user_id}.json")

    def create_user(self, user_id: str | None = None) -> dict[str, Any]:
        """创建新用户"""
        if user_id is None:
            user_id = f"user_{uuid.uuid4().hex[:12]}"

        path = self._user_path(user_id)
        if os.path.exists(path):
            raise ValueError(f"用户 {user_id} 已存在")

        user_data = {
            "user_id": user_id,
            "created_at": time.time(),
            "last_active": time.time(),
            "last_conversation_id": None,
        }

        with open(path, "w", encoding="utf-8") as f:
            json.dump(user_data, f, ensure_ascii=False, indent=2)

        # 初始化用户向量索引目录
        self._ensure_user_vector_dir(user_id)

        return user_data

    def get_user(self, user_id: str) -> dict[str, Any] | None:
        """获取用户信息"""
        path = self._user_path(user_id)
        if not os.path.exists(path):
            return None
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data

    def user_exists(self, user_id: str) -> bool:
        """检查用户是否存在"""
        return os.path.exists(self._user_path(user_id))

    def get_or_create_conversation_id(self, user_id: str) -> str:
        """
        获取或创建对话ID：
        - 如果用户有未超时的最近对话，复用该对话ID
        - 否则生成新的对话ID
        """
        path = self._user_path(user_id)
        if not os.path.exists(path):
            return str(uuid.uuid4())

        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)

        now = time.time()
        last_active = data.get("last_active", 0)
        last_conversation_id = data.get("last_conversation_id")

        # 判断会话是否超时
        if last_conversation_id and (now - last_active) < SESSION_TIMEOUT:
            conversation_id = last_conversation_id
        else:
            conversation_id = str(uuid.uuid4())

        # 更新活跃时间和对话ID
        data["last_active"] = now
        data["last_conversation_id"] = conversation_id
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

        return conversation_id

    def update_last_active(self, user_id: str):
        """更新用户最后活跃时间（防止会话超时）"""
        path = self._user_path(user_id)
        if not os.path.exists(path):
            return
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        data["last_active"] = time.time()
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def _ensure_user_vector_dir(self, user_id: str):
        """确保用户向量索引目录存在"""
        path = os.path.join(settings.vector_store_dir, f"user_{user_id}")
        os.makedirs(path, exist_ok=True)


user_service = UserService()
