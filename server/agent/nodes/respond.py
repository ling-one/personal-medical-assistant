"""统一回复生成节点 - 支持记忆上下文注入 + SSE 流式推送"""
from server.agent.state import AgentState
from server.services.llm_service import llm_service
from server.services.trace_service import trace_service
from server.services.stream_manager import stream_manager

RESPOND_PROMPT = """你是一个专业的医疗健康助手。请根据以下信息，生成一个完整、友好的回复。

{memory_context}
对话历史：
{conversation_history}

当前意图：{intent}
用户消息：{user_message}

分析结果/上下文：
{context}

请生成一个最终的回复，确保：
1. 回答准确、专业
2. 语言通俗易懂
3. 包含适当的健康提醒
4. 建议用户咨询专业医生（必要时）"""

HEALTH_QA_RESPOND_PROMPT = """你是一个专业的医疗健康助手。请基于参考资料回答用户的问题，生成完整、友好的回复。

{memory_context}
对话历史：
{conversation_history}

用户问题：{user_message}

参考资料：
{retrieved_docs}

请生成一个最终的回复，确保：
1. 回答准确、专业
2. 语言通俗易懂
3. 包含适当的健康提醒
4. 建议用户咨询专业医生（必要时）
如果参考资料中没有足够信息，请基于你的医学知识回答，同时说明这一点。"""

UNKNOWN_RESPONSE = """您好！我是一个医疗健康助手，我可以帮您：

• 健康知识问答 - 解答您的健康问题
• 报告解读 - 帮您解读体检报告
• 用药查询 - 查询药品信息
• 健康分析 - 基于您的健康档案进行分析
• 生活方式建议 - 提供饮食、运动等健康建议

请问有什么可以帮您的？"""


def _build_memory_context(state: AgentState) -> str:
    """构建记忆上下文（含成员档案）"""
    memory_parts = []

    # 成员健康档案（优先展示）
    member_profile = state.get("member_profile")
    if member_profile:
        memory_parts.append(f"【咨询成员健康档案】\n{member_profile}")

    # 长期记忆
    user_long_term = state.get("user_long_term_context")
    if user_long_term:
        memory_parts.append(user_long_term)

    # 短期记忆
    short_term = state.get("short_term_history", [])
    if short_term:
        st_text = "\n".join([
            f"{'用户' if m['role'] == 'user' else '助手'}: {m['content']}"
            for m in short_term
        ])
        memory_parts.append(f"【短期记忆】\n{st_text}")

    memory_context = "\n\n".join(memory_parts)
    if memory_context:
        memory_context = f"用户记忆信息：\n{memory_context}\n"
    return memory_context


def _build_history(state: AgentState) -> str:
    """构建对话历史"""
    messages = state.get("messages", [])
    return "\n".join([
        f"{'用户' if m['role'] == 'user' else '助手'}: {m['content']}"
        for m in messages[:-1]
    ]) if len(messages) > 1 else "（首次对话）"


async def _stream_or_chat(
    state: AgentState,
    prompt: str,
    system: str,
) -> str:
    """统一处理流式与非流式 LLM 调用"""
    stream_queue = stream_manager.get_queue(state.get("conversation_id", ""))
    if stream_queue:
        full_response = ""
        async for chunk in llm_service.chat_stream(
            messages=[{"role": "user", "content": prompt}],
            system=system,
        ):
            if chunk:
                full_response += chunk
                await stream_queue.put(chunk)
        await stream_queue.put(None)
        return full_response
    else:
        return await llm_service.chat(
            messages=[{"role": "user", "content": prompt}],
            system=system,
        )


async def node(state: AgentState) -> AgentState:
    """统一回复生成节点"""
    trace_service.start_node("respond", "respond_start")

    messages = state.get("messages", [])
    intent = state.get("intent")
    user_message = messages[-1]["content"] if messages else ""

    try:
        memory_context = _build_memory_context(state)
        history = _build_history(state)

        if intent and intent.value == "unknown":
            response = UNKNOWN_RESPONSE
            stream_queue = stream_manager.get_queue(state.get("conversation_id", ""))
            if stream_queue:
                await stream_queue.put(response)
                await stream_queue.put(None)
        elif intent and intent.value == "health_qa":
            # 合并 health_qa：直接用检索结果 + 记忆生成回复，省去一次 LLM 调用
            retrieved_docs = state.get("retrieved_docs", [])
            docs_str = "\n\n".join([f"- {d}" for d in retrieved_docs]) if retrieved_docs else "无相关参考资料"
            prompt = llm_service.format_prompt(
                "health_qa_respond_prompt", HEALTH_QA_RESPOND_PROMPT,
                memory_context=memory_context or "",
                conversation_history=history,
                user_message=user_message,
                retrieved_docs=docs_str,
            )
            response = await _stream_or_chat(
                state, prompt,
                system="你是一个专业、温暖、可靠的医疗健康助手。"
            )
        else:
            context = state.get("context", {})
            context_str = "\n".join([
                f"- {k}: {v}" for k, v in context.items()
                if v and k not in ("messages", "conversation_history")
            ])
            prompt = llm_service.format_prompt(
                "respond_prompt", RESPOND_PROMPT,
                memory_context=memory_context or "",
                conversation_history=history,
                intent=intent.value if intent else "unknown",
                user_message=user_message,
                context=context_str or "无",
            )
            response = await _stream_or_chat(
                state, prompt,
                system="你是一个专业、温暖、可靠的医疗健康助手。"
            )

        trace_service.end_node({
            "response_length": len(response),
            "intent": intent.value if intent else "unknown",
        })

        return {
            "response": response,
            "suggestions": state.get("suggestions", [
                "还有其他问题吗？",
                "查看健康知识",
                "更新健康档案",
            ]),
        }
    except Exception as e:
        trace_service.end_node({"error": str(e)}, error=str(e))
        return {
            "response": "抱歉，服务出现了一些问题，请稍后再试。",
            "error": str(e),
        }
