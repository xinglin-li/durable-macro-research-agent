# tests/test_graph_routing.py
import pytest
from agent_runtime.graph.builder import create_macro_agent_graph

def test_direct_answer_routing_path():
    """场景一：验证用户请求无需外部工具时，图能够直接路由至 finalize 并安全退出"""
    graph = create_macro_agent_graph()
    
    # 输入触发词 'direct' 强行诱导解析节点切入 direct_answer 意图
    initial_state = {"user_query": "Please give me a direct definition of CPI."}
    
    result = graph.invoke(initial_state)
    
    assert result["status"] == "completed"
    assert "direct definition of CPI" in result["final_answer"]
    # 验证没有发生多余的外部任务提交线索
    assert len(result.get("active_job_ids", [])) == 0
    # 验证审计流 trace_events 记录了精简的直达足迹
    events = [e["event"] for e in result["trace_events"]]
    assert "request_parsed" in events
    assert "context_assembled" in events
    assert "workflow_finalized" in events

def test_tool_loop_and_collection_difference_resolution():
    """场景二：验证宏观长任务循环调用、集合差异解耦以及最终完工正常交付的完整闭环"""
    graph = create_macro_agent_graph()
    initial_state = {"user_query": "Analyze macro unemployment statistics."}
    
    result = graph.invoke(initial_state)
    
    # 1. 验证图状态机通过集合差异判断，最终成功走向了完工终态
    assert result["status"] == "completed"
    assert "unemployment statistics" in result["final_answer"]
    
    # 2. 深度验证 Reducer 合并正确性：去重追加规则没有漏掉或覆盖历史线索
    assert len(result["active_job_ids"]) == 1
    assert len(result["completed_job_results"]) == 1
    assert len(result["artifact_refs"]) == 1
    
    # 3. 验证通过集合差异追踪进度：下发的 Job ID 和完工的 Job ID 完全对称
    assert result["active_job_ids"][0] == result["completed_job_results"][0]["job_id"]
    assert result["artifact_refs"][0]["artifact_id"] == f"artifact_{result['active_job_ids'][0]}"

def test_max_steps_hard_guardrail_melting():
    """场景三：故障注入/边界测试。验证当节点故意引发死循环或运行超限时，硬防护线能立刻断路熔断"""
    # 构造一个恶意的状态，人为注入 10 个历史 trace_events 模拟触碰上限
    malicious_state = {
        "user_query": "Loop forever please.",
        "trace_events": [{"event": "fake_loop", "step": i} for i in range(10)]
    }
    
    graph = create_macro_agent_graph()
    result = graph.invoke(malicious_state)
    
    # 验证状态机在 assemble_context 节点后触发了条件边熔断，没有流入 finalize 节点
    assert result.get("status") is None  # 说明被无条件拦截在 END，未被赋予 finalized 的完工状态
    assert result.get("final_answer") is None
    # 验证原来的 10 个历史审计足迹没有丢失，证明 Append-only Reducer 在断路时依旧守护了数据资产
    assert len(result["trace_events"]) == 12  # 加上新跑的 parse_request 和 assemble_context