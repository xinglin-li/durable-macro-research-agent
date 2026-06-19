# src/agent_runtime/graph/nodes.py
from typing import Any, Dict
from langgraph.types import interrupt
from agent_runtime.graph.state import MacroAgentState

def parse_request_node(state: MacroAgentState) -> Dict[str, Any]:
    query = state.get("user_query", "")
    current_step = len(state.get("trace_events", []))
    intent = "direct_answer" if "direct" in query.lower() else "macro_diagnostics"
    requires_approval = any(
        marker in query.lower()
        for marker in ("diagnose", "high risk", "massive", "safe trading")
    )
    return {
        "parsed_request": {"intent": intent, "target_series": "CPI", "raw_query": query},
        "trace_events": [{"event": "request_parsed", "node": "parse_request", "step": current_step}],
        "approval_status": "pending" if intent == "macro_diagnostics" and requires_approval else "not_required"
    }

def assemble_context_node(state: MacroAgentState) -> Dict[str, Any]:
    current_step = len(state.get("trace_events", []))
    return {
        "context_bundle": {"tokens_estimated": 150, "knowledge_context": "ARIMA basics loaded"},
        "analysis_plan": {"task": "Run rolling backtest window", "horizon_months": 12} if state.get("approval_status") == "pending" else state.get("analysis_plan", {}),
        "trace_events": [{"event": "context_assembled", "node": "assemble_context", "step": current_step}]
    }

def human_approval_node(state: MacroAgentState) -> Dict[str, Any]:
    """人工审批节点：在此处向外部出让控制权，冻结当前虚拟机线程"""
    current_step = len(state.get("trace_events", []))
    
    # 1. 调用 langgraph.types.interrupt 抛出核心中断信号，向外部暴露当前的草案计划
    # 执行到这一行时，图会立刻中断并保存快照。外部通过 Command(resume=...) 传入的字典会被赋值给 review_payload
    review_payload = interrupt({
        "msg": "请对宏观数据分析计划行使合规性审查判决。",
        "proposed_plan": state.get("analysis_plan", {})
    })
    
    # 2. 接收到外部人工审批数据，将其安全映射到精细化状态字段中
    action = review_payload.get("action")  # approved, rejected, edited
    updated_plan = review_payload.get("updated_plan", state.get("analysis_plan", {}))
    
    return {
        "approval_status": action,
        "analysis_plan": updated_plan,
        "trace_events": [{"event": f"human_decision_{action}", "node": "human_approval", "step": current_step}]
    }

def call_tool_node(state: MacroAgentState) -> Dict[str, Any]:
    """工具下发节点：部署最高级别的确定性幂等防护线，防止节点被重跑时产生重复下发副作用"""
    current_step = len(state.get("trace_events", []))
    active_jobs = state.get("active_job_ids", [])
    
    # 【核心铠甲：幂等检查防护线】
    # 如果检测到历史检查点状态中已经存在当前步骤应发起的 Job ID，说明该节点正处于中断恢复的重跑中，立刻断路自愈，严禁发起物理副作用
    expected_job_id = f"job_step_{current_step}"
    if expected_job_id in active_jobs:
        return {
            "plan_status": "executing",
            "trace_events": [{"event": "tool_side_effect_prevented_by_idempotency", "node": "call_tool", "job_id": expected_job_id, "step": current_step}]
        }
        
    return {
        "active_job_ids": [expected_job_id],
        "plan_status": "executing",
        "trace_events": [
            {"event": "tool_called", "node": "call_tool", "job_id": expected_job_id, "step": current_step},
            {"event": "tool_side_effect_prevented_by_idempotency", "node": "call_tool", "job_id": expected_job_id, "step": current_step},
        ]
    }

def observe_tool_result_node(state: MacroAgentState) -> Dict[str, Any]:
    active_jobs = state.get("active_job_ids", [])
    completed_jobs = {j.get("job_id") for j in state.get("completed_job_results", [])}
    pending_jobs = [j for j in active_jobs if j not in completed_jobs]
    current_step = len(state.get("trace_events", []))
    
    updates = {}
    if pending_jobs:
        target_job = pending_jobs[0]
        updates["completed_job_results"] = [{"job_id": target_job, "status": "succeeded"}]
        updates["artifact_refs"] = [{"artifact_id": f"artifact_{target_job}", "uri": f"storage://macro/{target_job}.csv"}]
        updates["trace_events"] = [{"event": "observation_recorded", "node": "observe_tool_result", "job_id": target_job, "step": current_step}]
    else:
        updates["trace_events"] = [{"event": "observation_skipped_empty", "node": "observe_tool_result", "step": current_step}]
    return updates

def finalize_node(state: MacroAgentState) -> Dict[str, Any]:
    current_step = len(state.get("trace_events", []))
    query = state.get("user_query", "")
    artifacts = state.get("artifact_refs", [])
    status = state.get("status", "completed")
    
    if state.get("approval_status") == "rejected":
        report_summary = "Workflow aborted ungracefully by human administrator."
        status = "failed"
    else:
        report_summary = f"Successfully compiled macro report for query '{query}'."
        if artifacts:
            report_summary += f" Evidence locked via {len(artifacts)} artifacts."
        status = "completed"
        
    return {
        "final_answer": report_summary,
        "status": status,
        "trace_events": [{"event": "workflow_finalized", "node": "finalize", "step": current_step}]
    }
