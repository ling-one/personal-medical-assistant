"""意图分类节点"""
import json
import re
import logging
from server.agent.state import AgentState
from server.models.conversation import IntentType
from server.services.llm_service import llm_service
from server.services.trace_service import trace_service

logger = logging.getLogger(__name__)

CLASSIFY_PROMPT = """你是一个医疗问答系统的意图分类器。请分析用户消息，判断其意图类型。

意图类型：
1. health_qa - 健康知识问答（询问疾病、症状、健康知识等）
2. report_reader - 报告解读（解读体检报告、化验单、检查报告等）
3. drug_query - 用药查询（查询药品说明、用法用量、相互作用等）
4. health_analysis - 健康数据分析（基于个人健康档案进行分析）
5. lifestyle - 生活方式建议（饮食、运动、作息等健康建议）

用户消息：{message}

请只返回一个 JSON 对象，包含：
- intent: 意图类型
- confidence: 置信度 (0-1)
- reason: 判断理由

直接返回 JSON，不要有其他内容。"""


def _extract_json(text: str) -> dict | None:
    """从 LLM 回复中提取 JSON（兼容 markdown 包裹、前后空白等）"""
    # 尝试提取 ```json ... ``` 代码块
    block_match = re.search(r'```(?:json)?\s*\n?(.*?)\n?```', text, re.DOTALL)
    if block_match:
        text = block_match.group(1).strip()
    # 尝试提取 {...} 大括号内容
    brace_match = re.search(r'\{.*\}', text, re.DOTALL)
    if brace_match:
        text = brace_match.group(0)
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return None


async def node(state: AgentState) -> AgentState:
    """意图分类节点"""
    trace_service.start_node("classify", "classify_start")
    
    messages = state.get("messages", [])
    user_message = messages[-1]["content"] if messages else ""

    logger.debug("classify 节点开始，user_message='%s'", user_message)

    try:
        # 调用 LLM 进行分类
        prompt = llm_service.format_prompt("classify_prompt", CLASSIFY_PROMPT, message=user_message)
        response = await llm_service.chat(
            messages=[{"role": "user", "content": prompt}]
        )

        logger.debug("classify LLM 返回: %s", response[:200])
        
        # 鲁棒解析
        result = _extract_json(response)
        if result is None:
            logger.warning("分类 LLM 返回非 JSON 内容: %s...", response[:200])
            raise ValueError("无法解析 LLM 返回的 JSON")

        intent_str = result.get("intent", "health_qa")
        confidence = result.get("confidence", 0.5)
        
        # 转换意图
        try:
            intent = IntentType(intent_str)
        except ValueError:
            intent = IntentType.UNKNOWN
        
        trace_service.end_node({"intent": intent.value, "confidence": confidence})
        
        return {
            "intent": intent,
            "intent_confidence": confidence,
            "context": {**state.get("context", {}), "classify_reason": result.get("reason")}
        }
    except Exception as e:
        logger.exception("classify 节点异常: %s", e)
        trace_service.end_node({"error": str(e)}, error=str(e))
        return {
            "intent": IntentType.UNKNOWN,
            "error": str(e)
        }
