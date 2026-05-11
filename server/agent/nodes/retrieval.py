"""检索节点 - 并行检索系统知识库 + 用户长期记忆"""
from typing import Any

from server.agent.state import AgentState
from server.services.vector_store import vector_store_service


async def node(state: AgentState) -> dict[str, Any]:
    """
    并行检索：
    - 系统共享库（好大夫医疗知识）
    - 用户私有库（长期记忆）
    """
    messages = state.get("messages", [])
    user_id = state.get("user_id", "")
    if not messages:
        return {"search_results": [], "retrieved_docs": [], "user_memory_results": []}

    query = ""
    for msg in reversed(messages):
        if msg.get("role") == "user":
            query = msg.get("content", "")
            break
    if not query:
        return {"search_results": [], "retrieved_docs": [], "user_memory_results": []}

    import asyncio

    # 并行检索
    system_task = vector_store_service.search(
        query=query, top_k=5, filter_category="haodf"
    )
    user_task = (
        vector_store_service.search_user_index(user_id=user_id, query=query, top_k=3)
        if user_id
        else asyncio.sleep(0, result=[])
    )

    system_results, user_results = await asyncio.gather(
        system_task, user_task, return_exceptions=True
    )
    if not isinstance(system_results, list):
        system_results = []
    if not isinstance(user_results, list):
        user_results = []

    # 格式化系统检索结果（好大夫知识）
    retrieved_docs = []
    search_results = []
    for r in system_results:
        doc_text = f"[来源: 好大夫医疗对话]\n{r['content']}"
        retrieved_docs.append(doc_text)
        search_results.append({
            "content": r["content"][:200] + "..." if len(r["content"]) > 200 else r["content"],
            "metadata": r.get("metadata", {}),
            "score": r.get("score", 0.0),
        })

    # 格式化用户记忆结果
    user_memory_results = []
    for r in user_results:
        cat = r.get("metadata", {}).get("category", "记忆")
        doc_text = f"[来源: 用户长期记忆 - {cat}]\n{r['content']}"
        retrieved_docs.append(doc_text)
        user_memory_results.append({
            "content": r["content"][:200] + "...",
            "metadata": r.get("metadata", {}),
            "score": r.get("score", 0.0),
        })

    return {
        "search_results": search_results,
        "retrieved_docs": retrieved_docs,
        "user_memory_results": user_memory_results,
    }


def retrieval_node(state: AgentState) -> dict[str, Any]:
    """同步包装器"""
    import asyncio
    return asyncio.run(node(state))
