# src/agent_runtime/graph/service.py
from typing import Any, Dict, List
from langgraph.types import Command
from agent_runtime.graph.persistence import CheckpointPersistenceManager
from agent_runtime.graph.builder import create_macro_agent_graph

class MacroAgentGraphService:
    def __init__(self, db_path: str = ":memory:"):
        self._persistence = CheckpointPersistenceManager.create_sqlite_checkpointer(db_path)
        self.checkpointer = self._persistence.__enter__()
        self.graph = create_macro_agent_graph(checkpointer=self.checkpointer)

    def close(self) -> None:
        self._persistence.__exit__(None, None, None)

    def __del__(self) -> None:
        try:
            self.close()
        except Exception:
            pass

    def run_workflow(self, thread_id: str, run_id: str, user_query: str) -> Dict[str, Any]:
        config = {"configurable": {"thread_id": thread_id}}
        initial_state = {"thread_id": thread_id, "run_id": run_id, "user_query": user_query, "status": "running"}
        
        # 使用 stream 模式或普通 invoke。当遇到节点内部的 interrupt 时，图会在此处优雅中断抛出，
        # 并将最新的 Checkpoint 存入数据库。我们使用 invoke 接收返回的状态
        return self.graph.invoke(initial_state, config=config)

    def resume_workflow(self, thread_id: str, review_action: dict) -> Dict[str, Any]:
        """向处于中断挂起状态的 Thread 虚拟机注入外部人工审查判决，使其原地复活"""
        config = {"configurable": {"thread_id": thread_id}}
        
        # 利用 langgraph.types.Command 优雅传递恢复数据给上一次阻断的 interrupt 接收器
        # 这就是原生支持 Durable Execution 的高级恢复指令
        resume_command = Command(resume=review_action)
        
        # 传入包含 Command 的指令和对应的 Thread 隔离配置，驱动图向下推进
        return self.graph.invoke(resume_command, config=config)

    def get_state_history(self, thread_id: str) -> List[Dict[str, Any]]:
        config = {"configurable": {"thread_id": thread_id}}
        history_chain = []
        for state_snapshot in self.graph.get_state_history(config):
            history_chain.append({
                "checkpoint_id": state_snapshot.config["configurable"].get("checkpoint_id"),
                "values": state_snapshot.values,
                "next_nodes": state_snapshot.next,
            })
        return history_chain
