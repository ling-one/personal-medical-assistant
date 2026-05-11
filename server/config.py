"""个人医疗助手 - 配置管理"""
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """应用配置"""

    # 应用设置
    app_name: str = "个人医疗助手"
    app_version: str = "0.1.0"
    debug: bool = False
    log_level: str = "INFO"

    # API 设置
    api_host: str = "0.0.0.0"
    api_port: int = 8000

    # LLM 设置 (小米大模型 / OpenAI 兼容)
    llm_api_key: str | None = None
    llm_base_url: str = "https://api.xiaomimimo.com/v1"
    llm_model: str = "mimo-v2-flash"
    llm_temperature: float = 0.7
    llm_max_tokens: int = 2000

    # OCR 设置 (千问 OCR)
    ocr_api_key: str | None = None
    ocr_api_base: str = "https://dashscope.aliyuncs.com/compatible-mode/v1"
    ocr_model: str = "qwen-vl-ocr-2025-11-20"
    ocr_provider: str = "qwen"

    # DashScope 设置 (Qwen3-VL-Rerank 等模型)
    dashscope_api_key: str | None = None

    # 向量模型设置 (本地模型)
    embedding_model_path: str = "BAAI/bge-small-zh-v1.5"
    embedding_device: str = "cpu"

    # 向量库配置
    vector_store_type: str = "faiss"
    vector_store_dir: str = "./vector_store_faiss"

    # 知识库设置
    knowledge_base_path: str = "data/knowledge_base"

    # 用户数据设置
    user_data_dir: str = "./data/users"

    # 家庭组数据设置
    group_data_dir: str = "./data/groups"
    member_data_dir: str = "./data/members"

    # 体检报告数据设置
    report_data_dir: str = "./data/reports"

    # 追踪设置 (Langfuse)
    langfuse_secret_key: str | None = None
    langfuse_public_key: str | None = None
    langfuse_base_url: str = "http://localhost:3000"

    # 调试设置
    debug_port: int = 8001

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


settings = Settings()
