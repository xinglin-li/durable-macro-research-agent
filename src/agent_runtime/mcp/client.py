# src/agent_runtime/mcp/client.py
import asyncio
import json
from typing import Any, Dict, List, Optional

class AsyncMcpStdioClient:
    """自研无框架标准 MCP Stdio 客户端：通过标准管道行使跨进程微服务解耦"""
    
    def __init__(self, command: str, args: Optional[List[str]] = None):
        self.command = command
        self.args = args or []
        self.process: Optional[asyncio.subprocess.Process] = None
        self.read_task: Optional[asyncio.Task] = None
        self.request_id = 0
        # 维护当前正在等待响应的请求映射：id -> asyncio.Future
        self._pending_requests: Dict[int, asyncio.Future] = {}

    async def start(self):
        """启动外部子进程，强行接管其 stdio 读写管道"""
        self.process = await asyncio.create_subprocess_exec(
            self.command,
            *self.args,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        # 启动后台非阻塞监听任务，持续泵入、解析外部 Server 吐出的 JSON 数据帧
        self.read_task = asyncio.create_task(self._read_loop())

    async def _read_loop(self):
        """核心读循环：解析标准 JSON-RPC 2.0 响应协议帧"""
        try:
            while self.process and self.process.stdout:
                line = await self.process.stdout.readline()
                if not line:
                    break
                
                # 每一行数据必须是一个合法的 JSON 字符串
                data = json.loads(line.decode("utf-8").strip())
                resp_id = data.get("id")
                
                # 如果能在挂起字典中寻找到对应的 Future，说明响应匹配成功，原地解锁解网
                if resp_id is not None and resp_id in self._pending_requests:
                    future = self._pending_requests.pop(resp_id)
                    if not future.done():
                        future.set_result(data)
        except asyncio.CancelledError:
            pass
        except Exception as e:
            # 异常发生时，强制释放所有处于挂起傻等状态的 Future，防止主线程挂死
            for future in self._pending_requests.values():
                if not future.done():
                    future.set_exception(e)

    async def _send_request(self, method: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """遵循标准 JSON-RPC 2.0 封装格式向子进程写入数据"""
        if not self.process or not self.process.stdin:
            raise RuntimeError("MCP Server 进程未启动或管道已破裂。")
            
        self.request_id += 1
        current_id = self.request_id
        
        payload = {
            "jsonrpc": "2.0",
            "id": current_id,
            "method": method,
            "params": params or {}
        }
        
        # 建立当前请求的异步期待卡位
        future = asyncio.get_running_loop().create_future()
        self._pending_requests[current_id] = future
        
        # 串行化并强行写入子进程的 stdin，必须以 \n 结尾作为物理帧截断符
        json_bytes = (json.dumps(payload) + "\n").encode("utf-8")
        self.process.stdin.write(json_bytes)
        await self.process.stdin.drain()
        
        # 非阻塞傻等后台 _read_loop 将其唤醒
        return await future

    async def list_tools(self) -> List[Dict[str, Any]]:
        """调用 MCP 标准协议原语：获取外部服务器宣告的所有合法工具资产"""
        response = await self._send_request("tools/list")
        if "error" in response:
            raise RuntimeError(f"MCP list_tools 失败: {response['error']}")
        return response.get("result", {}).get("tools", [])

    async def call_tool(self, tool_name: str, arguments: Dict[str, Any]) -> Any:
        """调用 MCP 标准协议原语：触发跨进程物理工具执行"""
        params = {"name": tool_name, "arguments": arguments}
        response = await self._send_request("tools/call", params=params)
        if "error" in response:
            raise RuntimeError(f"MCP call_tool 执行致命失败: {response['error']}")
        return response.get("result", {})

    async def stop(self):
        """优雅关闭进程树，杜绝僵尸进程（Zombie Process）污染操作系统"""
        if self.read_task:
            self.read_task.cancel()
            try:
                await self.read_task
            except asyncio.CancelledError:
                pass
        if self.process:
            try:
                self.process.terminate()
                await self.process.wait()
            except Exception:
                pass