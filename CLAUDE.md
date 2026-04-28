# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project overview

Graduation thesis project: an LLM-based AI agent for weather forecast data retrieval and analysis, using the **ReAct (Reasoning + Acting)** paradigm. The agent converts natural-language weather queries into structured API calls, retrieves heterogeneous weather data, and generates analysis reports.

**Core research problems:**
- Q1: Mapping natural-language queries to structured retrieval parameters
- Q2: Unifying multi-source, multi-temporal weather data
- Q3: Preventing LLM numerical hallucination via code-generation-driven analysis and "semantic bridging" (deterministic numerical-to-text conversion before LLM ingestion)

## Environment

```bash
conda activate weather311    # Python 3.11
```

Key dependencies: `langchain`, `langchain-openai`, `langgraph`, `requests`. No package manager file (pip/conda/poetry) exists yet — install manually.

## Run the agent

```bash
python -m src.agent.react_agent
```

Must use `-m` module invocation because imports are absolute (`from src.xxx import ...`). The default query in `__main__` is `"接下来一周武汉有哪些日子适合骑车？"`.

## Configuration

`src/config/settings.py` is **gitignored** (contains API keys). It provides:
- `LLM_MODEL`, `LLM_API_KEY`, `LLM_BASE_URL` — LLM service (currently DeepSeek via OpenAI-compatible API)
- `QWEATHER_API_KEY`, `QWEATHER_API_HOST` — QWeather API credentials
- `SYSTEM_PROMPT` — the agent's system prompt (currently the only place prompts are defined; planned to split into `src/agent/prompts/`)

If you need to recreate it, see the template in README.md §十.

## Architecture

### Implemented (`src/`)

```
src/agent/react_agent.py     — Agent orchestration
src/tools/weather_api.py     — 9 @tool-decorated weather tools
src/config/settings.py       — Secrets & SYSTEM_PROMPT (gitignored)
```

**Agent flow** (`react_agent.py`):
1. `create_weather_agent()`: Creates a LangGraph agent via `create_agent()` with `ChatOpenAI` model, all 9 tools, `InMemorySaver` checkpointer, and the `SYSTEM_PROMPT`.
2. `run_agent()`: Streams agent execution with `stream_mode="updates"`, printing each step's tool calls, tool returns, or final response.

**9 tools** (`weather_api.py`):

| Tool | Source | Purpose |
|------|--------|---------|
| `get_current_time` | system clock | Resolve relative time references |
| `search_city` | QWeather GeoAPI | City name → LocationID + lat/lon |
| `get_current_weather` | QWeather | Real-time weather |
| `get_forcast_weather` | QWeather | Hourly forecast (24h/72h/168h) |
| `get_daily_forecast` | QWeather | Daily forecast (3d/7d/10d/15d/30d) |
| `get_weather_warning` | QWeather | Active weather alerts (takes lat/lon, not LocationID) |
| `get_weather_indices` | QWeather | Life indices (clothing, sports, UV, etc.; 1d/3d) |
| `get_historical_hourly` | Open-Meteo | Historical hourly data (free, no key needed) |
| `get_historical_daily` | Open-Meteo | Historical daily data |

Tools return trimmed data (only key fields) to reduce token consumption. Historical tools use Open-Meteo instead of Meteostat (no API key, global grid coverage).

### Not yet implemented (empty directories)

- `src/analysis/` — code-execution sandbox, semantic bridge, report generator (Chapter 4)
- `src/rag/` — RAG knowledge base with weather terminology, geo-mapping (Chapter 2.3)
- `src/agent/prompts/` — prompt template modularization (currently all in `settings.py`)
- `src/utils/` — logging, data helpers
- `tests/` — no tests exist yet
- `experiments/` — evaluation framework, ablation studies, results
- `data/` — knowledge base JSON, semantic mapping tables, test cases/baselines

## Key design decisions

- **Semantic bridging**: Before feeding raw weather data to the LLM, a deterministic script converts numerical values to natural-language descriptions (e.g., 12.3°C → "cool, wear a jacket"). This keeps the LLM organizing language, not interpreting raw numbers, reducing hallucination.
- **Code generation for analysis**: Statistical computations must go through generated Python code execution, never direct LLM output.
- **Historical data source**: Migrated from Meteostat to Open-Meteo (no API key, no local station matching).
- **Warning API**: Takes lat/lon, not LocationID — the SYSTEM_PROMPT guides the agent to extract coordinates from `search_city` results.
