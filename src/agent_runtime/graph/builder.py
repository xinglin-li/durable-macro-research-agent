# src/agent_runtime/graph/builder.py
from langgraph.graph import StateGraph, START, END
from agent_runtime.graph.state import MacroAgentState
from agent_runtime.graph.nodes import (
    parse_request_node,
    assemble_context_node,
    call_tool_node,
    observe_tool_result_node,
    finalize_node
)
from agent_runtime.graph.edges import decide_next_action

def create_macro_agent_graph():
    """使用最底层的 StateGraph API 组装宏观研究智能体状态机拓扑"""
    # 1. 传入带类型的状态定义初始化图底座
    workflow = StateGraph(MacroAgentState)
    
    # 2. 显式注册所有单一职责的原子计算节点
    workflow.add_node("parse_request", parse_request_node)
    workflow.add_node("assemble_context", assemble_context_node)
    workflow.add_node("call_tool", call_tool_node)
    workflow.add_node("observe_tool_result", observe_tool_result_node)
    workflow.add_node("finalize", finalize_node)
    
    # 3. 编织确定性的硬路由控制流（无条件边）
    workflow.add_edge(START, "parse_request")
    workflow.add_edge("parse_request", "assemble_context")
    
    # 4. 在控制流的分水岭节点上绑定“条件边（动态路由）”
    # 我们强行阻断模型直接路由，由代码级表决函数进行安全决断
    workflow.add_conditional_edges(
        "assemble_context",
        decide_next_action,
        {
            "call_tool": "call_tool",
            "observe_tool_result": "observe_tool_result",
            "finalize": "finalize",
            "max_steps_hit": END # 触碰硬防护线时直接断路退出
        }
    )
    
    # 让工具链节点执行完毕后，无条件交回控制权给分水岭，重新判定集合差异
    workflow.add_edge("call_tool", "assemble_context")
    workflow.add_edge("observe_tool_result", "assemble_context")
    
    # 终审交付节点执行完毕后，流向虚拟终点，锁定当前状态
    workflow.add_edge("finalize", END)
    
    # 5. 编译图，生成确定性的可执行运行时骨架
    return workflow.compile()