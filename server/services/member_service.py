"""成员服务 - JSON 文件存储"""
import json
import os
import uuid
from datetime import datetime

from server.config import settings
from server.models.member import Member
from server.models.profile import MedicalHistory, VitalSigns


class MemberService:
    """成员服务"""

    def __init__(self):
        self._members_dir = settings.member_data_dir
        os.makedirs(self._members_dir, exist_ok=True)
        self._members: dict[str, Member] = {}
        self._load_members()

    def _load_members(self):
        """从文件加载所有成员到内存"""
        if not os.path.exists(self._members_dir):
            return
        for filename in os.listdir(self._members_dir):
            if filename.endswith(".json"):
                path = os.path.join(self._members_dir, filename)
                try:
                    with open(path, "r", encoding="utf-8") as f:
                        data = json.load(f)
                    member = Member(**data)
                    self._members[member.member_id] = member
                except (json.JSONDecodeError, KeyError):
                    continue

    def _member_path(self, member_id: str) -> str:
        """成员 JSON 文件路径"""
        return os.path.join(self._members_dir, f"{member_id}.json")

    def _save_member(self, member: Member):
        """保存单个成员到文件"""
        path = self._member_path(member.member_id)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(member.model_dump(mode="json"), f, ensure_ascii=False, indent=2)

    def _delete_member_file(self, member_id: str):
        """删除成员文件"""
        path = self._member_path(member_id)
        if os.path.exists(path):
            os.remove(path)

    async def create(self, group_id: str, data: dict) -> Member:
        """创建成员"""
        member = Member(
            member_id=str(uuid.uuid4()),
            group_id=group_id,
            name=data["name"],
            relationship=data["relationship"],
            gender=data["gender"],
            birth_date=data["birth_date"],
            height=data.get("height"),
            weight=data.get("weight"),
            medical_history=data.get("medical_history", MedicalHistory()),
            vital_signs=data.get("vital_signs"),
            created_at=datetime.now(),
            updated_at=datetime.now(),
        )
        self._members[member.member_id] = member
        self._save_member(member)
        return member

    async def get(self, member_id: str) -> Member | None:
        """获取成员"""
        return self._members.get(member_id)

    async def update(self, member_id: str, data: dict) -> Member | None:
        """更新成员"""
        member = self._members.get(member_id)
        if not member:
            return None
        for key, value in data.items():
            if value is not None and hasattr(member, key):
                setattr(member, key, value)
        member.updated_at = datetime.now()
        self._save_member(member)
        return member

    async def delete(self, member_id: str) -> bool:
        """删除成员"""
        if member_id in self._members:
            del self._members[member_id]
            self._delete_member_file(member_id)
            return True
        return False

    async def get_by_group(self, group_id: str) -> list[Member]:
        """获取组的所有成员"""
        return [m for m in self._members.values() if m.group_id == group_id]

    async def update_medical_history(self, member_id: str, medical_history: MedicalHistory) -> Member | None:
        """更新病史"""
        member = self._members.get(member_id)
        if not member:
            return None
        member.medical_history = medical_history
        member.updated_at = datetime.now()
        self._save_member(member)
        return member

    async def update_vital_signs(self, member_id: str, vital_signs: VitalSigns) -> Member | None:
        """更新生命体征"""
        member = self._members.get(member_id)
        if not member:
            return None
        member.vital_signs = vital_signs
        member.updated_at = datetime.now()
        self._save_member(member)
        return member

    def to_summary_text(self, member: Member) -> str:
        """生成成员健康档案摘要文本（供 Agent 注入）"""
        parts = [f"姓名：{member.name}"]
        parts.append(f"年龄：{member.age}岁")
        parts.append(f"性别：{member.gender}")
        parts.append(f"关系：{member.relationship}")

        if member.bmi is not None:
            parts.append(f"BMI：{member.bmi}")

        mh = member.medical_history
        if mh.allergies:
            parts.append(f"过敏史：{'、'.join(mh.allergies)}")
        if mh.chronic_diseases:
            parts.append(f"慢性病：{'、'.join(mh.chronic_diseases)}")
        if mh.surgeries:
            parts.append(f"手术史：{'、'.join(mh.surgeries)}")
        if mh.family_history:
            parts.append(f"家族病史：{'、'.join(mh.family_history)}")
        if mh.medications:
            parts.append(f"当前用药：{'、'.join(mh.medications)}")

        if member.vital_signs:
            vs = member.vital_signs
            vals = []
            if vs.blood_pressure_systolic and vs.blood_pressure_diastolic:
                vals.append(f"血压 {vs.blood_pressure_systolic}/{vs.blood_pressure_diastolic} mmHg")
            if vs.heart_rate:
                vals.append(f"心率 {vs.heart_rate} 次/分")
            if vs.temperature:
                vals.append(f"体温 {vs.temperature} °C")
            if vs.respiratory_rate:
                vals.append(f"呼吸 {vs.respiratory_rate} 次/分")
            if vs.oxygen_saturation:
                vals.append(f"血氧 {vs.oxygen_saturation}%")
            if vals:
                parts.append(f"体征：{'、'.join(vals)}")

        return "；".join(parts)


member_service = MemberService()
