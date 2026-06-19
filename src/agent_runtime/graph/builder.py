# src/agent_runtime/graph/builder.py
from typing import Optional, Any
from langgraph.graph import StateGraph, START, END
from agent_runtime.graph.state import MacroAgentState
from agent_runtime.graph.nodes import (
    parse_request_node, assemble_context_node, human_approval_node,
    call_tool_node, observe_tool_result_node, finalize_node
)
from agent_runtime.graph.edges import decide_next_action

def create_macro_agent_graph(checkpointer: Optional[Any] = None):
    workflow = StateGraph(MacroAgentState)
    
    # 注册包含新加入的 human_approval 节点
    workflow.add_node("parse_request", parse_request_node)
    workflow.add_node("assemble_context", assemble_context_node)
    workflow.add_node("human_approval", human_approval_node)
    workflow.add_node("call_tool", call_tool_node)
    workflow.add_node("observe_tool_result", observe_tool_result_node)
    workflow.add_node("finalize", finalize_node)
    
    workflow.add_edge(START, "parse_request")
    workflow.add_edge("parse_request", "assemble_context")
    
    # 在控制流核心判定中心挂载条件路由边
    workflow.add_conditional_edges(
        "assemble_context",
        decide_next_action,
        {
            "human_approval": "human_approval",
            "call_tool": "call_tool",
            "observe_tool_result": "observe_tool_result",
            "finalize": "finalize",
            "max_steps_hit": END
        }
    )
    
    # 编织人工审批完成、拒绝、修改后的控制流回路
    # 节点执行完毕后统一回到大分水岭重新判定状态
    workflow.add_edge("human_approval", "assemble_context")
    workflow.add_edge("call_tool", "assemble_context")
    workflow.add_edge("observe_tool_result", "assemble_context")
    workflow.add_edge("finalize", END)
    
    return workflow.compile(checkpointer=checkpointer)