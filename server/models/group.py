"""家庭组数据模型"""
from datetime import datetime
from pydantic import BaseModel, Field


class Group(BaseModel):
    """家庭组"""
    group_id: str = Field(..., description="组ID")
    group_number: str = Field(..., description="9位数字组号")
    group_name: str = Field(..., description="组名称")
    owner_id: str = Field(..., description="创建者用户ID")
    member_ids: list[str] = Field(default_factory=list, description="成员ID列表")
    created_at: datetime = Field(default_factory=datetime.now, description="创建时间")
    updated_at: datetime = Field(default_factory=datetime.now, description="更新时间")


class GroupCreate(BaseModel):
    """创建家庭组请求"""
    group_name: str = Field(..., description="组名称")
    user_id: str = Field(..., description="创建者用户ID")
