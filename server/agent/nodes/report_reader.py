"""报告解读节点 - 支持 OCR 文本输入"""
from server.agent.state import AgentState
from server.services.llm_service import llm_service
from server.services.trace_service import trace_service

REPORT_READER_PROMPT = """你是一个专业的医疗报告解读专家。请分析用户提供的报告内容，提供详细的解读和建议。

报告内容：
{report_content}

用户问题：{question}

请提供：
1. 报告概览
2. 主要指标解读
3. 异常指标说明
4. 参考建议
5. 注意事项

注意：如果报告中包含专业术语，请用通俗易懂的语言解释。"""


async def node(state: AgentState) -> AgentState:
    """报告解读节点"""
    trace_service.start_node("report_reader", "report_reader_start")

    messages = state.get("messages", [])
    user_message = messages[-1]["content"] if messages else ""
    context = state.get("context", {}) or {}

    try:
        # 优先使用 OCR 文本（来自 uploaded report），否则使用用户消息
        ocr_text = context.get("ocr_text")
        report_content = ocr_text if ocr_text else user_message

        # 调用 LLM 解读（结果由 respond 节点输出）
        prompt = llm_service.format_prompt("report_reader_prompt", REPORT_READER_PROMPT,
            report_content=report_content, question=user_message)
        response = await llm_service.chat(
            messages=[{"role": "user", "content": prompt}],
            system="你是一个专业的医疗报告解读专家，有丰富的临床经验。"
        )

        trace_service.end_node({"has_content": bool(report_content), "from_ocr": bool(ocr_text)})

        return {
            "context": {
                **context,
                "report_content": report_content,
            }
        }
    except Exception as e:
        trace_service.end_node({"error": str(e)}, error=str(e))
        return {"error": str(e)}
