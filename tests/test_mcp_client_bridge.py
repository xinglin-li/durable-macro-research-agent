# tests/test_mcp_client_bridge.py
import sys
import os
import pytest
import asyncio
import json
from agent_runtime.mcp.client import AsyncMcpStdioClient
from agent_runtime.mcp.bridge import McpToolBridge

# 1. 动态构造一个完全独立的外部物理 Python 脚本，模拟标准 MCP Server
MOCK_SERVER_CODE = """
import sys
import json

def listen_loop():
    for line in sys.stdin:
        if not line.strip():
            continue
        try:
            req = json.loads(line)
            req_id = req.get("id")
            method = req.get("method")
            
            if method == "tools/list":
                res = {
                    "jsonrpc": "2.0",
                    "id": req_id,
                    "result": {
                        "tools": [
                            {
                                "name": "mcp_arima_forecast",
                                "description": "Execute cross-process ARIMA calculation",
                                "inputSchema": {"type": "object", "properties": {"series_id": {"type": "string"}}}
                            }
                        ]
                    }
                }
            elif method == "tools/call":
                tool_name = req.get("params", {}).get("name")
                args = req.get("params", {}).get("arguments", {})
                sid = args.get("series_id", "UNKNOWN")
                
                res = {
                    "jsonrpc": "2.0",
                    "id": req_id,
                    "result": {
                        "content": [{"type": "text", "text": f"Mcp server output successfully for {sid}"}]
                    }
                }
            else:
                res = {"jsonrpc": "2.0", "id": req_id, "error": {"message": "Method not found"}}
                
            sys.stdout.write(json.dumps(res) + "\\n")
            sys.stdout.flush()
        except Exception as e:
            sys.stderr.write(str(e) + "\\n")
            sys.stderr.flush()

if __name__ == "__main__":
    listen_loop()
"""

@pytest.fixture
def mock_server_file(tmp_path):
    """在系统的临时隔离沙箱文件夹中创建外部 Server 实体文件"""
    server_path = tmp_path / "mock_mcp_server.py"
    server_path.write_text(MOCK_SERVER_CODE, encoding="utf-8")
    return str(server_path)

@pytest.mark.asyncio
async def test_mcp_stdio_client_and_bridge_full_lifecycle(mock_server_file):
    """全链路无框架跨进程通道联调集成测试"""
    # 1. 实例化客户端，指定使用当前操作系统的 Python 解释器去强制拉起外部子进程脚本
    client = AsyncMcpStdioClient(command=sys.executable, args=[mock_server_file])
    
    await client.start()
    
    try:
        # 2. 第一阶段：验证协议原语 tools/list 跨物理管道收发正常
        tools_list = await client.list_tools()
        assert len(tools_list) == 1
        assert tools_list[0]["name"] == "mcp_arima_forecast"
        assert "ARIMA calculation" in tools_list[0]["description"]
        
        # 3. 第二阶段：验证桥接器动态包装闭包函数的能力
        bridge = McpToolBridge(mcp_client=client)
        native_tool = bridge.convert_to_native_tool(tools_list[0])
        
        # 执行被桥接转换为本地结构的异步包装函数
        execution_result = await native_tool({"series_id": "USA_CPI_2026"})
        
        # 4. 终极断言：跨进程 JSON-RPC 往返通信完美解网，数据线索严密扣合
        assert execution_result["tool_name"] == "mcp_arima_forecast"
        assert execution_result["is_success"] is True
        assert "Mcp server output successfully for USA_CPI_2026" in execution_result["raw_output"]
        
    finally:
        # 5. 第三阶段：终结回收生命周期，防止系统残留僵尸子进程
        await client.stop()