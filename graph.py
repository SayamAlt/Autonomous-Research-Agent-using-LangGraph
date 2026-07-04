import sqlite3
from langgraph.graph import StateGraph, END
from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.types import Send
from state import ResearchState
from nodes import query_analyzer, search_source, deduplicator, summarizer, exporter

def route_to_parallel_search(state: ResearchState) -> list[Send]:
    """ Route to selected sources for parallel execution. """
    return [
        Send("search_source", {**state, "current_source": source})
        for source in state["selected_sources"]
    ]
    
def build_graph(memory_db: str = "research_memory.db") -> any:
    builder = StateGraph(ResearchState)
    builder.add_node("query_analyzer", query_analyzer)
    builder.add_node("search_source", search_source)
    builder.add_node("deduplicator", deduplicator)
    builder.add_node("summarizer", summarizer)
    builder.add_node("exporter", exporter)
    
    builder.set_entry_point("query_analyzer")
    builder.add_conditional_edges("query_analyzer", route_to_parallel_search, ["search_source"])
    builder.add_edge("search_source", "deduplicator")
    builder.add_edge("deduplicator", "summarizer")
    builder.add_edge("summarizer", "exporter")
    builder.add_edge("exporter", END)
    
    connection = sqlite3.connect(memory_db, check_same_thread=False)
    memory = SqliteSaver(connection)
    return builder.compile(checkpointer=memory)

# Visualize the research workflow
if __name__ == "__main__":
    graph = build_graph()
    
    img_bytes = graph.get_graph().draw_mermaid_png()
    
    with open("research_workflow.png", "wb") as f:
        f.write(img_bytes)