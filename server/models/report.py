"""体检报告数据模型"""
from datetime import datetime
from pydantic import BaseModel, Field


class ReportRecord(BaseModel):
    """体检报告记录"""
    report_id: str = Field(..., description="报告ID")
    member_id: str = Field(..., description="成员ID")
    filename: str = Field(..., description="原始文件名")
    ocr_text: str = Field(..., description="OCR 识别文本")
    analysis: str | None = Field(None, description="LLM 分析结果")
    created_at: datetime = Field(default_factory=datetime.now, description="创建时间")
