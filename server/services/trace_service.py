"""执行追踪服务 (Langfuse SDK v4.5)"""
import uuid
import time
import os
import contextvars
import logging
from dataclasses import dataclass, field, asdict
from typing import Any

from server.config import settings

logger = logging.getLogger(__name__)

# 使用 ContextVar 实现每个异步请求的追踪隔离（解决并发安全问题）
_current_trace_var: contextvars.ContextVar['Trace | None'] = contextvars.ContextVar(
    'trace_service_current_trace', default=None
)


@dataclass
class TraceEvent:
    """追踪事件"""
    event_id: str
    event_type: str
    node_name: str
    timestamp: float
    input_data: dict[str, Any] = field(default_factory=dict)
    output_data: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)
    duration_ms: float | None = None
    error: str | None = None


@dataclass
class Trace:
    """追踪记录"""
    trace_id: str
    conversation_id: str
    user_id: str
    start_time: float
    end_time: float | None = None
    events: list[TraceEvent] = field(default_factory=list)
    final_state: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)


class TraceService:
    """追踪服务 (Langfuse SDK v4)"""

    def __init__(self):
        self._traces: dict[str, Trace] = {}
        self._current_event: TraceEvent | None = None
        # v4 SDK 客户端的引用（惰性初始化）
        self._langfuse_client = None
        # v4 observation 对象：当前节点的 span（start_node 创建，end_node 结束）
        self._current_lf_span: Any = None
        self._callback_handler = None

    # ═══════════════════════════════════════════════
    #  SDK 初始化
    # ═══════════════════════════════════════════════

    def _init_langfuse(self):
        """延迟初始化 Langfuse"""
        if self._langfuse_client is not None:
            return

        # ★ 防止代理软件拦截 localhost 请求
        if "localhost" not in os.environ.get("NO_PROXY", "") and \
           "localhost" not in os.environ.get("no_proxy", ""):
            _existing = os.environ.get("NO_PROXY", os.environ.get("no_proxy", "")).strip(",")
            _merged = f"localhost,127.0.0.1,{_existing}".strip(",").strip()
            os.environ["NO_PROXY"] = _merged
            os.environ["no_proxy"] = _merged

        # ★ 关闭 SDK 自动埋点，只用手动追踪
        os.environ.setdefault("LANGFUSE_ENABLE_DEFAULT_INSTRUMENTORS", "false")

        try:
            from langfuse import Langfuse

            if settings.langfuse_public_key and settings.langfuse_secret_key:
                self._langfuse_client = Langfuse(
                    public_key=settings.langfuse_public_key,
                    secret_key=settings.langfuse_secret_key,
                    host=settings.langfuse_base_url,
                )
                logger.info("Langfuse SDK v4 客户端已创建")

                # 自动创建 Dataset
                try:
                    self.create_dataset()
                except Exception:
                    pass  # 不影响主流程
        except ImportError:
            logger.warning("langfuse 未安装，降级为本地追踪")
            return

        # CallbackHandler（供 LangChain / LangGraph 使用）
        if self._langfuse_client:
            try:
                from langfuse.langchain import CallbackHandler
                self._callback_handler = CallbackHandler()
            except ImportError:
                logger.warning("langfuse CallbackHandler 不可用（降级为手动追踪）")

    def get_callback_handler(self):
        """获取 Langfuse CallbackHandler（用于 LangChain/LangGraph）"""
        self._init_langfuse()
        return self._callback_handler

    def get_langfuse_client(self):
        """获取 Langfuse 客户端实例"""
        self._init_langfuse()
        return self._langfuse_client

    def get_current_trace(self) -> 'Trace | None':
        """获取当前异步上下文的追踪记录"""
        return _current_trace_var.get()

    def get_current_lf_observation(self) -> Any:
        """获取当前 Langfuse observation 对象（用于挂载 child generation）

        v4 API: generation 必须通过 parent_obs.start_observation(...) 创建。
        优先级：当前节点 span > 根 trace chain
        """
        if self._current_lf_span:
            return self._current_lf_span
        current = _current_trace_var.get()
        if current:
            return current.metadata.get("_lf_root_obs")
        return None

    # ═══════════════════════════════════════════════
    #  Trace 生命周期（顶层）
    # ═══════════════════════════════════════════════

    def start_trace(self, conversation_id: str, user_id: str) -> str:
        """开始追踪"""
        self._init_langfuse()

        trace_id = str(uuid.uuid4())[:8]
        trace_obj = Trace(
            trace_id=trace_id,
            conversation_id=conversation_id,
            user_id=user_id,
            start_time=time.time()
        )
        _current_trace_var.set(trace_obj)
        self._traces[trace_id] = trace_obj

        # ★ v4 API：用 start_observation 创建根节点（as_type="chain" 相当于 trace）
        if self._langfuse_client:
            try:
                root_obs = self._langfuse_client.start_observation(
                    name="medical_chat",
                    as_type="chain",
                    input={"conversation_id": conversation_id, "user_id": user_id},
                    metadata={"conversation_id": conversation_id},
                )
                trace_obj.metadata["_lf_root_obs"] = root_obs
                # 记录 trace_id（v4 自动生成，供后续参考）
                trace_obj.metadata["_lf_trace_id"] = root_obs.trace_id
                self._langfuse_client.flush()
                logger.info("Langfuse Trace 已创建: trace_id=%s obs_id=%s", trace_id, root_obs.id)
            except Exception as e:
                logger.exception("Langfuse 创建 Trace 失败: %s", e)

        return trace_id

    def propagate_session(self, session_id: str):
        """传播 session_id 到所有子 observation（Langfuse Sessions 分组）

        用法:
            with trace_service.propagate_session(conversation_id):
                result = await graph.ainvoke(state)
        """
        from contextlib import contextmanager
        @contextmanager
        def _ctx():
            self._init_langfuse()
            if self._langfuse_client:
                try:
                    from langfuse import propagate_attributes
                    with propagate_attributes(session_id=session_id):
                        yield
                        return
                except ImportError:
                    pass
                except Exception as e:
                    logger.warning("propagate_session 失败: %s", e)
            yield
        return _ctx()

    def end_trace(self, final_state: dict[str, Any]):
        """结束追踪，并自动将问答对存入 Langfuse Dataset"""
        current = _current_trace_var.get()
        if not current:
            return

        current.end_time = time.time()
        current.final_state = final_state

        # ★ v4 API：结束根 observation
        root_obs = current.metadata.pop("_lf_root_obs", None)
        if root_obs:
            try:
                root_obs.update(output=final_state)
                root_obs.end()
            except Exception as e:
                logger.exception("Langfuse 结束 Trace 失败: %s", e)

        # flush
        if self._langfuse_client:
            try:
                self._langfuse_client.flush()
            except Exception:
                pass

        # 自动存入 Dataset（用于批量回归测试）
        self._save_to_dataset(current, final_state)

        # 自动评分
        self._auto_score_trace(current, final_state)

        _current_trace_var.set(None)

    # ═══════════════════════════════════════════════
    #  节点生命周期
    # ═══════════════════════════════════════════════

    def start_node(self, node_name: str, event_type: str = "node_start"):
        """节点开始"""
        current_trace = _current_trace_var.get()
        if current_trace:
            event_id = str(uuid.uuid4())[:8]
            self._current_event = TraceEvent(
                event_id=event_id,
                event_type=event_type,
                node_name=node_name,
                timestamp=time.time()
            )

            # ★ v4 API：在根节点下创建 child span
            root_obs = current_trace.metadata.get("_lf_root_obs")
            if root_obs:
                try:
                    node_span = root_obs.start_observation(
                        name=node_name,
                        as_type="span",
                        input={"event_type": event_type},
                    )
                    self._current_lf_span = node_span
                except Exception as e:
                    logger.warning("Langfuse 创建 Span 失败: %s", e)
                    self._current_lf_span = None

    def end_node(
        self,
        output_data: dict[str, Any] | None = None,
        error: str | None = None
    ):
        """节点结束"""
        current = _current_trace_var.get()
        if self._current_event and current:
            self._current_event.output_data = output_data or {}
            self._current_event.duration_ms = (
                time.time() - self._current_event.timestamp
            ) * 1000
            self._current_event.error = error
            current.events.append(self._current_event)

            # ★ v4 API：结束 child span
            if self._current_lf_span:
                try:
                    self._current_lf_span.update(output=output_data or {})
                    if error:
                        self._current_lf_span.update(metadata={"error": error})
                    self._current_lf_span.end()
                except Exception as e:
                    logger.warning("Langfuse 结束 Span 失败: %s", e)
                self._current_lf_span = None

            self._current_event = None

    # ═══════════════════════════════════════════════
    #  LLM Generation 手动上报
    # ═══════════════════════════════════════════════

    def create_generation(
        self,
        input_text: str,
        output_text: str,
        model: str | None = None,
        usage: dict[str, int] | None = None,
    ):
        """在当前 trace/span 下创建 LLM generation（v4 API）"""
        parent_obs = self.get_current_lf_observation()
        if not parent_obs:
            return

        try:
            gen = parent_obs.start_observation(
                name="llm_call",
                as_type="generation",
                model=model or settings.llm_model,
                input=input_text,
                output=output_text,
                usage_details=usage or {},
            )
            gen.end()
            if self._langfuse_client:
                self._langfuse_client.flush()
        except Exception as e:
            logger.exception("Langfuse 上报 Generation 失败: %s", e)

    # ═══════════════════════════════════════════════
    #  元数据 & 查询
    # ═══════════════════════════════════════════════

    def add_metadata(self, key: str, value: Any):
        """添加元数据"""
        current = _current_trace_var.get()
        if current:
            current.metadata[key] = value

    def get_last_trace_id(self) -> str | None:
        """获取当前追踪ID"""
        current = _current_trace_var.get()
        return current.trace_id if current else None

    def get_trace(self, trace_id: str) -> Trace | None:
        """获取追踪记录"""
        return self._traces.get(trace_id)

    def get_all_traces(self) -> list[Trace]:
        """获取所有追踪记录"""
        return list(self._traces.values())

    def get_conversation_traces(self, conversation_id: str) -> list[Trace]:
        """获取对话的所有追踪"""
        return [
            t for t in self._traces.values()
            if t.conversation_id == conversation_id
        ]

    def export_trace(self, trace_id: str) -> dict[str, Any] | None:
        """导出追踪数据"""
        trace = self._traces.get(trace_id)
        if trace:
            return asdict(trace)
        return None

    # ═══════════════════════════════════════════════
    #  Langfuse Datasets（批量回归测试）
    # ═══════════════════════════════════════════════

    DATASET_NAME = "medical-chat-dataset"

    def create_dataset(self):
        """创建 Dataset（幂等，已存在则跳过）"""
        self._init_langfuse()
        if not self._langfuse_client:
            return
        try:
            self._langfuse_client.create_dataset(
                name=self.DATASET_NAME,
                description="医疗助手自动采集的问答数据集，用于 prompt 回归测试",
                metadata={"source": "auto-collect", "project": "medical-assistant"},
            )
            logger.info("Langfuse Dataset 已创建: %s", self.DATASET_NAME)
        except Exception as e:
            logger.debug("Dataset 创建/已存在: %s", e)

    def _save_to_dataset(self, trace: Trace, final_state: dict[str, Any]):
        """将本次对话的问答对存入 Dataset（后台异步，不阻塞主流程）"""
        self._init_langfuse()
        if not self._langfuse_client:
            return

        # 提取用户问题和助手回答
        messages = trace.final_state.get("messages", [])
        user_message = ""
        for msg in reversed(messages):
            if isinstance(msg, dict) and msg.get("role") == "user":
                user_message = msg.get("content", "")
                break
        response = final_state.get("response", "")
        intent = final_state.get("intent")

        if not user_message or not response or response.startswith("抱歉"):
            return  # 跳过无效或错误回复

        try:
            self._langfuse_client.create_dataset_item(
                dataset_name=self.DATASET_NAME,
                input={
                    "user_message": user_message,
                    "conversation_id": trace.conversation_id,
                    "user_id": trace.user_id,
                    "intent": intent.value if intent else None,
                },
                expected_output={
                    "response": response,
                    "intent": intent.value if intent else None,
                },
                metadata={
                    "trace_id": trace.trace_id,
                    "timestamp": trace.start_time,
                    "duration_s": round((trace.end_time or time.time()) - trace.start_time, 2),
                },
            )
        except Exception as e:
            logger.warning("存入 Dataset 失败（不影响主流程）: %s", e)

    # ═══════════════════════════════════════════════
    #  Langfuse Scores（自动评分 + 用户反馈）
    # ═══════════════════════════════════════════════

    def _auto_score_trace(self, trace: Trace, final_state: dict[str, Any]):
        """对话结束后自动打分（不阻塞主流程）

        自动评分维度：
        - latency_score: 响应速度评分 (0-1)
        - response_quality: 回复质量 (基于评估节点结果, 0-1)
        - has_error: 是否出错 (布尔)
        - response_length_ratio: 回复长度合理性 (0-1)
        """
        self._init_langfuse()
        if not self._langfuse_client or not trace.metadata.get("_lf_trace_id"):
            return

        lf_trace_id = trace.metadata["_lf_trace_id"]
        duration_s = (trace.end_time or time.time()) - trace.start_time
        response = final_state.get("response", "")
        error = final_state.get("error")
        evaluation = final_state.get("context", {}).get("evaluation")

        # 1. 延迟评分：10s 内满分，30s 以上递减
        if duration_s <= 10:
            latency_score = 1.0
        elif duration_s <= 20:
            latency_score = 0.8
        elif duration_s <= 30:
            latency_score = 0.6
        else:
            latency_score = max(0.2, 1.0 - (duration_s - 10) / 40)

        # 2. 回复质量：取 evaluate 节点结果（如果有）
        if evaluation and isinstance(evaluation, dict):
            quality_score = evaluation.get("total_score", None)
            if quality_score is not None:
                quality_score = min(quality_score / 10.0, 1.0)  # 归一化到 0-1
        else:
            quality_score = None

        # 3. 回复长度合理性：50-500 字为最佳区间
        resp_len = len(response)
        if 50 <= resp_len <= 500:
            length_score = 1.0
        elif resp_len < 50:
            length_score = max(0.2, resp_len / 50.0)
        else:
            length_score = max(0.3, 1.0 - (resp_len - 500) / 1000.0)

        scores_to_create = [
            ("latency_score", latency_score, "NUMERIC",
             f"响应耗时 {duration_s:.1f}s"),
            ("has_error", 0 if error else 1, "BOOLEAN",
             error if error else "无错误"),
            ("response_length_ratio", length_score, "NUMERIC",
             f"回复 {resp_len} 字符"),
        ]
        if quality_score is not None:
            scores_to_create.append((
                "response_quality", quality_score, "NUMERIC",
                f"evaluate 节点评分 {quality_score * 10:.1f}/10"
            ))

        for name, value, data_type, comment in scores_to_create:
            try:
                self._langfuse_client.create_score(
                    name=name,
                    value=value,
                    trace_id=lf_trace_id,
                    data_type=data_type,
                    comment=comment,
                    score_id=f"{lf_trace_id}-{name}",  # 幂等键，可更新
                )
            except Exception as e:
                logger.debug("创建 score '%s' 失败: %s", name, e)

    def submit_user_feedback(self, conversation_id: str, user_id: str,
                              score_value: int | float, comment: str = ""):
        """提交用户反馈评分

        Args:
            conversation_id: 对话 ID（用于关联 session）
            user_id: 用户 ID
            score_value: 分数（如 1=点赞/0=点踩，或 1-5 星）
            comment: 可选备注
        """
        self._init_langfuse()
        if not self._langfuse_client:
            return False
        try:
            self._langfuse_client.create_score(
                name="user_feedback",
                value=float(score_value),
                session_id=conversation_id,
                data_type="NUMERIC",
                comment=f"user={user_id}; {comment}",
                score_id=f"{conversation_id}-user_feedback",  # 幂等：同一会话只保留最新反馈
            )
            logger.info("用户反馈已记录: conversation=%s score=%s", conversation_id, score_value)
            return True
        except Exception as e:
            logger.warning("提交用户反馈失败: %s", e)
            return False


trace_service = TraceService()
