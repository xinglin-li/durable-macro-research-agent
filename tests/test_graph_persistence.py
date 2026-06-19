# tests/test_graph_persistence.py
import pytest
from agent_runtime.graph.service import MacroAgentGraphService

def test_durable_crash_recovery_lifecycle():
    """验证崩溃恢复：同一 Thread 在停止、重启服务后，Checkpoint 能够接续历史状态"""
    # 模拟服务首次启动，使用一个共享物理内存空间（或临时物理文件模拟重启）
    # 为了在单体测试中完美模拟“应用彻底关闭”，我们采用内存服务实例被销毁、但共用同一个连接字符串的逻辑
    db_url = "file:memdb_day02?mode=memory&cache=shared"
    
    service_v1 = MacroAgentGraphService(db_path=db_url)
    
    # 触发一个普通长任务请求，图会在工具循环中跑完，但我们可以通过 thread_id 锁定检查点
    res_v1 = service_v1.run_workflow(thread_id="thread_macro_001", run_id="run_001", user_query="Analyze CPI gaps")
    assert res_v1["status"] == "completed"
    
    # --- 模拟系统突然崩溃重启 / 销毁旧实例 ---
    del service_v1
    
    # 服务重新初始化，重新加载相同的数据库
    service_v2 = MacroAgentGraphService(db_path=db_url)
    
    # 检索历史：即使新实例中完全没有运行过 invoke，它也必须从数据库中完整还原出 thread_macro_001 的历史记忆
    history = service_v2.get_state_history(thread_id="thread_macro_001")
    assert len(history) > 0
    # 最终的交付成果完好无损
    assert "Analyze CPI gaps" in history[0]["values"]["final_answer"]

def test_multi_tenant_thread_strict_isolation():
    """验证隔离边界：两个不同的 Thread ID 在同一个持久化底座中必须呈现完美的空间状态隔离"""
    service = MacroAgentGraphService()
    
    # Thread A 跑一个时序分析任务
    res_a = service.run_workflow(thread_id="tenant_user_xinglin", run_id="run_a", user_query="Xinglin task")
    # Thread B 跑一个完全无关的直接回答任务
    res_b = service.run_workflow(thread_id="tenant_user_hacker", run_id="run_b", user_query="Hacker task direct")
    
    # 验证 Thread A 的状态字典没有沾染 Thread B 的任何意图或解析字段
    assert res_a["parsed_request"]["raw_query"] == "Xinglin task"
    assert "Hacker" not in res_a["final_answer"]
    
    assert res_b["parsed_request"]["raw_query"] == "Hacker task direct"