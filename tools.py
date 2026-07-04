import os
import time
import requests
import arxiv
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from tavily import TavilyClient
from langchain_community.document_loaders import WebBaseLoader

os.environ.setdefault("USER_AGENT", "ResearchAgent/1.0 (educational; contact@example.com)")

_WIKI_UA = "ResearchAgent/1.0 (educational; contact@example.com)"
_WIKI_BASE = "https://en.wikipedia.org/w/api.php"

def _wiki_session() -> requests.Session:
    """Session with automatic retry + exponential backoff for 429/5xx."""
    session = requests.Session()
    session.headers.update({"User-Agent": _WIKI_UA})
    retry = Retry(
        total=4,
        backoff_factor=2,          # waits: 2s → 4s → 8s → 16s on each retry
        status_forcelist=[429, 500, 502, 503, 504],
        respect_retry_after_header=True,   # honours Wikipedia's Retry-After header
        raise_on_status=False,
    )
    session.mount("https://", HTTPAdapter(max_retries=retry))
    return session

def tavily_web_search(query: str, max_results: int = 5) -> list[dict]:
    client = TavilyClient(api_key=os.environ["TAVILY_API_KEY"])
    response = client.search(query=query, max_results=max_results, include_raw_content=True)
    return [
        {
            "source": "web_search",
            "url": r.get("url", ""),
            "title": r.get("title", ""),
            "content": (r.get("raw_content") or r.get("content") or "")[:4000],
        }
        for r in response.get("results", [])
    ]

def wikipedia_search(query: str, load_max_docs: int = 2) -> list[dict]:
    """Search Wikipedia via direct API calls with retry + backoff.

    load_max_docs reduced to 2 (was 3/5) so parallel sub-query calls
    don't saturate Wikipedia's rate limit (10 req/s per IP).
    """
    session = _wiki_session()

    # Step 1: get matching page titles
    try:
        resp = session.get(
            _WIKI_BASE,
            params={"action": "query", "list": "search", "srsearch": query,
                    "srlimit": load_max_docs + 2, "format": "json", "utf8": 1},
            timeout=15,
        )
        resp.raise_for_status()
        titles = [item["title"] for item in resp.json().get("query", {}).get("search", [])]
    except Exception as e:
        print(f"[wikipedia] search failed for '{query}': {e}")
        return []

    # Step 2: fetch full plain-text extract per title
    # 1 s gap between page fetches keeps us under Wikipedia's rate limit
    results = []
    for title in titles[:load_max_docs]:
        try:
            time.sleep(1)
            resp = session.get(
                _WIKI_BASE,
                params={"action": "query", "titles": title,
                        "prop": "extracts|info", "explaintext": True,
                        "inprop": "url", "format": "json", "utf8": 1},
                timeout=15,
            )
            resp.raise_for_status()
            pages = resp.json().get("query", {}).get("pages", {})
            for pid, page in pages.items():
                if pid == "-1" or not page.get("extract"):
                    continue
                results.append({
                    "source": "wikipedia",
                    "url": page.get("fullurl",
                                    f"https://en.wikipedia.org/wiki/{title.replace(' ', '_')}"),
                    "title": page.get("title", title),
                    "content": page["extract"][:4000],
                })
        except Exception as e:
            print(f"[wikipedia] page fetch failed for '{title}': {e}")
            continue

    return results

def arxiv_search(query: str, load_max_docs: int = 3) -> list[dict]:
    # Using arxiv SDK directly — ArxivLoader metadata keys differ across
    # langchain-community versions and entry_id is not always populated.
    results = []
    try:
        client = arxiv.Client()
        search = arxiv.Search(
            query=query,
            max_results=load_max_docs,
            sort_by=arxiv.SortCriterion.Relevance,
        )
        for paper in client.results(search):
            results.append({
                "source": "arxiv",
                "url": paper.entry_id,
                "title": paper.title,
                "content": (paper.summary or "")[:4000],
            })
    except Exception as e:
        print(f"[arxiv] search failed: {e}")

    return results

def web_loader_fetch(urls: list[str]) -> list[dict]:
    loader = WebBaseLoader(urls)
    documents = loader.load()
    return [
        {
            "source": "web_loader",
            "url": doc.metadata.get("source", ""),
            "title": doc.metadata.get("title", ""),
            "content": doc.page_content[:4000],
        }
        for doc in documents
    ]


SOURCE_HANDLERS: dict[str, callable] = {
    "web_search": tavily_web_search,
    "wikipedia": wikipedia_search,
    "arxiv": arxiv_search,
}