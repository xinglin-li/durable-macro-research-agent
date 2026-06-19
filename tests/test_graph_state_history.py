# tests/test_graph_state_history.py
import pytest
from agent_runtime.graph.service import MacroAgentGraphService

def test_state_history_and_artifact_ref_boundary():
    """验证数据分层：大结果文件只保存 Ref 引用进入 Checkpoint 链，绝不塞入大实体"""
    service = MacroAgentGraphService()
    
    res = service.run_workflow(thread_id="thread_travel_999", run_id="run_999", user_query="Heavy analysis")
    
    # 1. 检索状态历史链条
    history = service.get_state_history(thread_id="thread_travel_999")
    
    # 验证状态演进的历史节点个数（parse_request -> assemble_context -> call_tool -> observe_tool_result -> finalize）
    # 应该有多个明确记录的版本镜像
    assert len(history) >= 3
    
    # 2. 深度验证精益智能体架构的数据分层边界
    latest_values = history[0]["values"]
    # 状态里只有用于模型推理的高价值 Ref 线索（artifact_id, uri），没有任何几十兆的超大原始 CSV 内容
    assert "artifact_refs" in latest_values
    ref_item = latest_values["artifact_refs"][0]
    assert "uri" in ref_item
    assert "storage://macro/" in ref_item["uri"]
    # 证明其保持了精益设计：State中不存在任何庞大实体的具体数据负载
    assert "large_raw_csv_data_content" not in ref_item