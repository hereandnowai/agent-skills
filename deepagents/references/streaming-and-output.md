# Streaming and structured output

The agent returned by `create_deep_agent` is a compiled LangGraph graph, so all of LangGraph's streaming machinery applies. The `response_format` parameter wires up structured-output extraction without you needing to write a separate parsing pass.

## Streaming modes

`agent.stream(...)` and `agent.astream(...)` accept `stream_mode=` with these values:

| Mode | What you get | Use for |
|---|---|---|
| `"values"` | The full state after every node runs. Each chunk is `{"messages": [...], "files": {...}, ...}`. | UI that re-renders the whole conversation each step. |
| `"updates"` | Just the diff produced by each node. Each chunk is `{"<node_name>": {"messages": [...]}}`. | Logs, dashboards, fine-grained progress. |
| `"messages"` | Token-by-token model output (LLM streaming). | Live typing UX. |
| `"custom"` | Whatever you push via `get_stream_writer()` from inside a tool. | Custom progress events. |
| `"events"` (with `version="v2"`) | Typed event stream covering tool starts/ends, model calls, etc. | Debug tracing, advanced UIs. |

You can also pass a list — `stream_mode=["updates", "messages"]` — and each chunk arrives tagged with which mode produced it.

## Capturing sub-agent events

Sub-agents are LangGraph subgraphs. Without `subgraphs=True` you'll only see events from the supervisor and the wrapped sub-agent results will show up as opaque tool messages. To see what's happening inside sub-agents:

```python
for chunk in agent.stream(
    {"messages": [{"role": "user", "content": "Plan a 5-day Tokyo trip."}]},
    stream_mode="updates",
    subgraphs=True,         # essential
    version="v2",           # typed event names
):
    ns = chunk.get("ns") or ()
    is_subagent = any(s.startswith("tools:") for s in ns)
    label = f"[subagent {ns[-1]}]" if is_subagent else "[main]"
    print(label, chunk.get("data") or chunk)
```

`chunk["ns"]` is a tuple of namespace segments. An empty tuple means the supervisor; a non-empty tuple includes a `tools:<tool_call_id>` segment when the event came from a sub-agent. In LangSmith traces, sub-agent runs nest under the parent and are labelled by `lc_agent_name`.

## Custom progress events from a tool

For long-running tools, push intermediate progress to the stream:

```python
from langchain.tools import tool
from langgraph.config import get_stream_writer

@tool
def heavy_analysis(query: str) -> str:
    """Run a multi-step analysis."""
    writer = get_stream_writer()
    writer({"phase": "loading", "pct": 10})
    # ... step 1
    writer({"phase": "analyzing", "pct": 50})
    # ... step 2
    writer({"phase": "writing", "pct": 90})
    return "done"

# When invoking, include "custom" in the stream modes:
for chunk in agent.stream({"messages": [...]}, stream_mode=["updates", "custom"]):
    print(chunk)
```

## Async streaming

```python
async for chunk in agent.astream(
    {"messages": [{"role": "user", "content": "..."}]},
    stream_mode="values",
    subgraphs=True,
    version="v2",
):
    if "messages" in chunk:
        chunk["messages"][-1].pretty_print()
```

Use `astream` whenever any tool is async — including all MCP tools. With sync `stream` and async tools, the run can stall on event-loop contention.

## Frontend integration

LangGraph ships a React `useStream` hook (see `frontend/overview` in the LangChain docs) that consumes the same SSE stream the LangSmith Deployment exposes. For your own backend, the typical pattern is:

```python
from fastapi.responses import StreamingResponse
import json

@app.post("/chat")
async def chat(req: ChatRequest):
    async def event_stream():
        async for chunk in agent.astream(
            {"messages": [{"role": "user", "content": req.message}]},
            stream_mode=["updates", "messages"],
            subgraphs=True,
            version="v2",
            config={"configurable": {"thread_id": req.thread_id}},
        ):
            yield f"data: {json.dumps({'mode': chunk[0], 'data': str(chunk[1])})}\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream")
```

## Structured output via `response_format`

Pass any `create_agent`-compatible schema to require a typed final answer. The agent runs as normal, and the final answer is extracted into `result["structured_response"]`.

### Pydantic schema (most common)

```python
from pydantic import BaseModel, Field
from deepagents import create_deep_agent

class WeatherReport(BaseModel):
    """Structured weather report with current conditions and forecast."""
    location: str = Field(description="The location for this report")
    temperature_c: float = Field(description="Current temperature in Celsius")
    condition: str = Field(description="Current weather condition")
    humidity_pct: int = Field(description="Humidity percentage")
    wind_kph: float = Field(description="Wind speed in km/h")
    forecast_24h: str = Field(description="Brief 24-hour forecast")

agent = create_deep_agent(
    model="anthropic:claude-sonnet-4-6",
    response_format=WeatherReport,
    tools=[get_weather_api],
)

result = agent.invoke({"messages": [{"role": "user", "content": "Weather in Chennai?"}]})
report = result["structured_response"]
assert isinstance(report, WeatherReport)
print(report.temperature_c, report.forecast_24h)
```

The model gets the schema as part of its system message; descriptions on `Field(...)` directly improve extraction quality, so write them.

### Strategy classes (advanced)

For finer control over how the schema is enforced, use `ToolStrategy(...)` (extracted via a synthetic tool call) or `ProviderStrategy(...)` (uses provider-native structured output, e.g. OpenAI's response format). These come from `langchain.agents` and pass through `create_deep_agent` unchanged.

### Sub-agent structured output

Same parameter on a `SubAgent` dict. The structured response is JSON-serialised and returned as the `ToolMessage` content to the parent — so the parent receives clean structured data rather than free-form prose:

```python
research_subagent = {
    "name": "research-agent",
    "description": "Research and return findings as structured JSON.",
    "system_prompt": "Research, then produce ResearchFindings.",
    "tools": [internet_search],
    "model": "anthropic:claude-sonnet-4-6",
    "response_format": ResearchFindings,
}
```

## Reading the result

After `result = agent.invoke(...)`:

```python
final_message = result["messages"][-1]                  # the agent's final user-facing reply
all_files     = result.get("files", {})                  # virtual FS state (StateBackend)
todos         = result.get("todos", [])                  # final todo list
typed         = result.get("structured_response")        # only if response_format was set
```

Note: with `StoreBackend` or `FilesystemBackend`, files won't appear in `result["files"]` because they live outside the LangGraph state. Read them via the backend directly if you need to inspect them after the run.
