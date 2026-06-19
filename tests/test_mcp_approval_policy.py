# tests/test_mcp_approval_policy.py
import pytest
from tests.test_mcp_capability_registry import populated_registry
from agent_runtime.mcp_clients.policy import McpApprovalPolicyGate

def test_policy_gate_high_risk_routing_to_hitl(populated_registry):
    """验证风险管控：低风险工具直接放行，高风险工具必须强制拦截并改道路由至人工审批锁"""
    gate = McpApprovalPolicyGate(populated_registry)
    
    # 场景一：低风险查看工具，角色对齐，参数无污染 -> 绿灯直接通过放行
    decision_low, msg_low = gate.evaluate_tool_call("fetch_series", {}, "researcher")
    assert decision_low == "allow"
    
    # 场景二：高风险特权级工具，即便管理员 admin 发起，也必须触发动态改道路由，扣下扳机上审批锁
    decision_high, msg_high = gate.evaluate_tool_call("delete_artifact", {}, "admin")
    assert decision_high == "route_to_hitl"
    assert "HITL Guard Engaged" in msg_high

def test_policy_gate_argument_schema_injection_blocking(populated_registry):
    """边界故障注入断言：当大模型试图下发携带恶意 Schema 注入参数时，策略网关必须精准识别并防御截断"""
    # 给 fetch_series 强制配上严格的参数约束元数据
    cap = populated_registry.get_capability("fetch_series")
    cap.input_schema = {"type": "object", "properties": {"series_id": {"type": "string"}}}
    
    gate = McpApprovalPolicyGate(populated_registry)
    
    # 模型试图下发带有注入攻击性质的额外非合规参数（如恶意拼接 SQL/路径）
    malicious_args = {"series_id": "CPI", "malicious_injected_sql_field": "DROP TABLE users;"}
    
    decision, msg = gate.evaluate_tool_call("fetch_series", malicious_args, "researcher")
    assert decision == "deny"
    assert "Schema Error" in msg