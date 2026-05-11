"""家庭组服务 - JSON 文件存储"""
import json
import os
import random
import time
import uuid
from datetime import datetime

from server.config import settings
from server.models.group import Group


class GroupService:
    """家庭组服务"""

    def __init__(self):
        self._groups_dir = settings.group_data_dir
        os.makedirs(self._groups_dir, exist_ok=True)
        self._groups_file = os.path.join(self._groups_dir, "groups.json")
        self._groups: dict[str, Group] = {}
        self._load_groups()

    def _load_groups(self):
        """从 JSON 文件加载所有组到内存"""
        if os.path.exists(self._groups_file):
            try:
                with open(self._groups_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                for g in data:
                    group = Group(**g)
                    self._groups[group.group_id] = group
            except (json.JSONDecodeError, KeyError):
                self._groups = {}

    def _save_groups(self):
        """将内存中所有组写入 JSON 文件"""
        data = [g.model_dump(mode="json") for g in self._groups.values()]
        with open(self._groups_file, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def _generate_group_number(self) -> str:
        """生成唯一的 9 位纯数字组号（含查重）"""
        existing_numbers = {g.group_number for g in self._groups.values()}
        for _ in range(1000):
            number = f"{random.randint(100000000, 999999999)}"
            if number not in existing_numbers:
                return number
        # 极端情况：千次随机全部冲突，使用时间戳后缀保底
        ts = int(time.time()) % 100000000
        return f"{ts:09d}"

    async def create(self, owner_id: str, group_name: str) -> Group:
        """创建家庭组"""
        group = Group(
            group_id=str(uuid.uuid4()),
            group_number=self._generate_group_number(),
            group_name=group_name,
            owner_id=owner_id,
            member_ids=[],
            created_at=datetime.now(),
            updated_at=datetime.now(),
        )
        self._groups[group.group_id] = group
        self._save_groups()
        return group

    async def get(self, group_id: str) -> Group | None:
        """获取组"""
        return self._groups.get(group_id)

    async def get_by_number(self, group_number: str) -> Group | None:
        """通过组号获取"""
        for g in self._groups.values():
            if g.group_number == group_number:
                return g
        return None

    async def get_by_owner(self, owner_id: str) -> list[Group]:
        """获取用户创建的所有组"""
        return [g for g in self._groups.values() if g.owner_id == owner_id]

    async def update(self, group: Group) -> Group:
        """更新组"""
        group.updated_at = datetime.now()
        self._groups[group.group_id] = group
        self._save_groups()
        return group

    async def delete(self, group_id: str) -> bool:
        """删除组"""
        if group_id in self._groups:
            del self._groups[group_id]
            self._save_groups()
            return True
        return False

    async def add_member(self, group_id: str, member_id: str) -> Group | None:
        """添加成员到组"""
        group = self._groups.get(group_id)
        if not group:
            return None
        if member_id not in group.member_ids:
            group.member_ids.append(member_id)
            group.updated_at = datetime.now()
            self._save_groups()
        return group

    async def remove_member(self, group_id: str, member_id: str) -> Group | None:
        """从组移除成员"""
        group = self._groups.get(group_id)
        if not group:
            return None
        if member_id in group.member_ids:
            group.member_ids.remove(member_id)
            group.updated_at = datetime.now()
            self._save_groups()
        return group


group_service = GroupService()
