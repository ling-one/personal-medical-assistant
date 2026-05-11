"""生活方式建议节点"""
from server.agent.state import AgentState
from server.services.llm_service import llm_service
from server.services.trace_service import trace_service

LIFESTYLE_PROMPT = """你是一个专业的健康生活方式顾问。请为用户提供个性化的生活方式建议。

用户信息：
{user_info}

用户问题/需求：{question}

请从以下方面提供建议：
1. 饮食建议
2. 运动建议
3. 作息建议
4. 心理调节
5. 其他健康习惯

请确保建议是安全、科学、可操作的。"""


async def node(state: AgentState) -> AgentState:
    """生活方式建议节点"""
    trace_service.start_node("lifestyle", "lifestyle_start")
    
    messages = state.get("messages", [])
    user_message = messages[-1]["content"] if messages else ""

    try:
        # 生成建议（不依赖个人档案，由LLM根据对话内容判断）
        prompt = llm_service.format_prompt("lifestyle_prompt", LIFESTYLE_PROMPT,
            user_info="根据对话内容提供建议", question=user_message)
        response = await llm_service.chat(
            messages=[{"role": "user", "content": prompt}],
            system="你是一个热情、专业的健康生活方式顾问。你的建议要积极、正向，让用户感到被鼓励。"
        )
        
        trace_service.end_node({"has_user_info": False})
        
        return {
            "suggestions": [
                "查看更多饮食建议",
                "制定运动计划",
                "预约体检",
            ]
        }
    except Exception as e:
        trace_service.end_node({"error": str(e)}, error=str(e))
        return {"error": str(e)}
