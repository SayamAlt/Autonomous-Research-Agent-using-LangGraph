from typing import TypedDict, Annotated, Optional, Literal
from operator import add

class SearchResult(TypedDict):
    source: str
    url: str
    title: str
    content: str
    
class ResearchState(TypedDict):
    user_query: str
    session_id: str
    selected_sources: list[str]
    search_queries: list[str]
    current_source: Optional[str]
    raw_results: Annotated[list[SearchResult], add]  # Reducer to merge raw search results from parallel branches
    deduplicated_content: list[SearchResult]
    summary: dict
    export_format: Literal["pdf", "markdown", "both"]
    export_path: Optional[str]
    error: Optional[str]