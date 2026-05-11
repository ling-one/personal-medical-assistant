"""查询改写节点 - 纠错 + 术语转换 + 子查询拆解"""
import re
import json
from typing import Any
from server.agent.state import AgentState
from server.services.llm_service import llm_service
from server.services.trace_service import trace_service

QUERY_REWRITE_PROMPT = """你是一个医疗查询处理专家。请对用户的医疗问题进行改写处理。

用户原始查询：{original_query}

任务：
1. **纠错**：修正拼写错误、语法错误、口语化表达
2. **术语转换**：将通俗用语转换为标准医学术语
3. **子查询拆解**：将复杂问题拆解为多个可独立检索的子问题

医学术语对照表（部分）：
- 血压高 → 高血压
- 血糖高 → 高血糖/糖尿病
- 心脏不舒服 → 心悸/胸闷/心绞痛
- 睡不着 → 失眠
- 脑袋疼 → 头痛
- 肚子疼 → 腹痛
- 拉肚子 → 腹泻

请返回JSON格式：
{
    "rewritten_query": "改写后的标准查询",
    "corrected": true/false,  // 是否进行了纠错
    "term_mappings": {{"通俗词": "医学术语"}},  // 术语映射
    "sub_queries": ["子查询1", "子查询2", ...],  // 拆解后的子查询
    "original_intent": "原始意图总结"
}
"""

SUB_QUERY_SPLITTER = """将以下医疗问题拆解为可独立检索的子查询：

问题：{question}

拆解规则：
1. 每个子查询应该专注于一个具体方面
2. 子查询之间应该相互独立
3. 包含必要的上下文信息

示例：
问题："我有高血压和糖尿病，饮食要注意什么？"
拆解：
- "高血压患者的饮食原则"
- "糖尿病患者的饮食原则"  
- "高血压合并糖尿病的饮食禁忌"

请返回子查询列表，每行一个："""


class QueryRewriteResult:
    """查询改写结果"""
    def __init__(
        self,
        original_query: str,
        rewritten_query: str,
        corrected: bool,
        term_mappings: dict[str, str],
        sub_queries: list[str],
        original_intent: str
    ):
        self.original_query = original_query
        self.rewritten_query = rewritten_query
        self.corrected = corrected
        self.term_mappings = term_mappings
        self.sub_queries = sub_queries
        self.original_intent = original_intent

    def to_dict(self) -> dict[str, Any]:
        return {
            "original_query": self.original_query,
            "rewritten_query": self.rewritten_query,
            "corrected": self.corrected,
            "term_mappings": self.term_mappings,
            "sub_queries": self.sub_queries,
            "original_intent": self.original_intent
        }


async def rewrite_query(query: str) -> QueryRewriteResult:
    """改写查询"""
    try:
        prompt = llm_service.format_prompt("query_rewrite_prompt", QUERY_REWRITE_PROMPT, original_query=query)
        response = await llm_service.chat(
            messages=[{"role": "user", "content": prompt}],
            system="你是一个专业的医疗查询处理助手，擅长将用户的口语化问题转换为标准医学查询。"
        )
        
        result = json.loads(response)
        
        return QueryRewriteResult(
            original_query=query,
            rewritten_query=result.get("rewritten_query", query),
            corrected=result.get("corrected", False),
            term_mappings=result.get("term_mappings", {}),
            sub_queries=result.get("sub_queries", [query]),
            original_intent=result.get("original_intent", "")
        )
    except json.JSONDecodeError:
        # 解析失败时返回原始查询
        return QueryRewriteResult(
            original_query=query,
            rewritten_query=query,
            corrected=False,
            term_mappings={},
            sub_queries=[query],
            original_intent=""
        )
    except Exception as e:
        return QueryRewriteResult(
            original_query=query,
            rewritten_query=query,
            corrected=False,
            term_mappings={},
            sub_queries=[query],
            original_intent=""
        )


async def split_sub_queries(question: str) -> list[str]:
    """拆分子查询"""
    try:
        prompt = llm_service.format_prompt("sub_query_splitter_prompt", SUB_QUERY_SPLITTER, question=question)
        response = await llm_service.chat(
            messages=[{"role": "user", "content": prompt}],
            system="你是一个医疗查询拆解专家。"
        )
        
        # 简单解析，按行拆分
        lines = response.strip().split('\n')
        sub_queries = [
            re.sub(r'^\d+[\.、]\s*', '', line).strip()
            for line in lines
            if line.strip() and not line.startswith('#')
        ]
        
        return sub_queries if sub_queries else [question]
    except Exception:
        return [question]


async def node(state: AgentState) -> AgentState:
    """查询改写节点"""
    trace_service.start_node("query_rewrite", "query_rewrite_start")
    
    messages = state.get("messages", [])
    user_message = messages[-1]["content"] if messages else ""
    
    try:
        # 执行查询改写
        rewrite_result = await rewrite_query(user_message)
        
        trace_service.end_node({
            "rewritten_query": rewrite_result.rewritten_query,
            "sub_queries_count": len(rewrite_result.sub_queries),
            "corrected": rewrite_result.corrected
        })
        
        return {
            "context": {
                **state.get("context", {}),
                "query_rewrite": rewrite_result.to_dict(),
                "original_query": user_message,
                "rewritten_query": rewrite_result.rewritten_query,
                "sub_queries": rewrite_result.sub_queries,
            }
        }
    except Exception as e:
        trace_service.end_node({"error": str(e)}, error=str(e))
        return {
            "context": {
                **state.get("context", {}),
                "query_rewrite": None,
                "sub_queries": [user_message],
            },
            "error": str(e)
        }
