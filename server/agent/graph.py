"""LangGraph 图定义 - 新增记忆加载/更新节点"""
from server.models.conversation import IntentType


from langgraph.graph.state import StateGraph


from langgraph.graph import StateGraph, END
from typing import Literal

from server.agent.state import AgentState
from server.agent.nodes import (
    classify,
    report_reader,
    drug_query,
    health_analysis,
    lifestyle,
    respond,
    query_rewrite,
    retrieval,
    # 记忆节点
    memory_load,
    memory_update,
)
from server.services.trace_service import trace_service


def create_graph() -> StateGraph:
    """创建医疗问答图 - 带记忆管理"""
    graph: StateGraph[AgentState, None, AgentState, AgentState] = StateGraph(state_schema=AgentState)

    # ========== Agentic 核心节点 ==========
    graph.add_node("query_rewrite", query_rewrite.node)
    graph.add_node("memory_load", memory_load.node)
    graph.add_node("memory_update", memory_update.node)

    # ========== RAG 检索 ==========
    graph.add_node("retrieval", retrieval.node)

    # ========== 原有功能节点 ==========
    graph.add_node("classify", classify.node)
    graph.add_node("report_reader", report_reader.node)
    graph.add_node("drug_query", drug_query.node)
    graph.add_node("health_analysis", health_analysis.node)
    graph.add_node("lifestyle", lifestyle.node)
    graph.add_node("respond", respond.node)

    # ========== 流程编排 ==========

    # 入口：查询改写 → 记忆加载 → 意图分类
    graph.set_entry_point(key="query_rewrite")
    graph.add_edge(start_key="query_rewrite", end_key="memory_load")
    graph.add_edge(start_key="memory_load", end_key="classify")

    # 意图分类 → 检索
    graph.add_edge(start_key="classify", end_key="retrieval")

    # 检索 → 各功能节点（条件路由）
    def route_after_retrieval(state: AgentState) -> str:
        intent: IntentType | None = state.get("intent")
        if intent:
            return intent.value
        return "health_qa"

    graph.add_conditional_edges(
        "retrieval",
        route_after_retrieval,
        {
            "health_qa": "respond",
            "report_reader": "report_reader",
            "drug_query": "drug_query",
            "health_analysis": "health_analysis",
            "lifestyle": "lifestyle",
            "unknown": "respond",
        },
    )

    # 所有意图节点 → 回复生成
    for node_name in ["report_reader", "drug_query", "health_analysis", "lifestyle"]:
        graph.add_edge(node_name, "respond")

    # 回复 → 记忆更新 → 结束
    graph.add_edge("respond", "memory_update")
    graph.add_edge("memory_update", END)

    return graph.compile()


# 全局图实例
medical_graph = create_graph()
