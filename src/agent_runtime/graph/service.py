# src/agent_runtime/graph/service.py
from typing import Any, Dict, Optional, List
from agent_runtime.graph.persistence import CheckpointPersistenceManager
from agent_runtime.graph.builder import create_macro_agent_graph

class MacroAgentGraphService:
    """虚拟机服务管理器：负责驱动 Thread 隔离、崩溃恢复与时间旅行回溯"""
    
    def __init__(self, db_path: str = ":memory:"):
        # 1. 实例化底层硬持久化器
        self._persistence = CheckpointPersistenceManager.create_sqlite_checkpointer(db_path)
        self.checkpointer = self._persistence.__enter__()
        # 2. 将持久化器注入到图运行时中并编译
        self.graph = create_macro_agent_graph(checkpointer=self.checkpointer)

    def close(self) -> None:
        self._persistence.__exit__(None, None, None)

    def __del__(self) -> None:
        try:
            self.close()
        except Exception:
            pass
        
    def run_workflow(self, thread_id: str, run_id: str, user_query: str) -> Dict[str, Any]:
        """开启或接续一个特定 thread_id 的执行流"""
        # 控制配置字典： thread_id 是 LangGraph 区分多会话路由的唯一主键
        config = {"configurable": {"thread_id": thread_id}}
        
        initial_state ={
            "thread_id": thread_id,
            "run_id": run_id,
            "user_query": user_query,
            "status": "running"
        }
        # 通过传入 config，让运行时自动读取、追加该 thread 的最新检查点
        return self.graph.invoke(initial_state, config=config)
    
    def get_state_history(self, thread_id: str) -> List[Dict[str, Any]]:
        """回溯当前 Thread 的快照时间线，暴露每一个历史版本的镜像"""
        config = {"configurable": {"thread_id": thread_id}}
        history_chain = []
        
        # get_state_history 会由新到旧迭代返回当前 thread 所有的历史 CheckpointTuple
        for state_snapshot in self.graph.get_state_history(config):
            history_chain.append({
                "checkpoint_id": state_snapshot.config["configurable"].get("checkpoint_id"),
                "values": state_snapshot.values,
                "next_nodes": state_snapshot.next, # 下一步即将激活哪一个节点
            })
        return history_chain
