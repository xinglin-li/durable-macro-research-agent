# src/agent_runtime/mcp_clients/policy.py
from typing import Any, Dict, Literal, Tuple
from agent_runtime.mcp_clients.registry import McpCapabilityRegistry

class McpApprovalPolicyGate:
    """合规策略网关：将模型的随意提议（Request）翻译翻译为安全的执行控制（Execution Decision）"""
    
    def __init__(self, registry: McpCapabilityRegistry):
        self.registry = registry
    
    def evaluate_tool_call(
        self,
        tool_name: str,
        arguments: Dict[str, Any],
        current_user_role: str
    ) -> Tuple[Literal["allow", "deny", "route_to_hitl"], str]:
        """安全模型评估中心：执行 Least Privilege 判决"""
        
        # 1. 拦截未知能力：如果大模型产生幻觉或试图下发未注册的黑盒工具，立刻物理切断
        cap = self.registry.get_capability(tool_name)
        if not cap:
            return "deny", f"Security Violation: Capability '{tool_name}' is not registered in the host."
        
        # 2. RBAC 鉴权：检查当前激活执行的图线程用户角色是否有权限触摸该工具
        if current_user_role not in cap.allowed_roles:
            return "deny", f"Access Denied: Role '{current_user_role}' has insufficient privileges for '{tool_name}'."
        
        # 3. 参数级边界强校验：模型下发的参数必须绝对契合输入 Schema 约束
        if cap.input_schema:
            properties = cap.input_schema.get("properties", {})
            for key in arguments.keys():
                if key not in properties:
                    return "deny", f"Schema Error: Malicious or invalid argument key '{key}' detected."

        # 4. 核心风险等级与人工审批挂起拦截（HITL 动态分叉）
        if cap.risk_level == "high" or cap.requires_approval:
            # 触碰高危红线或显式标记需要审批，拦截执行，强行引导图切入中断等待审批分支
            return "route_to_hitl", f"HITL Guard Engaged: '{tool_name}' exhibits high-risk status. Control routed to human approval lock."

        # 安全过关，允许推向底层的 MCP Client 异步通道执行
        return "allow", "Verification passed."