# Autonomous Research Agent

**Assessment Option 1** — AI Automation Engineer Assessment (Xiarch)

An autonomous AI agent that accepts a research query, searches multiple external sources in parallel, deduplicates and filters results, and generates a structured report exported as Markdown and PDF — with full session memory across runs.

---

## Architecture

```
User Query
    │
    ▼
┌─────────────────┐
│  query_analyzer │  LLM selects sources + generates focused sub-queries
└────────┬────────┘
         │  LangGraph Send API (parallel fan-out)
    ┌────┴────────────────────────────┐
    ▼            ▼                   ▼
web_search    wikipedia           arxiv
(Tavily)    (Wikipedia API)   (arXiv SDK)
    └────────────┬────────────────────┘
                 │  raw_results reducer merges all branches
                 ▼
        ┌────────────────┐
        │  deduplicator  │  MD5 hash dedup → LLM relevance filter
        └───────┬────────┘
                ▼
        ┌───────────────┐
        │   summarizer  │  Synthesizes structured JSON report
        └───────┬───────┘
                ▼
        ┌───────────────┐
        │   exporter    │  Writes .md + .pdf to outputs/
        └───────────────┘
                │
        SQLite checkpointer (session memory)
```

**Stack:** LangGraph · LangChain · OpenAI GPT-4o-mini · Tavily Search · Wikipedia REST API · arXiv SDK · fpdf2

---

## Requirements Fulfilled

| Requirement | How |
|---|---|
| Accept user query | CLI argument or `run_research()` function |
| Search external sources | Tavily (web), Wikipedia REST API, arXiv SDK |
| Extract relevant information | `search_source` node with per-source handlers |
| Remove duplicates | MD5 hash dedup + LLM relevance filter (keeps top 15) |
| Key points | `key_points[]` in summary |
| Important findings | `important_findings[]` in summary |
| References/Sources | `references[]` with title, URL, source |
| Actionable insights | `actionable_insights[]` in summary |
| **Bonus** — LLM selects sources | `query_analyzer` with strict keyword rules + few-shot examples |
| **Bonus** — Parallel search | LangGraph `Send` API fans out one branch per source |
| **Bonus** — PDF + Markdown export | `exporter` node writes both to `outputs/` |
| **Bonus** — Memory | SQLite `SqliteSaver` checkpointer; resume any session by ID |

---

## Project Structure

```
.
├── main.py          # Entry point — run_research() + CLI
├── graph.py         # LangGraph StateGraph assembly
├── nodes.py         # All node functions (query_analyzer, search_source, deduplicator, summarizer, exporter)
├── state.py         # ResearchState TypedDict definition
├── tools.py         # External source handlers (Tavily, Wikipedia, arXiv)
├── requirements.txt
├── .env             # API keys (not committed)
├── outputs/         # All generated MD/PDF reports land here
└── research_memory.db  # SQLite session memory (auto-created)
```

---

## Installation

### 1. Clone / unzip the project

```bash
cd "Xiarch Agentic AI Assessment"
```

### 2. Create and activate a virtual environment

```bash
python3 -m venv venv
source venv/bin/activate        # macOS / Linux
# venv\Scripts\activate         # Windows
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

### 4. Configure API keys

Create a `.env` file in the project root:

```env
OPENAI_API_KEY=your_openai_api_key_here
TAVILY_API_KEY=your_tavily_api_key_here
```

- **OpenAI API key** — [platform.openai.com](https://platform.openai.com)
- **Tavily API key** — [app.tavily.com](https://app.tavily.com) (free tier available)

---

## Usage

### Run a research query

```bash
python3 main.py "your research topic here"
```

**Examples:**

```bash
# Academic + web search (selects web_search + arxiv + wikipedia)
python3 main.py "reinforcement learning from human feedback latest research"

# Technical paper query (selects web_search + arxiv)
python3 main.py "LoRA low-rank adaptation fine-tuning LLM paper"

# Historical/conceptual query (selects web_search + wikipedia)
python3 main.py "history of deep learning neural networks who invented"

# Current events (selects web_search only)
python3 main.py "latest AI model releases 2025"
```

### Output

Each run produces two files in `outputs/`:

```
outputs/
├── research_<query_slug>_<timestamp>.md    # Markdown report
└── research_<query_slug>_<timestamp>.pdf   # PDF report
```

Both contain:
- Executive Summary
- Key Points
- Important Findings
- Actionable Insights
- References (with URLs and source labels)

### Resume a previous session

```python
from main import resume_session

state = resume_session("your-session-id-here")
print(state["summary"])
```

### Visualize the workflow graph

```bash
python3 graph.py   # saves research_workflow.png
```

---

## How It Works

### 1. Query Analyzer
The LLM analyzes the user query and autonomously selects the most appropriate sources (`web_search`, `wikipedia`, `arxiv`) based on keyword rules and few-shot examples. It also generates 2–3 refined sub-queries to improve coverage.

### 2. Parallel Search (LangGraph Send API)
LangGraph fans out one `search_source` execution per selected source simultaneously. All results are merged automatically via the `Annotated[list, add]` state reducer — no manual join needed.

### 3. Deduplication
- **Pass 1:** MD5 hash of the first 500 chars of each result — exact duplicates removed instantly.
- **Pass 2:** LLM reviews remaining snippets and returns indices of relevant ones to keep (max 15 sent to LLM).

### 4. Summarizer
GPT-4o-mini synthesizes the filtered content into a structured JSON report with all required fields.

### 5. Exporter
Writes Markdown and PDF to `outputs/`. PDF uses fpdf2 with safe latin-1 character encoding and explicit margin resets to prevent layout errors.

### 6. Memory
Every run is persisted to `research_memory.db` (SQLite) via LangGraph's `SqliteSaver`. Pass the same `session_id` to `run_research()` to continue a previous research thread.

---

## Configuration

| Variable | Description |
|---|---|
| `OPENAI_API_KEY` | OpenAI API key (used for all LLM calls) |
| `TAVILY_API_KEY` | Tavily search API key (web search) |

The LLM model is set in `nodes.py` (`gpt-4o-mini`). To switch models, change:
```python
llm = ChatOpenAI(model="gpt-4o", temperature=0)
```

---

## Dependencies

```
langchain
langchain-community
langchain-openai
langgraph
langgraph-checkpoint-sqlite
tavily-python
arxiv
fpdf2
requests
beautifulsoup4
python-dotenv
```
