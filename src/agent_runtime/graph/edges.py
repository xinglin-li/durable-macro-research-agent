# src/agent_runtime/graph/edges.py
from typing import Literal
from agent_runtime.graph.state import MacroAgentState

def decide_next_action(state: MacroAgentState) -> Literal["call_tool", "observe_tool_result", "finalize", "max_steps_hit"]:
    """核心决策路由：行使状态机的表决检查权"""
    # 1. 业务级硬防护守卫：检查高层审计迹深度，防止恶意死循环挤爆 Token 预算
    trace_count = len(state.get("trace_events", []))
    if trace_count >= 8:  # 触碰训练营硬边界防护线
        return "max_steps_hit"
        
    # 2. 检查解析意图：如果是直接回答请求，不需要任何工具循环直接走向终点
    parsed = state.get("parsed_request", {})
    if parsed.get("intent") == "direct_answer":
        return "finalize"
        
    # 3. 核心集合差异对齐：对比下发任务与完工任务
    active_jobs = state.get("active_job_ids", [])
    completed_job_ids = {j.get("job_id") for j in state.get("completed_job_results", [])}
    
    pending_jobs = [j for j in active_jobs if j not in completed_job_ids]
    
    if not active_jobs:
        # 初始状态且没有下发过任何工具任务，引导进入工具调用
        return "call_tool"
        
    if pending_jobs:
        # 存在下发了但尚未观测到完工结果的任务，强制分叉进观测节点
        return "observe_tool_result"
        
    # 所有的工具任务和长任务全部完工，安全交付
    return "finalize"