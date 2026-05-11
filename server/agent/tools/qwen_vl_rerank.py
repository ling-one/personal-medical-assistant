"""Qwen3-VL-Rerank 多模态重排序工具"""
import os
from typing import List, Dict, Any, Optional, Union
from langchain.tools import tool

try:
    from dashscope import TextReRank
except ImportError:
    TextReRank = None


class QwenVLReranker:
    """Qwen3-VL-Rerank 多模态重排序器"""
    
    def __init__(self, api_key: Optional[str] = None, model: str = "qwen3-vl-rerank"):
        """
        初始化重排序器
        
        Args:
            api_key: DashScope API Key，如果不提供则从环境变量读取
            model: 模型名称
        """
        self._api_key = api_key or os.getenv("DASHSCOPE_API_KEY")
        self._model = model
        self._headers = None
        
        if self._api_key:
            self._headers = {
                "Authorization": f"Bearer {self._api_key}",
                "Content-Type": "application/json"
            }
    
    def _call_api(
        self,
        query: Union[str, Dict],
        documents: List[Union[str, Dict]],
        top_n: int = 10,
        return_documents: bool = True
    ) -> Dict[str, Any]:
        """
        调用 DashScope TextReRank API
        
        Args:
            query: 查询（文本或包含文本+图像的多模态输入）
            documents: 文档列表（文本或多模态）
            top_n: 返回结果数量
            return_documents: 是否返回文档内容
        
        Returns:
            API 响应结果
        """
        if not TextReRank:
            raise ImportError("dashscope 未安装，请运行: pip install dashscope")
        
        if not self._api_key:
            raise ValueError("未配置 DASHSCOPE_API_KEY，请在 .env 中配置")
        
        try:
            # 使用 DashScope SDK 调用
            response = TextReRank.call(
                model=self._model,
                query=query,
                documents=documents,
                top_n=top_n,
                return_documents=return_documents,
                api_key=self._api_key
            )
            
            return response
        except Exception as e:
            # 降级：使用 HTTP API 直接调用
            import requests
            
            url = "https://dashscope.aliyuncs.com/api/v1/services/rerank/text-rerank"
            
            payload = {
                "model": self._model,
                "input": {
                    "query": query,
                    "documents": documents
                },
                "parameters": {
                    "top_n": top_n,
                    "return_documents": return_documents
                }
            }
            
            response = requests.post(url, headers=self._headers, json=payload, timeout=30)
            response.raise_for_status()
            
            return response.json()
    
    def rerank(
        self,
        query: str,
        documents: List[str],
        top_k: int = 10
    ) -> List[Dict[str, Any]]:
        """
        文本重排序
        
        Args:
            query: 查询文本
            documents: 文档文本列表
            top_k: 返回结果数量
        
        Returns:
            重排序后的结果列表
        """
        if not documents:
            return []
        
        try:
            response = self._call_api(
                query=query,
                documents=documents,
                top_n=min(top_k, len(documents)),
                return_documents=True
            )
            
            # 解析响应
            results = []
            
            # DashScope SDK 响应格式
            if hasattr(response, 'output'):
                output = response.output
                if isinstance(output, dict) and 'results' in output:
                    for item in output['results']:
                        results.append({
                            "index": item.get("index", 0),
                            "score": item.get("relevance_score", 0.0),
                            "document": item.get("document", {}).get("text", "") if isinstance(item.get("document"), dict) else ""
                        })
            # HTTP API 响应格式
            elif isinstance(response, dict):
                output = response.get("output", {})
                for item in output.get("results", []):
                    results.append({
                        "index": item.get("index", 0),
                        "score": item.get("relevance_score", 0.0),
                        "document": item.get("document", {}).get("text", "") if isinstance(item.get("document"), dict) else ""
                    })
            
            return results
        except Exception as e:
            # 出错时返回原始顺序
            return [
                {"index": i, "score": 1.0, "document": doc}
                for i, doc in enumerate(documents[:top_k])
            ]
    
    def rerank_multimodal(
        self,
        query: Union[str, List[Dict]],
        documents: List[Union[str, Dict]],
        top_k: int = 10
    ) -> List[Dict[str, Any]]:
        """
        多模态重排序（支持文本+图像）
        
        Args:
            query: 查询（文本或多模态格式）
            documents: 文档列表（文本或多模态格式）
            top_k: 返回结果数量
        
        Returns:
            重排序后的结果列表
        
        示例:
            # 文本查询 + 图像文档
            query = "描述这张图片"
            documents = [
                {"text": "图片描述", "image": "https://example.com/image.jpg"},
                ...
            ]
        """
        if not documents:
            return []
        
        try:
            response = self._call_api(
                query=query,
                documents=documents,
                top_n=min(top_k, len(documents)),
                return_documents=True
            )
            
            # 解析响应
            results = []
            
            # DashScope SDK 响应格式
            if hasattr(response, 'output'):
                output = response.output
                if isinstance(output, dict) and 'results' in output:
                    for item in output['results']:
                        results.append({
                            "index": item.get("index", 0),
                            "score": item.get("relevance_score", 0.0),
                            "document": item.get("document", {})
                        })
            # HTTP API 响应格式
            elif isinstance(response, dict):
                output = response.get("output", {})
                for item in output.get("results", []):
                    results.append({
                        "index": item.get("index", 0),
                        "score": item.get("relevance_score", 0.0),
                        "document": item.get("document", {})
                    })
            
            return results
        except Exception as e:
            # 出错时返回原始顺序
            return [
                {"index": i, "score": 1.0, "document": doc}
                for i, doc in enumerate(documents[:top_k])
            ]


