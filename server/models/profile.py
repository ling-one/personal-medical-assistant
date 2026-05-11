"""健康档案基础模型（被 Member 模型引用）"""
from datetime import date
from pydantic import BaseModel, Field


class VitalSigns(BaseModel):
    """生命体征"""
    blood_pressure_systolic: int | None = Field(None, description="收缩压 (mmHg)")
    blood_pressure_diastolic: int | None = Field(None, description="舒张压 (mmHg)")
    heart_rate: int | None = Field(None, description="心率 (次/分)")
    temperature: float | None = Field(None, description="体温 (°C)")
    respiratory_rate: int | None = Field(None, description="呼吸频率 (次/分)")
    oxygen_saturation: float | None = Field(None, description="血氧饱和度 (%)")


class MedicalHistory(BaseModel):
    """病史信息"""
    allergies: list[str] = Field(default_factory=list, description="过敏史")
    chronic_diseases: list[str] = Field(default_factory=list, description="慢性病")
    surgeries: list[str] = Field(default_factory=list, description="手术史")
    family_history: list[str] = Field(default_factory=list, description="家族病史")
    medications: list[str] = Field(default_factory=list, description="当前用药")

