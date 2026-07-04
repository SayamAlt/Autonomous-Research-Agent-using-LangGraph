# Autonomous Research Agent

**Assessment Option 1** | AI Automation Engineer Assessment (Xiarch)

An autonomous AI agent that takes a research query, searches multiple sources at the same time, removes duplicate results, and writes a clean structured report as Markdown and PDF. It also saves every session to memory for future use.

---

## Architecture

```
User Query
    |
    v
[query_analyzer]   LLM picks sources + builds focused sub-queries
    |
    |  LangGraph Send API (runs all sources at the same time)
    |
    +----------+----------+
    v          v          v
web_search  wikipedia  arxiv
(Tavily)   (Wiki API) (arXiv SDK)
    |          |          |
    +----------+----------+
               |
               v  all results merged by state reducer
        [deduplicator]   MD5 hash dedup + LLM filter
               |
               v
          [summarizer]   builds structured JSON report
               |
               v
           [exporter]   saves .md and .pdf to outputs/
               |
        SQLite memory (session stored per run)
```

**Stack:** LangGraph, LangChain, OpenAI GPT-4o-mini, Tavily Search, Wikipedia REST API, arXiv SDK, fpdf2

---

## What This Agent Does

| Requirement | How it works |
|---|---|
| Accept user query | CLI argument or `run_research()` function call |
| Search external sources | Tavily (web), Wikipedia REST API, arXiv SDK |
| Extract relevant information | `search_source` node runs per source with its own handler |
| Remove duplicates | MD5 hash check + LLM filter keeps only the best 15 results |
| Key points | `key_points[]` field in the report |
| Important findings | `important_findings[]` field in the report |
| References and sources | `references[]` with title, URL, and source name |
| Actionable insights | `actionable_insights[]` field in the report |
| **Bonus:** LLM picks sources | `query_analyzer` uses strict rules and examples to choose |
| **Bonus:** Parallel search | LangGraph `Send` API runs each source as its own branch |
| **Bonus:** PDF and Markdown export | `exporter` node writes both file types to `outputs/` |
| **Bonus:** Session memory | SQLite `SqliteSaver` stores every run; resume by session ID |

---

## Project Structure

```
.
├── main.py            Entry point: run_research() function and CLI
├── graph.py           Builds the LangGraph workflow
├── nodes.py           All node functions (query_analyzer, search_source, deduplicator, summarizer, exporter)
├── state.py           ResearchState type definition
├── tools.py           Source handlers: Tavily, Wikipedia, arXiv
├── requirements.txt   Python dependencies
├── .env               API keys (not committed to git)
├── outputs/           All generated MD and PDF reports saved here
└── research_memory.db SQLite session memory (auto-created on first run)
```

---

## Setup and Installation

### Step 1: Create and activate a virtual environment

```bash
python3 -m venv venv
source venv/bin/activate        # macOS and Linux
# venv\Scripts\activate         # Windows
```

### Step 2: Install all dependencies

```bash
pip install -r requirements.txt
```

### Step 3: Add API keys

Create a `.env` file in the project root with these two values:

```env
OPENAI_API_KEY=your_openai_api_key_here
TAVILY_API_KEY=your_tavily_api_key_here
```

Where to get them:
- OpenAI key: https://platform.openai.com
- Tavily key: https://app.tavily.com (free tier available)

---

## How to Run

### Basic usage

```bash
python3 main.py "your research topic here"
```

### Example queries

```bash
# Picks web_search + arxiv + wikipedia
python3 main.py "reinforcement learning from human feedback latest research"

# Picks web_search + arxiv
python3 main.py "LoRA low-rank adaptation fine-tuning LLM paper"

# Picks web_search + wikipedia
python3 main.py "history of deep learning neural networks who invented"

# Picks web_search only
python3 main.py "latest AI model releases 2025"
```

### What gets created

Every run saves two files inside `outputs/`:

```
outputs/
├── research_<topic>_<timestamp>.md
└── research_<topic>_<timestamp>.pdf
```

Both files contain:
- Executive Summary
- Key Points
- Important Findings
- Actionable Insights
- References with URLs

### Resume a past session

```python
from main import resume_session

state = resume_session("your-session-id-here")
print(state["summary"])
```

### View the workflow graph image

```bash
python3 graph.py    # saves research_workflow.png
```

---

## How Each Part Works

### query_analyzer
The LLM reads the query and picks the right sources to search. It also creates 2 to 3 better sub-queries to get wider coverage. The LLM decides which sources to use based on the topic, with no hardcoded logic.

### search_source (parallel)
LangGraph runs one copy of this node per source at the same time using the `Send` API. Results from all branches flow into a shared list via a state reducer.

### deduplicator
Two passes:
1. MD5 hash of the first 500 characters of each result removes exact copies fast.
2. LLM reads the remaining snippets and picks only the useful ones. At most 15 items are sent to the LLM.

### summarizer
GPT-4o-mini reads all kept content and writes a structured JSON report with every required field.

### exporter
Saves the report as both Markdown and PDF. PDF uses explicit margin resets and latin-1 character filtering to avoid layout errors.

### memory
LangGraph's `SqliteSaver` stores the full run state in `research_memory.db`. Use the same session ID to pick up where you left off.

---

## Configuration

| Variable | What it does |
|---|---|
| `OPENAI_API_KEY` | Used for all LLM calls |
| `TAVILY_API_KEY` | Used for web search via Tavily |

To change the LLM model, edit one line in `nodes.py`:

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