# src/agent_runtime/graph/reducers.py
from typing import Any, List, Optional

def reduce_append(left: Optional[List[Any]], right: Optional[List[Any]]) -> List[Any]:
    """标准的只增不减（Append-only）合并规则。用于 trace_events、errors 和 messages。"""
    if left is None:
        left = []
    if right is None:
        right = []
    return left + list(right)

def reduce_unique_str_list(left: Optional[List[str]], right: Optional[List[str]]) -> List[str]:
    """针对字符串列表（如 active_job_ids）的去重追加合并规则。防止重复记录导致线索污染。"""
    if left is None:
        left = []
    if right is None:
        right = []
    # 保持原有顺序并进行去重
    seen = set(left)
    result = list(left)
    for item in right:
        if item not in seen:
            seen.add(item)
            result.append(item)
    return result

def reduce_artifact_refs(left: Optional[List[dict]], right: Optional[List[dict]]) -> List[dict]:
    """针对结构化字典（如 artifact_refs, completed_job_results）的去重追加规则。
    基于唯一的标识符（如 'artifact_id' 或 'job_id'）进行冲突判定。
    """
    if left is None:
        left = []
    if right is None:
        right = []
    
    result = {m.get("artifact_id", m.get("job_id", idx)): m for idx, m in enumerate(left)}
    for item in right:
        # 如果有唯一的业务 key，执行增量 upsert / 保持最新元数据
        key = item.get("artifact_id", item.get("job_id", f"gen_{len(result)}"))
        result[key] = item
        
    return list(result.values())