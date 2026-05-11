"""知识库检索工具"""
from typing import Optional

from langchain.tools import tool

from server.services.vector_store import vector_store_service


@tool
def search_knowledge_base(
    query: str,
    category: Optional[str] = None,
    top_k: int = 5
) -> str:
    """
    在本地医学知识库中检索相关信息。
    
    Args:
        query: 查询内容
        category: 可选，限定分类
        top_k: 返回结果数量
    
    Returns:
        检索到的相关内容
    """
    import asyncio
    
    async def _search():
        return await vector_store_service.search(
            query=query,
            filter_category=category,
            top_k=top_k
        )
    
    results = asyncio.run(_search())
    
    if not results:
        return "未在知识库中找到相关信息"
    
    formatted = []
    for i, r in enumerate(results, 1):
        source = r.get("metadata", {}).get("title", "未知来源")
        content = r["content"][:200] + "..." if len(r["content"]) > 200 else r["content"]
        formatted.append(f"{i}. [{source}]\n{content}")
    
    return "\n\n".join(formatted)


@tool
def get_disease_info(disease_name: str) -> str:
    """
    获取疾病的详细信息。
    
    Args:
        disease_name: 疾病名称
    
    Returns:
        疾病相关信息
    """
    return search_knowledge_base.invoke(
        query=f"{disease_name} 病因 症状 治疗",
        category="disease",
        top_k=3
    )


@tool
def get_health_tip(topic: str) -> str:
    """
    获取健康小贴士。
    
    Args:
        topic: 主题（如：饮食、运动、睡眠等）
    
    Returns:
        健康建议
    """
    return search_knowledge_base.invoke(
        query=f"{topic} 健康建议 注意事项",
        category="health_tips",
        top_k=3
    )
