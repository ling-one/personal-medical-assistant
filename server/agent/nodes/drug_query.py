"""用药查询节点"""
from server.agent.state import AgentState
from server.services.llm_service import llm_service
from server.services.vector_store import vector_store_service
from server.services.trace_service import trace_service

DRUG_QUERY_PROMPT = """你是一个专业的药品咨询师。请根据用户提供的信息提供药品相关知识。

用户查询：{query}

相关资料：
{context}

请提供以下信息（如果适用）：
1. 药品基本信息
2. 适应症
3. 用法用量
4. 注意事项
5. 禁忌症
6. 不良反应
7. 药物相互作用

请注意：最终用药请遵医嘱，本回答仅供参考。"""


async def node(state: AgentState) -> AgentState:
    """用药查询节点"""
    trace_service.start_node("drug_query", "drug_query_start")
    
    messages = state.get("messages", [])
    user_message = messages[-1]["content"] if messages else ""
    
    try:
        # 检索药品信息
        search_results = await vector_store_service.search(
            query=user_message,
            top_k=5,
            filter_category="drug"
        )
        
        context = ""
        if search_results:
            context = "\n\n".join([
                f"- {r['content']}"
                for r in search_results
            ])
        else:
            context = "未找到相关药品信息，请咨询专业药师或医生。"
        
        # 生成回答
        prompt = llm_service.format_prompt("drug_query_prompt", DRUG_QUERY_PROMPT,
            query=user_message, context=context)
        response = await llm_service.chat(
            messages=[{"role": "user", "content": prompt}],
            system="你是一个专业的药品咨询师。提供准确、专业的药品信息，并提醒用户遵医嘱用药。"
        )
        
        trace_service.end_node({"drug_found": bool(search_results)})
        
        return {
            "search_results": search_results,
            "context": {**state.get("context", {}), "drug_context": context}
        }
    except Exception as e:
        trace_service.end_node({"error": str(e)}, error=str(e))
        return {"error": str(e)}
