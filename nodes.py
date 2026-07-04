import re, json, hashlib, os
from datetime import datetime
from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage
from state import ResearchState
from tools import SOURCE_HANDLERS
from dotenv import load_dotenv
from fpdf import FPDF
from fpdf.enums import XPos, YPos

load_dotenv()

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

llm = ChatOpenAI(model="gpt-4o-mini", temperature=0)

# Query Analyzer
def query_analyzer(state: ResearchState) -> dict:
    """ LLM picks the best sources and generates focused subqueries. """
    response = llm.invoke([
        SystemMessage(content="""You are a research planning expert. Return ONLY valid JSON, no markdown.

MANDATORY SOURCE SELECTION RULES:
1. ALWAYS include "web_search".
2. MUST add "arxiv" if query involves ANY of:
   - machine learning, deep learning, AI, NLP, LLM, neural network, transformer
   - algorithm, model, training, fine-tuning, optimization, reinforcement learning
   - RLHF, LoRA, qLoRA, GPT, BERT, diffusion, GAN, attention, embedding
   - research, paper, study, arxiv, scientific, technical, mathematics, physics
3. MUST add "wikipedia" if query involves ANY of:
   - history, origin, "what is", definition, overview, concept, who invented
   - biography, timeline, background, introduction, founded, discovered
   - any well-known person, place, event, technology, or concept

For academic/technical queries ALWAYS include BOTH "arxiv" AND "wikipedia".

FEW-SHOT EXAMPLES:
Query: "reinforcement learning from human feedback latest research"
{"selected_sources": ["web_search", "arxiv", "wikipedia"], "search_queries": ["RLHF reinforcement learning from human feedback", "RLHF papers 2024", "reinforcement learning human feedback overview"]}

Query: "history of neural networks perceptron"
{"selected_sources": ["web_search", "wikipedia"], "search_queries": ["history of neural networks", "perceptron invention origin"]}

Query: "LoRA fine-tuning LLM paper"
{"selected_sources": ["web_search", "arxiv"], "search_queries": ["LoRA low-rank adaptation paper", "LoRA fine-tuning large language models"]}

Query: "latest iPhone release"
{"selected_sources": ["web_search"], "search_queries": ["latest iPhone release 2025"]}

Now return JSON for the given query. Return 2-3 focused sub-queries."""),
        HumanMessage(content=f"Query: {state['user_query']}")
    ])
    
    try:
        parsed_content = json.loads(response.content)
    except json.JSONDecodeError:
        parsed_content = {"selected_sources": ["web_search"], "search_queries": [state["user_query"]]}
        
    return {
        "selected_sources": parsed_content.get("selected_sources", ["web_search"]),
        "search_queries": parsed_content.get("search_queries", [state["user_query"]]),
        "raw_results": []
    }
    
# Fetch raw results from relevant sources
def search_source(state: ResearchState) -> dict:
    """ Runs once per source in parallel. Collects raw results. """
    source = state.get("current_source")
    handler = SOURCE_HANDLERS.get(source)
    
    if not handler:
        return {"raw_results": []}
    
    results: list[dict] = []
    
    for query in state.get("search_queries", [state["user_query"]]):
        try:
            results.extend(handler(query))
        except Exception as exc:
            print(f"{source} failed for '{query}': {exc}")
            
    return {"raw_results": results}

# Deduplicator
def deduplicator(state: ResearchState) -> dict:
    """ Hash deduplication the LLM relevance filter. """
    raw_results = state["raw_results"]
    
    # Content-hash deduplication
    seen: set[str] = set()
    unique: list[dict] = []
    
    for res in raw_results:
        hash = hashlib.md5(res["content"][:500].encode()).hexdigest()
        
        if hash not in seen and res["content"].strip():
            seen.add(hash)
            unique.append(res)
            
    # Cap before LLM call
    unique = unique[:15]
    
    # LLM relevance filter
    snippet_block = "\n\n".join([
        f"[{idx}] ({res['source']}) {res['title']}\n{res['content'][:300]}..."
        for idx, res in enumerate(unique)
    ])
    
    try:
        response = llm.invoke([
            SystemMessage(content="""
                You are a relevance filter.
                Given a query and numbered content snippets, return ONLY a JSON array of indices to KEEP.
                Remove off-topic, promotional, duplicate, or low-quality items.                
            """),
            HumanMessage(content=f"Query: {state['user_query']}\n\n{snippet_block}")
        ])
        keep = json.loads(response.content)
        filtered = [unique[i] for i in keep if isinstance(i, int) and i < len(unique)]
    except Exception:
        filtered = unique
        
    return {"deduplicated_content": filtered}

