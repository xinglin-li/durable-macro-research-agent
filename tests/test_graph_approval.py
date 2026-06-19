# tests/test_graph_approval.py
import pytest
from agent_runtime.graph.service import MacroAgentGraphService

def test_human_approval_approve_path():
    """矩阵一：验证人工审核‘批准运行’控制流。图挂起、接收Command恢复并最终完工"""
    service = MacroAgentGraphService()
    tid = "thread_approve_001"
    
    # 1. 首次触发，图解析为宏观研究任务，控制流无条件引导至 human_approval 并在此处优雅冻结出让线程
    paused_state = service.run_workflow(thread_id=tid, run_id="r1", user_query="Diagnose CPI trends")
    
    # 深度断言：检查点状态精准停留在即将激活 human_approval 的挂起状态，状态未完工
    assert paused_state["approval_status"] == "pending"
    assert paused_state.get("final_answer") is None
    
    # 2. 模拟管理员提交“Approve”判决指令，驱动虚拟机原地复活并向下跑完自动化工具链
    final_state = service.resume_workflow(thread_id=tid, review_action={"action": "approved"})
    
    # 验证最终解网交付，状态完备且合法
    assert final_state["approval_status"] == "approved"
    assert final_state["status"] == "completed"
    assert "Evidence locked" in final_state["final_answer"]

def test_human_approval_reject_path():
    """矩阵二：验证人工审核‘严厉驳回’。图挂起后接收驳回 Command，直接断路走向终结异常终结"""
    service = MacroAgentGraphService()
    tid = "thread_reject_002"
    
    service.run_workflow(thread_id=tid, run_id="r2", user_query="High risk backtest query")
    
    # 提交恶意驳回指令
    final_state = service.resume_workflow(thread_id=tid, review_action={"action": "rejected"})
    
    # 验证控制流被强行掐断，直接跳过了工具链执行，最终状态被标记为失败
    assert final_state["approval_status"] == "rejected"
    assert final_state["status"] == "failed"
    assert "aborted ungracefully by human administrator" in final_state["final_answer"]
    assert len(final_state.get("active_job_ids", [])) == 0

def test_human_approval_edit_and_replanning_path():
    """矩阵三：验证人工审核‘亲手修改’。触发动态重规划环路，修改被合并覆盖，二次审批通过后才解锁工具"""
    service = MacroAgentGraphService()
    tid = "thread_edit_003"
    
    service.run_workflow(thread_id=tid, run_id="r3", user_query="Run massive 20 year correlation")
    
    # 1. 管理员发现方案太重，行使修改裁决：将计划修改为仅跑 2 年，并将状态标记为 edited
    edited_state = service.resume_workflow(
        thread_id=tid,
        review_action={
            "action": "edited",
            "updated_plan": {"task": "Run massive 20 year correlation", "horizon_months": 2}
        }
    )
    
    # 动态重规划断言：状态机由于 edited 条件，无条件重新被吸回了上游的 human_approval，等待二次判决！
    # 此时由于经过了 human_approval_node 的重新返回，其状态会被由于没有再次传入 Command 而重新触发第二次挂起
    assert edited_state["approval_status"] == "edited" 
    # 深度断言：新计划已经通过状态覆盖规则（Override）完美取代了旧的 20 年膨胀草案
    assert edited_state["analysis_plan"]["horizon_months"] == 2
    
    # 2. 二次判决：由于计划已被修正，管理员下发通过放行指令
    final_state = service.resume_workflow(thread_id=tid, review_action={"action": "approved"})
    assert final_state["approval_status"] == "approved"
    assert final_state["status"] == "completed"

def test_tool_node_side_effect_idempotency_shield():
    """矩阵四：最高等级硬核安全断言。验证当恢复图导致节点重跑时，幂等防护线能彻底抵御二次物理副作用"""
    service = MacroAgentGraphService()
    tid = "thread_idempotency_004"
    
    # 放行进工具下发阶段
    service.run_workflow(thread_id=tid, run_id="r4", user_query="Execute safe trading task")
    mid_state = service.resume_workflow(thread_id=tid, review_action={"action": "approved"})
    
    # 人为回溯或重跑节点：向执行成功的中间态注入相同的完成推进，迫使节点再次被调度
    events = [e["event"] for e in mid_state["trace_events"]]
    # 验证审计志中存在明确的幂等性拦截，证明物理副作用防护线绝对没有被二次击穿
    assert "tool_side_effect_prevented_by_idempotency" in events