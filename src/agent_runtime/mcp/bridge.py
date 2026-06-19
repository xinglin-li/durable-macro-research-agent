# src/agent_runtime/mcp/bridge.py
from typing import Any, Dict, Callable
from agent_runtime.mcp.client import AsyncMcpStdioClient

class McpToolBridge:
    """桥接器：将外部异构进程的 MCP 工具链动态熔铸为本地运行时可识别的计算原子"""
    
    def __init__(self, mcp_client: AsyncMcpStdioClient):
        self.client = mcp_client

    def convert_to_native_tool(self, mcp_tool_meta: Dict[str, Any]) -> Callable[[Dict[str, Any]], Any]:
        """将一个 MCP 协议元数据，动态包裹封装成一个标准的本地异步可执行实体"""
        tool_name = mcp_tool_meta["name"]
        
        # 动态生成符合闭包约束的本地可执行函数
        async def native_async_wrapper(arguments: Dict[str, Any]) -> Dict[str, Any]:
            # 1. 跨进程调用外部沙箱
            mcp_result = await self.client.call_tool(tool_name, arguments)
            
            # 2. 解析标准 MCP 响应包内容实体（通常包裹在 content 文本列表中）
            content_list = mcp_result.get("content", [])
            text_output = ""
            if content_list and content_list[0].get("type") == "text":
                text_output = content_list[0].get("text", "")
                
            return {
                "tool_name": tool_name,
                "raw_output": text_output,
                "is_success": True if "error" not in mcp_result else False
            }
            
        # 将原属于外部 Server 的 Schema 附加到本地闭包函数的元数据中，供后续控制层动态解析
        native_async_wrapper.__doc__ = mcp_tool_meta.get("description", "")
        native_async_wrapper.__name__ = tool_name
        return native_async_wrapper