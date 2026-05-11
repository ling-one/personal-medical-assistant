"""记忆更新节点 - 更新短期记忆 + LLM 提取长期记忆 + 对话轮次持久化"""
import json
import time
from typing import Any

from server.agent.state import AgentState
from server.services.memory_service import get_short_memory
from server.services.vector_store import vector_store_service
from server.services.llm_service import llm_service

EXTRACT_PROMPT = """请从以下医患对话中，提取用户的重要健康信息。

用户消息: {user_message}
助手回复: {assistant_message}

请提取以下类别（如无则留空）：
1. symptoms — 用户提到的症状
2. conditions — 疾病、诊断
3. medications — 用药信息
4. preferences — 用户偏好
5. key_facts — 其他重要事实

仅返回 JSON 格式，不要有其他文字：
{{
    "symptoms": ["..."],
    "conditions": ["..."],
    "medications": ["..."],
    "preferences": ["..."],
    "key_facts": ["..."]
}}
"""


async def node(state: AgentState) -> dict[str, Any]:
    """
    记忆更新节点：
    1. 将本轮对话写入短期记忆（按 conversation_id）
    2. 用 LLM 提取关键信息存入用户私有向量库（按 user_id）
    3. 在 metadata 中记录 member_id（如有）
    """
    user_id = state.get("user_id", "")
    conversation_id = state.get("conversation_id", "")
    member_id = state.get("member_id")
    if not user_id:
        return {}

    messages = state.get("messages", [])
    response = state.get("response", "")
    if not messages or not response:
        return {}

    # 获取最后一条用户消息
    user_message = ""
    for msg in reversed(messages):
        if msg.get("role") == "user":
            user_message = msg.get("content", "")
            break
    if not user_message:
        return {}

    # 1. 更新短期记忆（按 conversation_id）
    if conversation_id:
        short_memory = get_short_memory(conversation_id)
        turn_order = short_memory.turn_count  # 当前轮次序号（0-based）
        short_memory.add(user_message, "user")
        short_memory.add(response, "assistant")

        # 1b. 持久化到 conversation_service
        from server.services.conversation_service import conversation_service
        conversation_service.add_message(conversation_id, "user", user_message, {"turn_order": turn_order})
        conversation_service.add_message(conversation_id, "assistant", response, {"turn_order": turn_order})

    # 2. 对话轮次持久化：将本轮完整对话存入 FAISS（双标签：user_id + conversation_id）
    if conversation_id:
        turn_text = f"用户: {user_message}\n助手: {response}"
        # 基础 metadata
        turn_metadata: dict[str, Any] = {
            "category": "conversation_turn",
            "user_id": user_id,
            "conversation_id": conversation_id,
            "role": "turn",
            "turn_order": turn_order,
            "timestamp": time.time(),
            "source": "conversation_history",
        }
        if member_id:
            turn_metadata["member_id"] = member_id

        await vector_store_service.add_to_user_index(
            user_id=user_id,
            texts=[turn_text],
            metadatas=[turn_metadata],
        )

    # 3. 长期记忆提取（仅一次）
    already_updated = state.get("_memory_updated", False)
    if not already_updated:
        try:
            extract_prompt = llm_service.format_prompt("memory_extract_prompt", EXTRACT_PROMPT,
                user_message=user_message, assistant_message=response)
            extraction_text = await llm_service.chat(
                messages=[{"role": "user", "content": extract_prompt}],
                system="你是一个医疗记忆提取助手。只输出 JSON。",
            )

            extracted = _parse_extraction(extraction_text)
            if extracted:
                texts: list[str] = []
                metadatas: list[dict[str, Any]] = []
                for category, items in extracted.items():
                    for item in items:
                        text = item.strip()
                        if text:
                            ext_metadata: dict[str, Any] = {
                                "category": category,
                                "user_id": user_id,
                                "conversation_id": conversation_id,
                                "source": "chat_extraction",
                            }
                            if member_id:
                                ext_metadata["member_id"] = member_id
                            texts.append(f"[{category}] {text}")
                            metadatas.append(ext_metadata)

                if texts:
                    await vector_store_service.add_to_user_index(
                        user_id=user_id,
                        texts=texts,
                        metadatas=metadatas,
                    )

            return {"_memory_updated": True}

        except Exception:
            # 提取失败不阻塞主流程
            return {"_memory_updated": True}

    return {"_memory_updated": True}


def _parse_extraction(text: str) -> dict[str, list[str]]:
    """解析 LLM 返回的 JSON"""
    try:
        start = text.index("{")
        end = text.rindex("}")
        json_str = text[start:end + 1]
        data = json.loads(json_str)
        return {
            "symptoms": data.get("symptoms", []),
            "conditions": data.get("conditions", []),
            "medications": data.get("medications", []),
            "preferences": data.get("preferences", []),
            "key_facts": data.get("key_facts", []),
        }
    except (ValueError, json.JSONDecodeError):
        return {}


def memory_update_node(state: AgentState) -> dict[str, Any]:
    """同步包装器"""
    import asyncio
    return asyncio.run(node(state))
