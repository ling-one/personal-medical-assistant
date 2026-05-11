"""混合检索工具 - 向量 + BM25 + 关键词"""
import re
import math
from collections import Counter
from langchain.tools import tool

try:
    from rank_bm25 import BM25Okapi
except ImportError:
    BM25Okapi = None


class HybridRetriever:
    """混合检索器"""

    def __init__(self):
        self.vector_results: list[dict] = []
        self.bm25_results: list[dict] = []
        self.keyword_results: list[dict] = []

    def preprocess_text(self, text: str) -> list[str]:
        """文本预处理"""
        # 去除特殊字符，转小写，分词
        text = re.sub(r'[^\w\s]', ' ', text.lower())
        return text.split()
    
    def keyword_search(
        self,
        query: str,
        documents: list[dict[str, Any]],
        top_k: int = 10
    ) -> list[dict[str, Any]]:
        """关键词精确匹配"""
        query_terms = set(self.preprocess_text(query))
        results = []
        
        for i, doc in enumerate(documents):
            content = doc.get("content", "")
            title = doc.get("title", "")
            combined = f"{title} {content}".lower()
            doc_terms = set(self.preprocess_text(combined))
            
            # 计算命中数
            matches = query_terms & doc_terms
            if matches:
                # TF-IDF 风格评分
                score = len(matches) / len(query_terms)
                results.append({
                    "id": doc.get("id", i),
                    "doc": doc,
                    "score": score,
                    "matches": list(matches)
                })
        
        # 按分数排序
        results.sort(key=lambda x: x["score"], reverse=True)
        return results[:top_k]
    
    def bm25_search(
        self,
        query: str,
        documents: list[dict[str, Any]],
        top_k: int = 10
    ) -> list[dict[str, Any]]:
        """BM25 检索"""
        if not BM25Okapi:
            # 降级到关键词搜索
            return self.keyword_search(query, documents, top_k)
        
        # 准备语料库
        corpus = []
        for doc in documents:
            content = doc.get("content", "")
            title = doc.get("title", "")
            corpus.append(self.preprocess_text(f"{title} {content}"))
        
        # 构建 BM25
        bm25 = BM25Okapi(corpus)
        query_terms = self.preprocess_text(query)
        
        # 获取分数
        scores = bm25.get_scores(query_terms)
        
        # 构建结果
        results = []
        for i, score in enumerate(scores):
            if score > 0:
                results.append({
                    "id": documents[i].get("id", i),
                    "doc": documents[i],
                    "score": float(score),
                    "rank": i
                })
        
        # 排序
        results.sort(key=lambda x: x["score"], reverse=True)
        return results[:top_k]
    
    def normalize_scores(self, results: list[dict]) -> list[dict]:
        """归一化分数到 [0, 1]"""
        if not results:
            return results
        
        scores = [r["score"] for r in results]
        min_score, max_score = min(scores), max(scores)
        
        if max_score == min_score:
            return [{**r, "normalized_score": 1.0} for r in results]
        
        return [
            {**r, "normalized_score": (r["score"] - min_score) / (max_score - min_score)}
            for r in results
        ]
    
    def rrf_fusion(
        self,
        result_lists: list[list[dict]],
        k: int = 60
    ) -> list[dict]:
        """
        RRF (Reciprocal Rank Fusion) 融合排序
        
        Args:
            result_lists: 多个检索结果列表
            k: RRF 参数，通常 60
        """
        scores = Counter()
        doc_scores = {}
        
        for results in result_lists:
            for rank, item in enumerate(results, 1):
                doc_id = item.get("id", id(item.get("doc")))
                
                # RRF 分数
                rrf_score = 1 / (k + rank)
                scores[doc_id] += rrf_score
                
                # 保存文档信息
                if doc_id not in doc_scores:
                    doc_scores[doc_id] = {
                        "doc": item.get("doc"),
                        "id": doc_id,
                        "component_scores": {}
                    }
                
                # 保存各组件分数
                source_idx = len(doc_scores[doc_id]["component_scores"])
                doc_scores[doc_id]["component_scores"][f"source_{source_idx}"] = item.get("score", 0)
        
        # 构建最终结果
        fused_results = []
        for doc_id, rrf_score in scores.most_common():
            item = doc_scores[doc_id]
            item["rrf_score"] = rrf_score
            fused_results.append(item)
        
        return fused_results
    
    async def hybrid_retrieve(
        self,
        query: str,
        documents: list[dict[str, Any]],
        vector_scores: list[dict] | None = None,
        top_k: int = 10
    ) -> list[dict[str, Any]]:
        """
        混合检索
        
        Args:
            query: 查询词
            documents: 文档列表
            vector_scores: 向量检索分数（可选）
            top_k: 返回数量
        """
        results = []
        
        # 1. 关键词检索
        keyword_results = self.keyword_search(query, documents, top_k * 2)
        
        # 2. BM25 检索
        bm25_results = self.bm25_search(query, documents, top_k * 2)
        
        # 3. 向量检索（如果提供）
        if vector_scores:
            # 归一化向量分数
            vector_results = self.normalize_scores(vector_scores)
        else:
            vector_results = []
        
        # 4. RRF 融合
        component_results = [keyword_results]
        if bm25_results:
            component_results.append(bm25_results)
        if vector_results:
            component_results.append(vector_results)
        
        fused = self.rrf_fusion(component_results)
        
        # 5. 返回 top_k
        return fused[:top_k]


# 全局实例
hybrid_retriever = HybridRetriever()


@tool
def hybrid_search(
    query: str,
    top_k: int = 10
) -> str:
    """
    混合检索 - 结合向量、BM25和关键词检索。
    
    Args:
        query: 查询内容
        top_k: 返回结果数量
    
    Returns:
        检索结果
    """
    from server.services.vector_store import vector_store_service
    
    import asyncio
    
    async def _search():
        # 获取所有文档
        docs = await vector_store_service.search(query, top_k=top_k * 3)
        return docs
    
    docs = asyncio.run(_search())
    
    if not docs:
        return "未找到相关结果"
    
    # 执行混合检索
    results = asyncio.run(
        hybrid_retriever.hybrid_retrieve(query, docs, top_k=top_k)
    )
    
    if not results:
        return "未找到相关结果"
    
    formatted = []
    for i, r in enumerate(results, 1):
        doc = r.get("doc", {})
        title = doc.get("metadata", {}).get("title", "未知来源")
        content = doc.get("content", "")[:150] + "..."
        score = r.get("rrf_score", 0)
        formatted.append(f"{i}. [{title}] (相关性: {score:.2f})\n{content}")
    
    return "\n\n".join(formatted)
