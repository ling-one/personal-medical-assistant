"""联网搜索工具"""
import re
from typing import  Any
from langchain.tools import tool

try:
    import httpx
except ImportError:
    httpx = None


@tool
def web_search(query: str, top_k: int = 5) -> str:
    """
    搜索互联网获取最新的健康信息。
    
    Args:
        query: 搜索查询词
        top_k: 返回结果数量，默认5条
    
    Returns:
        搜索结果摘要
    """
    if not httpx:
        return "网络搜索功能暂不可用"
    
    # 使用 DuckDuckGo 搜索 (无需 API Key)
    search_url = f"https://html.duckduckgo.com/html/?q={query}"
    
    try:
        response = httpx.get(search_url, timeout=10)
        response.raise_for_status()
        
        # 简单解析 HTML
        html = response.text
        results = re.findall(
            r'<a class="result__snippet"[^>]*>(.*?)</a>',
            html,
            re.DOTALL
        )
        
        if not results:
            return "未找到相关结果"
        
        snippets = [re.sub(r'<[^>]+>', '', r).strip() for r in results[:top_k]]
        return "\n".join([f"{i+1}. {s}" for i, s in enumerate(snippets)])
        
    except Exception as e:
        return f"搜索失败: {str(e)}"


@tool
def search_medical_news(keyword: str) -> str:
    """
    搜索医学健康相关新闻。
    
    Args:
        keyword: 关键词
    
    Returns:
        新闻摘要
    """
    return web_search.invoke(f"健康新闻 {keyword}")
