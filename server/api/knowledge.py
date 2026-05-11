"""知识库管理接口"""
from concurrent.futures.thread import ThreadPoolExecutor
import asyncio
import concurrent.futures
from typing import Any
from fastapi import APIRouter, HTTPException, UploadFile, File

from server.services.vector_store import vector_store_service

router = APIRouter()

# 全局导入进度追踪
_import_progress: dict[str, Any] = {
    "total": 0,
    "current": 0,
    "phase": "idle",
    "result": None
}

# 全局线程池执行器
_executor: ThreadPoolExecutor = concurrent.futures.ThreadPoolExecutor(max_workers=1)


def _progress_callback(current: int, total: int, phase: str) -> None:
    """导入进度回调函数"""
    global _import_progress
    _import_progress["current"] = current
    _import_progress["total"] = total
    _import_progress["phase"] = phase


def _import_task_sync(file_path: str, batch_size: int = 500) -> None:
    """同步导入任务（在线程池中运行）"""
    global _import_progress
    _import_progress["phase"] = "running"
    
    result: dict[str, int] = vector_store_service.batch_import_haodf_sync(
        file_path=file_path,
        batch_size=batch_size,
        progress_callback=_progress_callback
    )
    
    _import_progress["result"] = result
    _import_progress["phase"] = "done"


@router.get(path="/search")
async def search_knowledge(
    query: str,
    top_k: int = 5,
    category: str | None = None
) -> dict[str, list[dict[str, Any]]]:
    """搜索知识库"""
    results: list[dict[str, Any]] = await vector_store_service.search(
        query=query,
        top_k=top_k,
        filter_category=category
    )
    return {"results": results}


@router.post(path="/documents")
async def add_document(
    title: str,
    content: str,
    category: str | None = None,
    metadata: dict[str, Any] | None = None
):
    """添加文档到知识库"""
    doc_id = await vector_store_service.add_document(
        title=title,
        content=content,
        category=category,
        metadata=metadata or {}
    )
    return {"document_id": doc_id, "status": "added"}


@router.delete(path="/documents/{doc_id}")
async def delete_document(doc_id: str) -> dict[str, str]:
    """从知识库删除文档"""
    success = await vector_store_service.delete_document(doc_id)
    if not success:
        raise HTTPException(status_code=404, detail="文档不存在")
    return {"status": "deleted"}


@router.post(path="/upload")
async def upload_document(file: UploadFile = File(default=...)) -> dict[str, str]:
    """上传文档"""
    if not file.filename.endswith(('.txt', '.pdf', '.md')):
        raise HTTPException(status_code=400, detail="不支持的文件格式")
    
    content = await file.read()
    text = content.decode("utf-8")
    
    doc_id = await vector_store_service.add_document(
        title=file.filename,
        content=text,
        category="uploaded"
    )
    
    return {"document_id": doc_id, "status": "uploaded"}


@router.get("/categories")
async def list_categories():
    """获取所有分类"""
    categories = await vector_store_service.get_categories()
    return {"categories": categories}


@router.post("/rebuild")
async def rebuild_index():
    """重建索引"""
    await vector_store_service.rebuild_index()
    return {"status": "rebuilt"}


@router.post("/import-haodf")
async def import_haodf(
    file_path: str = "d:/个人医疗助手/医疗对话.txt",
    batch_size: int = 500
):
    """
    批量导入好大夫医疗对话数据
    
    Args:
        file_path: 医疗对话.txt 路径
        batch_size: 每批导入数量
    """
    global _import_progress
    
    if _import_progress["phase"] in ["running", "start"]:
        return {"status": "already_running", "progress": _import_progress}
    
    # 重置进度
    _import_progress["total"] = 0
    _import_progress["current"] = 0
    _import_progress["phase"] = "start"
    _import_progress["result"] = None
    
    # 使用线程池真正在后台运行，不阻塞事件循环
    _executor.submit(_import_task_sync, file_path, batch_size)
    
    return {"status": "started", "message": "导入任务已启动，请查询 /import-progress 获取进度"}


@router.get("/import-progress")
async def get_import_progress():
    """查询导入进度"""
    global _import_progress
    return _import_progress


@router.get("/stats")
async def get_knowledge_stats():
    """获取知识库统计信息"""
    stats = await vector_store_service.get_stats()
    return stats
