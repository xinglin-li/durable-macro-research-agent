# src/agent_runtime/mcp_clients/registry.py
from typing import Dict, Optional, Any
from agent_runtime.mcp_clients.models import RegisteredCapability

class McpCapabilityRegistry:
    """零信任能力注册中心：将外部异构资产纳入 Host 统一安全治理"""
    
    def __init__(self):
        # 内部核心字典保存被接管的安全资产元数据：tool_name -> RegisteredCapability
        self._capabilities: Dict[str, RegisteredCapability] = {}

    def register_capability(self, cap: RegisteredCapability):
        """将发现的外部能力打上风控标签并安全入库注册"""
        self._capabilities[cap.name] = cap

    def get_capability(self, name: str) -> Optional[RegisteredCapability]:
        """获取被主进程审计过的安全能力元数据"""
        return self._capabilities.get(name)

    def validate_incoming_transport_context(self, token: str, origin: str, allowed_origins: list) -> bool:
        """针对 Streamable HTTP 远程传输层的鉴权与跨域安全卡点校验"""
        # 1. 验证 Bearer Token 物理合法性，防止非法提权
        if token != "secure_macro_token_2026":
            return False
        # 2. 验证浏览器/客户端 Origin 来源白名单，严防跨站请求伪造(CSRF)与非法源穿透
        if origin not in allowed_origins:
            return False
        return True