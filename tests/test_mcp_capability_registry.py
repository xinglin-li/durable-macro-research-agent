# tests/test_mcp_capability_registry.py
import pytest
from agent_runtime.mcp_clients.models import RegisteredCapability
from agent_runtime.mcp_clients.registry import McpCapabilityRegistry
from agent_runtime.mcp_clients.policy import McpApprovalPolicyGate

@pytest.fixture
def populated_registry():
    """初始化一个受治理的能力安全注册表"""
    reg = McpCapabilityRegistry()
    # 注册一个低风险无锁工具
    reg.register_capability(RegisteredCapability(
        server_id="macro_srv_01", name="fetch_series", kind="tool",
        description="Fetch reader series", risk_level="low",
        requires_approval=False, allowed_roles=["researcher", "admin"], transport="stdio"
    ))
    # 注册一个高风险需要审批的人工锁工具（如清空或下架数据资产）
    reg.register_capability(RegisteredCapability(
        server_id="macro_srv_01", name="delete_artifact", kind="tool",
        description="Delete file storage", risk_level="high",
        requires_approval=True, allowed_roles=["admin"], transport="stdio"
    ))
    return reg

def test_http_transport_origin_and_token_boundary(populated_registry):
    """验证远程传输层边界：非法 Token 与恶意伪造源 Origin 必须被断然拒绝"""
    allowed = ["https://xinglin-systematic.sas.com"]
    
    # 场景 A：伪造错误的 Token
    assert populated_registry.validate_incoming_transport_context(
        token="BAD_HACKER_TOKEN", origin=allowed[0], allowed_origins=allowed
    ) is False
    
    # 场景 B：合法的 Token 但使用了来自跨站伪造的恶意 Origin 源
    assert populated_registry.validate_incoming_transport_context(
        token="secure_macro_token_2026", origin="https://evil-malicious-site.com", allowed_origins=allowed
    ) is False

def test_policy_gate_rbac_and_unregistered_tool_blocking(populated_registry):
    """验证合规策略：未注册的幻觉工具与低特权角色越界调用必须当场物理阻断"""
    gate = McpApprovalPolicyGate(populated_registry)
    
    # 1. 拦截完全没有注册过的黑盒注入工具
    decision, msg = gate.evaluate_tool_call("drop_all_tables", {}, "admin")
    assert decision == "deny"
    assert "not registered" in msg
    
    # 2. 拦截特权级不足的低特权用户（例如让 researcher 角色去执行高危的 delete_artifact 工具）
    decision_rbac, msg_rbac = gate.evaluate_tool_call("delete_artifact", {}, "researcher")
    assert decision_rbac == "deny"
    assert "Access Denied" in msg_rbac