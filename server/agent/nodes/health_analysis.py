"""健康数据分析节点 - 使用成员真实健康档案"""
from server.agent.state import AgentState
from server.services.llm_service import llm_service
from server.services.trace_service import trace_service

HEALTH_ANALYSIS_PROMPT = """你是一个专业的健康管理师。请基于用户的健康档案和个人数据，提供个性化的健康分析和建议。

用户健康档案：
{profile_info}

用户问题/需求：{question}

请提供：
1. 健康状况总评
2. 风险因素分析
3. 建议关注指标
4. 改善建议
5. 下一步行动建议"""

DEFAULT_PROFILE_INFO = """暂无健康档案信息。请提供您的健康数据，例如：
- 基本信息（年龄、性别、身高、体重）
- 体检报告
- 既往病史
- 当前用药"""


async def node(state: AgentState) -> AgentState:
    """健康数据分析节点"""
    trace_service.start_node("health_analysis", "health_analysis_start")

    messages = state.get("messages", [])
    user_message = messages[-1]["content"] if messages else ""

    try:
        # 优先使用成员真实健康档案，否则使用默认提示
        member_profile = state.get("member_profile")
        profile_info = member_profile if member_profile else DEFAULT_PROFILE_INFO

        prompt = llm_service.format_prompt("health_analysis_prompt", HEALTH_ANALYSIS_PROMPT,
            profile_info=profile_info, question=user_message)
        response = await llm_service.chat(
            messages=[{"role": "user", "content": prompt}],
            system="你是一个专业、细心的健康管理师。你的分析要基于科学依据，同时表达要温和、鼓励。"
        )

        trace_service.end_node({"has_profile": bool(member_profile)})

        return {
            "analysis_result": {"profile": profile_info, "analysis": response}
        }
    except Exception as e:
        trace_service.end_node({"error": str(e)}, error=str(e))
        return {"error": str(e)}
