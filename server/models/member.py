"""家庭成员数据模型"""
from datetime import date, datetime
from pydantic import BaseModel, Field

from server.models.profile import VitalSigns, MedicalHistory


class Member(BaseModel):
    """家庭成员"""
    member_id: str = Field(..., description="成员ID")
    group_id: str = Field(..., description="所属家庭组ID")
    name: str = Field(..., description="姓名")
    relationship: str = Field(..., description="关系(本人/配偶/子女/父母等)")
    gender: str = Field(..., description="性别")
    birth_date: date = Field(..., description="出生日期")
    height: float | None = Field(None, description="身高 (cm)")
    weight: float | None = Field(None, description="体重 (kg)")
    medical_history: MedicalHistory = Field(default_factory=MedicalHistory, description="病史")
    vital_signs: VitalSigns | None = Field(None, description="生命体征")
    created_at: datetime = Field(default_factory=datetime.now, description="创建时间")
    updated_at: datetime = Field(default_factory=datetime.now, description="更新时间")

    @property
    def age(self) -> int:
        """计算年龄"""
        today = date.today()
        return today.year - self.birth_date.year - (
            (today.month, today.day) < (self.birth_date.month, self.birth_date.day)
        )

    @property
    def bmi(self) -> float | None:
        """计算 BMI"""
        if self.height and self.weight:
            height_m = self.height / 100
            return round(self.weight / (height_m**2), 1)
        return None


class MemberCreate(BaseModel):
    """创建成员请求"""
    name: str = Field(..., description="姓名")
    relationship: str = Field(..., description="关系")
    gender: str = Field(..., description="性别")
    birth_date: date = Field(..., description="出生日期")
    height: float | None = Field(None, description="身高 (cm)")
    weight: float | None = Field(None, description="体重 (kg)")


class MemberUpdate(BaseModel):
    """更新成员请求"""
    name: str | None = Field(None, description="姓名")
    relationship: str | None = Field(None, description="关系")
    gender: str | None = Field(None, description="性别")
    birth_date: date | None = Field(None, description="出生日期")
    height: float | None = Field(None, description="身高 (cm)")
    weight: float | None = Field(None, description="体重 (kg)")