# Summarizer
def summarizer(state: ResearchState) -> dict:
    """ Synthesize deduplicated content into a structured JSON summary. """
    content_block = "\n\n---\n\n".join([
        f"[{r['source']}] {r['title']}\nURL: {r['url']}\n{r['content']}"                                                                                 
        for r in state["deduplicated_content"]
    ])  
    
    response = llm.invoke([
        SystemMessage(content="""
            You are an expert research analyst.
            Synthesize the provided sources into a structured report.
            Return ONLY valid JSON matching this schema exactly:
            {
                "executive_summary": "2-3 sentence overview",
                "key_points": ["...", "..."],
                "important_findings": ["...", "..."],
                "actionable_insights": ["...", "..."],
                "references": [{"title": "...", "url": "...", "source": "..."}]
            }             
        """),
        HumanMessage(content=f"Research Query: {state['user_query']}\n\nSources:\n{content_block}")
    ])
    
    try:
        summary = json.loads(response.content)
    except json.JSONDecodeError:
        match = re.search(r"```(?:json)?\n(.*?)\n```", response.content, re.DOTALL)
        summary = json.loads(match.group(1)) if match else {"raw": response.content}
    
    summary["query"] = state["user_query"]
    summary["timestamp"] = datetime.now().isoformat()
    summary["sources_used"] = state["selected_sources"]
    
    return {"summary": summary}

def _to_markdown(summary: dict) -> str:
    lines = [
          f"# Research Report: {summary.get('query', '')}",
          f"\n*Generated: {summary.get('timestamp', '')} | Sources: {', '.join(summary.get('sources_used', []))}*\n",
          "## Executive Summary",
          summary.get("executive_summary", ""),
          "\n## Key Points",
          *[f"- {p}" for p in summary.get("key_points", [])],
          "\n## Important Findings",
          *[f"- {f}" for f in summary.get("important_findings", [])],
          "\n## Actionable Insights",
          *[f"- {i}" for i in summary.get("actionable_insights", [])],
          "\n## References",
          *[
              f"- [{r.get('title') or r.get('url')}]({r.get('url')}) _{r.get('source')}_"
              for r in summary.get("references", [])
          ]
    ]
    
    return "\n".join(lines)

def _safe_text(text: str, max_len: int = 500) -> str:
    """Strip non-latin1 characters fpdf2/Helvetica cannot encode, cap length."""
    sanitized = "".join(c if ord(c) < 256 else "?" for c in str(text or ""))
    return sanitized[:max_len]


def _write_row(pdf: FPDF, h: float, text: str) -> None:
    """Always reset X to left margin before multi_cell so width=epw is valid."""
    pdf.set_x(pdf.l_margin)
    pdf.multi_cell(pdf.epw, h, _safe_text(text, 800))


def _to_pdf(summary: dict, path: str) -> None:
    pdf = FPDF()
    pdf.set_margins(15, 15, 15)
    pdf.add_page()
    pdf.set_auto_page_break(auto=True, margin=15)

    pdf.set_font("Helvetica", "B", 16)
    pdf.cell(pdf.epw, 10, "Research Report", new_x=XPos.LMARGIN, new_y=YPos.NEXT)

    pdf.set_font("Helvetica", "", 11)
    _write_row(pdf, 8, f"Query: {summary.get('query', '')}")
    _write_row(pdf, 8, f"Generated: {summary.get('timestamp', '')}")
    pdf.ln(4)

    sections = [
        ("Executive Summary", [summary.get("executive_summary", "")]),
        ("Key Points", summary.get("key_points", [])),
        ("Important Findings", summary.get("important_findings", [])),
        ("Actionable Insights", summary.get("actionable_insights", [])),
    ]

    for heading, items in sections:
        pdf.set_font("Helvetica", "B", 13)
        pdf.set_x(pdf.l_margin)
        pdf.cell(pdf.epw, 10, heading, new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        pdf.set_font("Helvetica", "", 10)
        for item in items:
            if item and str(item).strip():
                _write_row(pdf, 7, f"- {item}")
        pdf.ln(3)

    pdf.set_font("Helvetica", "B", 13)
    pdf.set_x(pdf.l_margin)
    pdf.cell(pdf.epw, 10, "References", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.set_font("Helvetica", "", 9)
    for ref in summary.get("references", []):
        title = ref.get("title", "") or ref.get("url", "")
        url = ref.get("url", "")
        _write_row(pdf, 6, f"- {title}  {url}")

    pdf.output(path)
        
# Resolve outputs/ relative to this file so it works regardless of cwd
_OUTPUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "outputs")


# Exporter
def exporter(state: ResearchState) -> dict:
    """ Write summary to Markdown and/or PDF inside the outputs/ directory. """
    os.makedirs(_OUTPUT_DIR, exist_ok=True)

    summary = state["summary"]
    fmt = state.get("export_format", "markdown")
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    safe = re.sub(r"[^a-zA-Z0-9]+", "_", state["user_query"])[:40]
    base = os.path.join(_OUTPUT_DIR, f"research_{safe}_{timestamp}")

    paths: list[str] = []

    if fmt in ("markdown", "both"):
        path = f"{base}.md"
        with open(path, "w") as f:
            f.write(_to_markdown(summary))
        paths.append(path)

    if fmt in ("pdf", "both"):
        path = f"{base}.pdf"
        _to_pdf(summary, path)
        paths.append(path)

    return {"export_path": ", ".join(paths)}