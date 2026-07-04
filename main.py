import os
import sys
os.environ.setdefault("USER_AGENT", "ResearchAgent/1.0 (educational; contact@example.com)")

from uuid import uuid4
from dotenv import load_dotenv
from graph import build_graph

load_dotenv()

graph = build_graph()

def run_research(query:str, export_format: str = "both", session_id: str | None = None) -> dict:
    """ Runs a full end-to-end research pipeline. """
    session_id = session_id or str(uuid4())
    config = {"configurable": {"thread_id": session_id}}
    
    initial_state = {
        "user_query": query,
        "session_id": session_id,
        "selected_sources": [],
        "search_queries": [],
        "current_source": None,
        "raw_results": [],
        "deduplicated_content": [],
        "summary": {},
        "export_format": export_format,
        "export_path": None,
        "error": None
    }
    
    result = graph.invoke(initial_state, config=config)
    
    print(f"Query: {query}")
    print(f"Selected sources: {result['selected_sources']}")
    print(f"Raw results: {len(result['raw_results'])}")
    print(f"After deduplication, result: {len(result['deduplicated_content'])}")
    print(f"Key points: {len(result['summary'].get('key_points', []))}")
    print(f"Exported to: {result['export_path']}")
    print(f"{'-' * 50}")
    
    return result

def resume_session(session_id: str) -> dict | None:
    """ Fetch last saved state for a session (memory retrieval). """
    config = {"configurable": {"thread_id": session_id}}
    state = graph.get_state(config)
    return state.values if state else None

if __name__ == "__main__":
    query = " ".join(sys.argv[1:]) if len(sys.argv) > 1 else "latest advances in quantum computing 2026"
    result = run_research(query, export_format="both")
    
    summary = result.get("summary", {})
    
    print("Executive summary:")
    print(summary.get("executive_summary", ""))
    print("\n Key Points:")
    
    for point in summary.get("key_points", []):
        print(f"• {point}")