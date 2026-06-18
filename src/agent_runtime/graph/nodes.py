# src/agent_runtime/graph/nodes.py
from typing import Any, Dict
from agent_runtime.graph.state import MacroAgentState

def parse_request_node(state: MacroAgentState) -> Dict[str, Any]:
    """请求解析节点：从原始用户查询中提取推理意图，记录审计迹"""
    query = state.get("user_query", "")
    current_step = len(state.get("trace_events", []))
    
    # 模拟结构化参数解析
    intent = "direct_answer" if "direct" in query.lower() else "macro_diagnostics"
    
    return {
        "parsed_request": {"intent": intent, "target_series": "CPI", "raw_query": query},
        "trace_events": [{"event": "request_parsed", "node": "parse_request", "step": current_step}]
    }

def assemble_context_node(state: MacroAgentState) -> Dict[str, Any]:
    """上下文装配节点：模拟 Week 2 控制层装配高价值认知快照"""
    current_step = len(state.get("trace_events", []))
    return {
        "context_bundle": {"tokens_estimated": 150, "knowledge_context": "ARIMA basics & CPI SOP loaded"},
        "trace_events": [{"event": "context_assembled", "node": "assemble_context", "step": current_step}]
    }

def call_tool_node(state: MacroAgentState) -> Dict[str, Any]:
    """工具下发节点：生成一个待执行的任务线索（模拟提交长任务）"""
    current_step = len(state.get("trace_events", []))
    # 依据当前步数动态生成唯一的 Job ID 模拟连续工具循环调用
    simulated_job_id = f"job_step_{current_step}"
    
    return {
        "active_job_ids": [simulated_job_id],
        "plan_status": "executing",
        "trace_events": [{"event": "tool_called", "node": "call_tool", "job_id": simulated_job_id, "step": current_step}]
    }

def observe_tool_result_node(state: MacroAgentState) -> Dict[str, Any]:
    """结果观测节点：捕获当前pending的任务并模拟推进至成功，追加结果引用"""
    active_jobs = state.get("active_job_ids", [])
    completed_jobs = {j.get("job_id") for j in state.get("completed_job_results", [])}
    
    # 寻找到尚未标记完工的任务
    pending_jobs = [j for j in active_jobs if j not in completed_jobs]
    current_step = len(state.get("trace_events", []))
    
    updates = {}
    if pending_jobs:
        target_job = pending_jobs[0]
        # 追加已完成记录，间接完成任务出队
        updates["completed_job_results"] = [{"job_id": target_job, "status": "succeeded"}]
        updates["artifact_refs"] = [{"artifact_id": f"artifact_{target_job}", "uri": f"storage://macro/{target_job}.csv"}]
        updates["trace_events"] = [{"event": "observation_recorded", "node": "observe_tool_result", "job_id": target_job, "step": current_step}]
    else:
        updates["trace_events"] = [{"event": "observation_skipped_empty", "node": "observe_tool_result", "step": current_step}]
        
    return updates

def finalize_node(state: MacroAgentState) -> Dict[str, Any]:
    """终审交付节点：提取证据链并生成最终的研究交付成果报告"""
    current_step = len(state.get("trace_events", []))
    query = state.get("user_query", "")
    artifacts = state.get("artifact_refs", [])
    
    report_summary = f"Successfully compiled macro report for query '{query}'."
    if artifacts:
        report_summary += f" Evidence locked via {len(artifacts)} artifacts."
        
    return {
        "final_answer": report_summary,
        "status": "completed",
        "trace_events": [{"event": "workflow_finalized", "node": "finalize", "step": current_step}]
    }