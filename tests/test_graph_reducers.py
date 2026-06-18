# tests/test_graph_reducers.py
import pytest
from agent_runtime.graph.reducers import (
    reduce_append,
    reduce_unique_str_list,
    reduce_artifact_refs
)

def test_reduce_append_chaining():
    """验证可审计审计流 trace_events 是否只增不减且顺序正确"""
    left = [{"event": "start", "step": 0}]
    right = [{"event": "node_processed", "step": 1}]
    res = reduce_append(left, right)
    assert len(res) == 2
    assert res[0]["event"] == "start"
    assert res[1]["event"] == "node_processed"

def test_reduce_unique_str_list_dedup():
    """验证同时触发/提交多个 Job 时，异步长任务 ID 列表不会被重复插入"""
    left = ["job_001", "job_002"]
    right = ["job_002", "job_003"]
    res = reduce_unique_str_list(left, right)
    assert res == ["job_001", "job_002", "job_003"]

def test_reduce_artifact_refs_conflict_resolution():
    """验证重复重跑节点时，生成的报告/文件引用引用集合能够依据 ID 去重更新"""
    left = [{"artifact_id": "cpi_report", "path": "old/path.csv"}]
    right = [
        {"artifact_id": "cpi_report", "path": "new/actual_path.csv"},
        {"artifact_id": "unemployment_report", "path": "unemp.csv"}
    ]
    res = reduce_artifact_refs(left, right)
    assert len(res) == 2
    # 验证同名冲突时，新元数据成功覆盖/合并，而不是无脑 append
    cpi_ref = next(r for r in res if r["artifact_id"] == "cpi_report")
    assert cpi_ref["path"] == "new/actual_path.csv"