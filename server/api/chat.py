"""对话接口 - 适配会话隔离记忆（30分钟超时自动换对话ID）"""
import asyncio
import json
import os
from pydantic import BaseModel
from fastapi import APIRouter, HTTPException, WebSocket, WebSocketDisconnect
from sse_starlette.sse import EventSourceResponse
from typing import AsyncGenerator

from server.models.conversation import ChatRequest, ChatResponse, IntentType
from server.services.memory_service import get_short_memory
from server.agent.graph import medical_graph
from server.services.trace_service import trace_service
from server.services.user_service import user_service
from server.services.stream_manager import stream_manager
from server.services.member_service import member_service
from server.services.conversation_service import conversation_service
from server.config import settings

router = APIRouter()


async def _load_report_text(report_id: str, member_id: str | None) -> str | None:
    """根据 report_id 加载报告 OCR 文本"""
    if not member_id:
        return None
    report_path = os.path.join(settings.report_data_dir, member_id, f"{report_id}.json")
    if not os.path.exists(report_path):
        return None
    try:
        with open(report_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data.get("ocr_text")
    except (json.JSONDecodeError, KeyError):
        return None


class FeedbackRequest(BaseModel):
    """用户反馈请求"""
    conversation_id: str
    user_id: str
    score: int | float  # 1=点赞/0=点踩，或 1-5 星
    comment: str = ""


@router.post("/message", response_model=ChatResponse)
async def chat_message(request: ChatRequest):
    """发送消息并获取回复（自动管理 conversation_id，30分钟超时）"""
    try:
        # 验证用户是否存在
        if not user_service.user_exists(request.user_id):
            raise HTTPException(status_code=404, detail=f"用户 {request.user_id} 不存在，请先通过 /api/user/create 创建")

        # 优先使用用户传入的 conversation_id；未传入则按 (user, member) 自动获取
        if request.conversation_id and request.conversation_id.strip() and request.conversation_id != "string":
            conversation_id = request.conversation_id.strip()
            # 用户传入已有ID时，更新活跃时间防止该会话超时
            user_service.update_last_active(request.user_id)
        else:
            conversation_id, _ = conversation_service.get_or_create_conversation(
                request.user_id, request.member_id
            )

        # 开始追踪
        trace_id = trace_service.start_trace(conversation_id, request.user_id)

        # 解析 member_id → member_profile（供 Agent 注入）
        member_id = request.member_id
        member_profile = None
        group_id = None
        if member_id:
            member = await member_service.get(member_id)
            if member:
                member_profile = member_service.to_summary_text(member)
                group_id = member.group_id

        # 解析 report_id → OCR 文本（供报告解读）
        ocr_text = None
        if request.report_id:
            ocr_text = await _load_report_text(request.report_id, member_id)
            if ocr_text is None:
                raise HTTPException(status_code=404, detail="报告不存在")

        # 构建图输入（包含 trace_id，方便节点使用）
        graph_input = {
            "user_id": request.user_id,
            "conversation_id": conversation_id,
            "group_id": group_id,
            "member_id": member_id,
            "member_profile": member_profile,
            "messages": [{"role": "user", "content": request.message}],
            "intent": None,
            "context": {"ocr_text": ocr_text} if ocr_text else {},
            "short_term_history": [],
            "user_long_term_context": None,
            "trace_id": trace_id,
            "_memory_loaded": False,
            "_memory_updated": False,
        }

        # 执行图（传播 session_id 用于 Langfuse Sessions 分组）
        with trace_service.propagate_session(conversation_id):
            result = await medical_graph.ainvoke(graph_input)

        # 结束追踪
        trace_service.end_trace(result)

        return ChatResponse(
            conversation_id=result.get("conversation_id", conversation_id),
            message=result.get("response", ""),
            intent=result.get("intent", IntentType.UNKNOWN),
            suggestions=result.get("suggestions", []),
            trace_id=trace_id,
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/stream/{conversation_id}")
async def stream_chat(conversation_id: str, message: str, user_id: str = ""):
    """流式对话（SSE 逐 token 推送）"""
    async def event_generator() -> AsyncGenerator[dict, None]:
        # 创建流式队列
        queue = stream_manager.create_queue(conversation_id)
        trace_id = trace_service.start_trace(conversation_id, user_id)

        graph_input = {
            "user_id": user_id,
            "conversation_id": conversation_id,
            "group_id": None,
            "member_id": None,
            "member_profile": None,
            "messages": [{"role": "user", "content": message}],
            "short_term_history": [],
            "user_long_term_context": None,
            "trace_id": trace_id,
            "_memory_loaded": False,
            "_memory_updated": False,
        }

        # 在后台任务中执行图
        async def run_graph():
            try:
                with trace_service.propagate_session(conversation_id):
                    result = await medical_graph.ainvoke(graph_input)
                trace_service.end_trace(result)
            except Exception as e:
                trace_service.end_trace({}, error=str(e))
                # 通知前端出错
                await queue.put(f"【系统错误】{str(e)}")
                await queue.put(None)

        # 在后台任务中执行图（不 await，让 SSE 事件生成器并行读取队列）
        asyncio.create_task(run_graph())

        try:
            # 首先发送 intent 事件（可选：图刚开始时还没有 intent，靠后面节点推送）
            yield {"event": "status", "data": "processing"}

            # 从队列读取 LLM token，逐字推送给前端
            while True:
                token = await queue.get()
                if token is None:  # 结束标记
                    break
                if token:  # 跳过空 token
                    yield {"event": "message", "data": token}

            yield {"event": "done", "data": ""}

        except asyncio.CancelledError:
            pass  # 客户端断开连接
        finally:
            stream_manager.remove_queue(conversation_id)
            # 不取消 task，让 memory_update 在后台完成

    return EventSourceResponse(event_generator())


@router.websocket("/ws")
async def websocket_chat(websocket: WebSocket):
    """WebSocket 流式对话（逐 token 推送）"""
    await websocket.accept()
    conversation_id = ""

    try:
        data = await websocket.receive_json()
        message = data.get("message", "")
        user_id = data.get("user_id", "")
        raw_conversation_id = data.get("conversation_id", "")
        member_id = data.get("member_id") or None
        report_id = data.get("report_id") or None

        if not user_id:
            await websocket.send_json({"type": "error", "content": "缺少 user_id"})
            return
        if not user_service.user_exists(user_id):
            await websocket.send_json({"type": "error", "content": f"用户 {user_id} 不存在"})
            return

        # 分配/复用 conversation_id（按 member 隔离）
        if raw_conversation_id and raw_conversation_id.strip() and raw_conversation_id != "string":
            conversation_id = raw_conversation_id.strip()
            user_service.update_last_active(user_id)
        else:
            conversation_id, _ = conversation_service.get_or_create_conversation(
                user_id, member_id
            )

        # 先回复 conversation_id，便于前端保存
        await websocket.send_json({"type": "conversation_id", "content": conversation_id})

        # 加载成员档案
        trace_id = trace_service.start_trace(conversation_id, user_id)
        member_profile = None
        group_id = None
        if member_id:
            member = await member_service.get(member_id)
            if member:
                member_profile = member_service.to_summary_text(member)
                group_id = member.group_id

        # 加载报告 OCR 文本
        ocr_text = None
        if report_id:
            ocr_text = await _load_report_text(report_id, member_id)

        # 创建流式队列
        queue = stream_manager.create_queue(conversation_id)

        graph_input = {
            "user_id": user_id,
            "conversation_id": conversation_id,
            "group_id": group_id,
            "member_id": member_id,
            "member_profile": member_profile,
            "messages": [{"role": "user", "content": message}],
            "intent": None,
            "context": {"ocr_text": ocr_text} if ocr_text else {},
            "short_term_history": [],
            "user_long_term_context": None,
            "trace_id": trace_id,
            "_memory_loaded": False,
            "_memory_updated": False,
        }

        async def run_graph():
            try:
                with trace_service.propagate_session(conversation_id):
                    result = await medical_graph.ainvoke(graph_input)
                trace_service.end_trace(result)
            except Exception as e:
                trace_service.end_trace({}, error=str(e))
                # 通知前端出错
                try:
                    await queue.put(f"【系统错误】{str(e)}")
                except Exception:
                    pass
            finally:
                try:
                    await queue.put(None)
                except Exception:
                    pass

        asyncio.create_task(run_graph())

        # 逐 token 推送
        await websocket.send_json({"type": "status", "content": "processing"})
        while True:
            token = await queue.get()
            if token is None:
                break
            if token:
                await websocket.send_json({"type": "token", "content": token})

        await websocket.send_json({"type": "done"})

    except WebSocketDisconnect:
        pass
    except Exception as e:
        try:
            await websocket.send_json({"type": "error", "content": str(e)})
        except Exception:
            pass
    finally:
        if conversation_id:
            stream_manager.remove_queue(conversation_id)


@router.get("/history/{conversation_id}")
async def get_history(conversation_id: str):
    """获取对话历史（短期记忆）"""
    short_memory = get_short_memory(conversation_id)
    return short_memory.to_dict()


@router.get("/conversations")
async def get_conversations(user_id: str = ""):
    """获取用户的所有对话列表（按成员隔离）"""
    if not user_id:
        raise HTTPException(status_code=400, detail="缺少 user_id")
    conversations = conversation_service.list_conversations(user_id)
    return {"conversations": conversations}


@router.get("/messages/{conversation_id}")
async def get_conversation_messages(conversation_id: str):
    """获取指定对话的持久化消息列表"""
    messages = conversation_service.get_messages(conversation_id)
    return {"messages": messages}


@router.delete("/conversations")
async def clear_member_conversation(user_id: str = "", member_id: str = ""):
    """清除指定成员的对话"""
    if not user_id:
        raise HTTPException(status_code=400, detail="缺少 user_id")
    from server.services.memory_service import clear_short_memory
    # 先清除内存中的短期记忆
    conv_id = conversation_service.get_conversation_id_by_member(user_id, member_id or None)
    if conv_id:
        clear_short_memory(conv_id)
    # 再清除持久化文件
    success = conversation_service.clear_conversation(user_id, member_id or None)
    if success:
        return {"status": "ok", "message": "对话已清除"}
    raise HTTPException(status_code=404, detail="对话不存在")


@router.post("/feedback")
async def submit_feedback(request: FeedbackRequest):
    """提交用户反馈（点赞/点踩/评分），记录到 Langfuse Scores"""
    success = trace_service.submit_user_feedback(
        conversation_id=request.conversation_id,
        user_id=request.user_id,
        score_value=request.score,
        comment=request.comment,
    )
    if success:
        return {"status": "ok", "message": "反馈已记录"}
    raise HTTPException(status_code=500, detail="反馈提交失败，Langfuse 未连接")
