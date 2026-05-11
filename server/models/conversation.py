"""对话模型"""
from datetime import datetime
from enum import Enum
from typing import Any
from pydantic import BaseModel, Field


class IntentType(str, Enum):
    """意图类型枚举"""
    HEALTH_QA = "health_qa"           # 健康知识问答
    REPORT_READER = "report_reader"   # 报告解读
    DRUG_QUERY = "drug_query"         # 用药查询
    HEALTH_ANALYSIS = "health_analysis"  # 健康数据分析
    LIFESTYLE = "lifestyle"          # 生活方式建议
    UNKNOWN = "unknown"              # 未知意图


class Message(BaseModel):
    """消息"""
    role: str = Field(..., description="角色: user/assistant/system")
    content: str = Field(..., description="消息内容")
    timestamp: datetime = Field(default_factory=datetime.now, description="时间戳")
    metadata: dict[str, Any] = Field(default_factory=dict, description="元数据")


class Conversation(BaseModel):
    """对话"""
    id: str | None = Field(None, description="对话ID")
    user_id: str = Field(..., description="用户ID")
    messages: list[Message] = Field(default_factory=list, description="消息列表")
    context: dict[str, Any] = Field(default_factory=dict, description="上下文")
    created_at: datetime = Field(default_factory=datetime.now, description="创建时间")
    updated_at: datetime = Field(default_factory=datetime.now, description="更新时间")


class ChatRequest(BaseModel):
    """聊天请求"""
    message: str = Field(..., description="用户消息")
    user_id: str = Field(..., description="用户ID")
    conversation_id: str | None = Field(None, description="对话ID，不传则后端自动生成")
    stream: bool = Field(True, description="是否流式输出")
    member_id: str | None = Field(None, description="家庭成员ID，指定为谁咨询")
    report_id: str | None = Field(None, description="体检报告ID，指定要分析的报告")


class ChatResponse(BaseModel):
    """聊天响应"""
    conversation_id: str = Field(..., description="对话ID")
    message: str = Field(..., description="回复内容")
    intent: IntentType = Field(..., description="识别到的意图")
    suggestions: list[str] = Field(default_factory=list, description="建议追问")
    trace_id: str | None = Field(None, description="追踪ID")
