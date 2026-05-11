"""记忆加载节点 - 加载短期历史和长期记忆 + FAISS 持久化恢复 + 成员健康档案"""
from typing import Any

from server.agent.state import AgentState
from server.services.memory_service import get_short_memory
from server.services.vector_store import vector_store_service
from server.services.member_service import member_service


async def _restore_from_faiss(
    user_id: str,
    conversation_id: str,
) -> list[dict[str, str]]:
    """从 FAISS 按 conversation_id 恢复对话历史（用于服务重启后恢复短期记忆）"""
    try:
        turns = await vector_store_service.get_user_index_by_metadata(
            user_id=user_id,
            metadata_filter={
                "conversation_id": conversation_id,
                "category": "conversation_turn",
            },
        )
        if not turns:
            return []

        # 解析每条记录：从 "用户: ...\n助手: ..." 拆分为 user 和 assistant 消息
        restored: list[dict[str, str]] = []
        for turn in turns:
            content = turn.get("content", "")
            parts = content.split("\n助手: ", 1)
            if len(parts) == 2:
                user_msg = parts[0].replace("用户: ", "", 1)
                assistant_msg = parts[1]
                if user_msg:
                    restored.append({"role": "user", "content": user_msg})
                if assistant_msg:
                    restored.append({"role": "assistant", "content": assistant_msg})
            else:
                # 格式异常，兜底：整段作为 assistant 消息
                restored.append({"role": "assistant", "content": content})
        return restored
    except Exception:
        return []


async def node(state: AgentState) -> dict[str, Any]:
    """
    记忆加载节点：
    1. 从 short_term_memory 加载历史对话（按 conversation_id）
    2. 如果短期记忆为空，尝试从 FAISS 恢复（服务重启容灾）
    3. 从用户私有 FAISS 检索长期记忆（按 user_id）
    4. 加载指定家庭成员的健康档案（如有 member_id）
    """
    user_id = state.get("user_id", "")
    conversation_id = state.get("conversation_id", "")
    if not user_id:
        return {
            "short_term_history": [],
            "user_long_term_context": None,
            "_memory_loaded": True,
        }

    # 1. 加载短期记忆（按 conversation_id）
    short_term_history: list[dict[str, str]] = []
    history_text = ""
    if conversation_id:
        short_memory = get_short_memory(conversation_id)

        # 1a. 如果短期记忆为空，尝试从 conversation_service 恢复
        if short_memory.message_count == 0:
            from server.services.conversation_service import conversation_service
            stored_messages = conversation_service.get_messages(conversation_id)
            if stored_messages:
                for msg in stored_messages:
                    short_memory.add(msg["content"], msg["role"], msg.get("metadata", {}))

        # 1b. 如果仍然为空，尝试从 FAISS 恢复
        if short_memory.message_count == 0:
            restored_turns = await _restore_from_faiss(user_id, conversation_id)
            if restored_turns:
                short_memory.restore_from_turns(restored_turns)

        short_term_history = short_memory.get_messages(max_tokens=2000)
        history_text = short_memory.get_history_context(max_tokens=1500)

    # 2. 从用户向量库检索长期记忆（按 user_id）
    query = ""
    messages = state.get("messages", [])
    for msg in reversed(messages):
        if msg.get("role") == "user":
            query = msg.get("content", "")
            break

    user_long_term_context = None
    if query:
        try:
            memory_results = await vector_store_service.search_user_index(
                user_id=user_id,
                query=query,
                top_k=3,
            )
            if memory_results:
                memory_texts = [
                    f"[{r.get('metadata', {}).get('category', '记忆')}] {r['content']}"
                    for r in memory_results
                    if r.get("content")
                ]
                if memory_texts:
                    user_long_term_context = "【用户的长期记忆】\n" + "\n".join(memory_texts)
        except Exception:
            user_long_term_context = None

    # 3. 将历史文本注入 context 供后续节点使用
    context = state.get("context", {}) or {}
    if history_text:
        context["conversation_history"] = history_text

    # 4. 加载指定成员的健康档案（如有 member_id）
    member_id = state.get("member_id")
    if member_id:
        member = await member_service.get(member_id)
        if member:
            member_profile = member_service.to_summary_text(member)
            context["member_profile"] = member_profile
            return {
                "short_term_history": short_term_history,
                "user_long_term_context": user_long_term_context,
                "context": context,
                "member_profile": member_profile,
                "_memory_loaded": True,
            }

    return {
        "short_term_history": short_term_history,
        "user_long_term_context": user_long_term_context,
        "context": context,
        "member_profile": state.get("member_profile"),
        "_memory_loaded": True,
    }


def memory_load_node(state: AgentState) -> dict[str, Any]:
    """同步包装器"""
    import asyncio
    return asyncio.run(node(state))
