# src/agent_runtime/graph/edges.py
from typing import Literal

from agent_runtime.graph.state import MacroAgentState


def decide_next_action(
    state: MacroAgentState,
) -> Literal["human_approval", "call_tool", "observe_tool_result", "finalize", "max_steps_hit"]:
    trace_count = len(state.get("trace_events", []))
    if trace_count >= 12:
        return "max_steps_hit"

    parsed = state.get("parsed_request", {})
    if parsed.get("intent") == "direct_answer":
        return "finalize"

    approval = state.get("approval_status")
    if approval == "pending":
        return "human_approval"
    if approval == "rejected":
        return "finalize"
    if approval == "edited":
        return "human_approval"

    active_jobs = state.get("active_job_ids", [])
    completed_job_ids = {j.get("job_id") for j in state.get("completed_job_results", [])}
    pending_jobs = [j for j in active_jobs if j not in completed_job_ids]

    if not active_jobs:
        return "call_tool"
    if pending_jobs:
        return "observe_tool_result"
    return "finalize"
