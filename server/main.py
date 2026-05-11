"""个人医疗助手 - 主入口"""
import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager

from server.config import settings
from server.api import chat, knowledge, user, group, member, report

# 统一日志配置
logging.basicConfig(
    level=getattr(logging, settings.log_level.upper(), logging.INFO),
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理"""
    print(f"启动 {settings.app_name} v{settings.app_version}")
    yield
    print("应用关闭")


app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    lifespan=lifespan,
)

# CORS 配置
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 注册路由
app.include_router(chat.router, prefix="/api/chat", tags=["对话"])
app.include_router(knowledge.router, prefix="/api/knowledge", tags=["知识库"])
app.include_router(user.router, prefix="/api/user", tags=["用户管理"])
app.include_router(group.router, prefix="/api/group", tags=["家庭组管理"])
app.include_router(member.router, prefix="/api/member", tags=["家庭成员管理"])
app.include_router(report.router, prefix="/api/report", tags=["体检报告管理"])


@app.get("/")
async def root():
    """根路径"""
    return {
        "name": settings.app_name,
        "version": settings.app_version,
        "status": "running",
    }


@app.get("/health")
async def health_check():
    """健康检查"""
    return {"status": "healthy"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "server.main:app",
        host=settings.api_host,
        port=settings.api_port,
        reload=settings.debug,
    )
