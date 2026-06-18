# src/agent_runtime/graph/state.py
from typing import Any, Literal, Optional, List, Annotated
from typing_extensions import TypedDict
from pydantic import BaseModel

from agent_runtime.graph.reducers import (
    reduce_append,
    reduce_unique_str_list,
    reduce_artifact_refs
)

class MacroAgentState(TypedDict, total=False):
    # -- 身份信息与上下文静态变量（使用默认的 Override） --
    thread_id: str
    run_id: str
    user_query: str
    parsed_request: dict
    context_bundle: dict
    selected_skills: List[str]
    
    # -- 核心分析计划与其排他状态机位置（使用默认的 Override，以最新Edit/调整为准） --
    analysis_plan: dict
    plan_status: Literal["not_started", "drafted", "approved", "executing", "done"]
    approval_status: Literal["not_required", "pending", "approved", "rejected", "edited"]
    
    # -- 需要去重追加的外部系统指针与引用（严禁放入大实体，只放 Ref 和元数据） --
    active_job_ids: Annotated[List[str], reduce_unique_str_list]
    completed_job_results: Annotated[List[dict], reduce_artifact_refs]
    artifact_refs: Annotated[List[dict], reduce_artifact_refs]
    
    # -- 只增不减的确定性可审计历史足迹与错误累积（Append-only Reducer） --
    trace_events: Annotated[List[dict], reduce_append]
    errors: Annotated[List[dict], reduce_append]
    messages: Annotated[List[Any], reduce_append]  # 保留对底层 LLM 交互标准的兼容
    
    # -- 最终交付给用户的终审文本（Override） --
    final_answer: Optional[str]
    status: Literal[
        "created",
        "running",
        "waiting_for_approval",
        "waiting_for_job",
        "completed",
        "failed",
        "cancelled"
    ]
    
    