# 全局实例
qwen_vl_reranker = QwenVLReranker()


@tool
def qwen_vl_rerank(
    query: str,
    documents: List[str],
    top_k: int = 10
) -> str:
    """
    使用 Qwen3-VL-Rerank 模型对文本进行重排序。
    支持中文文本相关性排序，比本地 bge-reranker 效果更好。
    
    Args:
        query: 查询内容
        documents: 文档内容列表
        top_k: 返回结果数量
    
    Returns:
        重排序后的结果
    """
    results = qwen_vl_reranker.rerank(query, documents, top_k)
    
    if not results:
        return "无结果"
    
    formatted = []
    for i, r in enumerate(results, 1):
        doc = r.get("document", "")
        content = doc[:200] + "..." if len(doc) > 200 else doc
        formatted.append(f"{i}. [相关性: {r['score']:.4f}]\n{content}")
    
    return "\n\n".join(formatted)


@tool
def qwen_vl_rerank_search_results(
    query: str,
    top_k: int = 10
) -> str:
    """
    对向量库搜索结果进行重排序。
    使用 Qwen3-VL-Rerank 模型提升搜索结果相关性。
    
    Args:
        query: 查询内容
        top_k: 返回结果数量
    
    Returns:
        重排序后的搜索结果
    """
    from server.services.vector_store import vector_store_service
    
    import asyncio
    
    async def _rerank():
        # 获取初始检索结果
        docs = await vector_store_service.search(query, top_k=top_k * 2)
        
        if not docs:
            return "未找到相关结果"
        
        # 提取文档内容
        documents = []
        for doc in docs:
            content = doc.get("content", "")
            title = doc.get("metadata", {}).get("title", "")
            documents.append(f"{title}\n{content}" if title else content)
        
        # 重排序
        results = qwen_vl_reranker.rerank(query, documents, top_k)
        
        # 格式化输出
        formatted = []
        for i, r in enumerate(results, 1):
            doc_content = r.get("document", "")
            # 找到对应的原始文档
            orig_doc = None
            for d in docs:
                content = d.get("content", "")
                title = d.get("metadata", {}).get("title", "")
                full = f"{title}\n{content}" if title else content
                if full == doc_content:
                    orig_doc = d
                    break
            
            if orig_doc:
                title = orig_doc.get("metadata", {}).get("title", "未知来源")
                content = orig_doc.get("content", "")[:150] + "..."
                formatted.append(
                    f"{i}. [{title}] (相关性: {r['score']:.4f})\n{content}"
                )
        
        return "\n\n".join(formatted)
    
    return asyncio.run(_rerank())


@tool
def qwen_vl_rerank_multimodal(
    query: Union[str, List[Dict]],
    documents: List[Union[str, Dict]],
    top_k: int = 10
) -> str:
    """
    多模态重排序（支持文本+图像）。
    使用 Qwen3-VL-Rerank 模型对混合模态内容进行相关性排序。
    
    Args:
        query: 查询（文本或包含文本+图像的多模态输入）
        documents: 文档列表（文本或多模态格式）
        top_k: 返回结果数量
    
    Returns:
        重排序后的结果
    
    示例:
        # 文本查询 + 图像文档
        query = "描述这张图片"
        documents = [
            {"text": "图片描述", "image": "https://example.com/image.jpg"},
            ...
        ]
    """
    results = qwen_vl_reranker.rerank_multimodal(query, documents, top_k)
    
    if not results:
        return "无结果"
    
    formatted = []
    for i, r in enumerate(results, 1):
        doc = r.get("document", {})
        if isinstance(doc, dict):
            text = doc.get("text", "")
            image = doc.get("image", "")
            content = f"{text[:150]}..." if len(text) > 150 else text
            if image:
                content += f"\n[图片: {image}]"
        else:
            content = str(doc)[:200] + "..." if len(str(doc)) > 200 else str(doc)
        
        formatted.append(f"{i}. [相关性: {r['score']:.4f}]\n{content}")
    
    return "\n\n".join(formatted)
