# Sub-agents

Sub-agents are how a deep agent **isolates** context. The supervisor delegates a focused subtask via the `task` tool, the sub-agent runs in its own context window, and only its **last message** comes back as a `ToolMessage`. Everything the sub-agent saw, searched, or wrote stays in the sub-agent — the supervisor's context window stays small.

There are three sub-agent types. Pick by use case, not by complexity:

| Type | Use when… | Inheritance of `interrupt_on` |
|---|---|---|
| `SubAgent` (declarative dict) | The sub-task is well-defined and can be expressed as "tools + prompt + model" | Inherits parent's `interrupt_on` unless overridden |
| `CompiledSubAgent` | You already have a custom LangGraph (e.g. multi-step graph, custom routing) | Does **not** inherit; configure HITL inside |
| `AsyncSubAgent` (v0.5+) | The sub-task is long-running and shouldn't block the supervisor | Does **not** inherit; configure HITL on the remote |

## 1. `SubAgent` — declarative dict

The most common form. A plain dict (or `TypedDict`) handed to `subagents=[...]`.

```python
research_subagent = {
    "name": "research-agent",                    # required, must be unique
    "description": "Use for in-depth research on a single focused topic. Hand it a precise question.",
                                                  # required, the supervisor reads this to choose
    "system_prompt": "You are an expert researcher. Search broadly, then write a tight summary.",
                                                  # required (was `prompt` in 0.0.x — DON'T use that)
    "tools": [internet_search],                  # required in 0.4.x
    "model": "anthropic:claude-sonnet-4-6",      # required in 0.4.x
    # All optional below:
    "middleware": [...],                         # extra middleware just for this subagent
    "interrupt_on": {...},                       # override inherited HITL rules
    "skills": ["/skills/research/"],             # opt in to specific skills
    "response_format": MyPydanticSchema,         # require structured output
}
```

**Critical 0.4.x change:** `tools` and `model` are no longer optional for declarative `SubAgent` dicts. The factory raises a validation error if either is missing. Older 0.0.x code samples leave them out — don't.

The `description` field is *the* signal the supervisor uses to route. Write it imperatively ("Use for…" / "Use when…") and be specific. Vague descriptions cause the supervisor to misroute or to bypass the sub-agent entirely.

### What a sub-agent inherits automatically

Every declarative `SubAgent` is built with the standard middleware stack (`TodoListMiddleware`, `FilesystemMiddleware`, `SubAgentMiddleware`, `SummarizationMiddleware`, etc.) — so it gets its own `write_todos`, `read_file`, `write_file`, `task`, etc., plus a clean isolated context window. You don't need to add these manually.

### Filesystem sharing

Sub-agents share the same backend (and therefore the same virtual filesystem) as the supervisor. This is intentional — the supervisor can write a brief, the sub-agent can read it, the sub-agent can write a draft, the supervisor can read the draft. Treat the filesystem as the cross-agent message bus.

## 2. `CompiledSubAgent` — wrap an existing graph

When the sub-task isn't a simple tool-loop — e.g. it has its own routing logic, multiple LLM calls, conditional edges — build a LangGraph and wrap it.

```python
from deepagents import CompiledSubAgent, create_deep_agent
from langchain.agents import create_agent

specialist_graph = create_agent(
    model="anthropic:claude-sonnet-4-6",
    tools=specialized_tools,
    prompt="You are a specialised data analyst...",
)

data_subagent = CompiledSubAgent(
    name="data-analyzer",
    description="Use for SQL/analytical questions over the warehouse.",
    runnable=specialist_graph,
)

agent = create_deep_agent(
    model="anthropic:claude-sonnet-4-6",
    subagents=[data_subagent],
    system_prompt="You are an analytics lead. Delegate analysis to data-analyzer.",
)
```

**Constraint on custom graphs:** if you build a graph from scratch (instead of via `create_agent`), the state schema **must include a `messages` key**. `SubAgentMiddleware` extracts the last message from that list to return to the parent.

`CompiledSubAgent` does **not** inherit the parent's `interrupt_on`. If the wrapped graph needs HITL, configure it inside.

## 3. `AsyncSubAgent` — long-running remote sub-agent (v0.5+)

For sub-tasks that run for minutes or hours (deep research, large compilation jobs, long writeups), an `AsyncSubAgent` points at any Agent-Protocol-compliant remote — typically a LangGraph deployment or a small FastAPI server.

```python
from deepagents import AsyncSubAgent, create_deep_agent

agent = create_deep_agent(
    model="anthropic:claude-sonnet-4-6",
    subagents=[
        AsyncSubAgent(
            name="researcher",
            description="Use for deep research that may take 5+ minutes.",
            url="https://research-agent.your-domain.dev",   # omit for in-process ASGI
            graph_id="research_agent",
            # headers={"Authorization": "Bearer ..."} optional
        ),
    ],
    system_prompt="You are a coordinator. Kick off long research with `start_async_task`, keep the user updated, and gather results when ready.",
)
```

When **any** `AsyncSubAgent` is in the `subagents` list, the supervisor gains five new tools (added by `AsyncSubAgentMiddleware`):

- `start_async_task` — kick off a remote task, returns a task ID immediately.
- `check_async_task` — poll for status / partial results.
- `update_async_task` — send a follow-up message into the remote.
- `cancel_async_task` — kill it.
- `list_async_tasks` — see everything in flight.

The supervisor uses **fire-and-forget** semantics: it starts the task, keeps talking to the user, and checks back later. Multiple async sub-agents can run concurrently. The supervisor's context never blocks.

## The `task` tool

The supervisor doesn't call sub-agents directly — it calls the `task` tool, which `SubAgentMiddleware` injects. Schema:

```python
{
    "description": "What the sub-agent should do (acts as the user message to the sub-agent)",
    "subagent_type": "research-agent"   # one of the registered subagent names
}
```

The middleware filters state, dispatches to the chosen sub-agent, and returns a `Command` that updates the supervisor's state. Only the sub-agent's last message is folded back as a `ToolMessage`.

## The auto-injected `general-purpose` sub-agent

`deepagents` always adds a sub-agent named `general-purpose` that inherits the supervisor's tools and skills. The supervisor uses it as a fallback when no other sub-agent fits. To customise:

```python
agent = create_deep_agent(
    model="anthropic:claude-sonnet-4-6",
    tools=[internet_search],
    subagents=[{
        "name": "general-purpose",                          # exact name to override
        "description": "General purpose helper for ad-hoc multi-step tasks.",
        "system_prompt": "You are a careful generalist.",
        "tools": [internet_search],
        "model": "anthropic:claude-sonnet-4-6",
    }],
)
```

To remove it entirely, configure the active harness profile's general-purpose subagent enabled flag to `False` (advanced; typically not needed).

## Streaming sub-agent events

Sub-agents are LangGraph subgraphs. To see their events in a stream, you must opt in:

```python
for chunk in agent.stream(
    {"messages": [...]},
    stream_mode="updates",
    subgraphs=True,        # required to surface sub-agent events
    version="v2",          # typed events
):
    ns = chunk.get("ns") or ()
    is_subagent = any(s.startswith("tools:") for s in ns)
    label = f"[subagent {ns}]" if is_subagent else "[main]"
    print(label, chunk["data"])
```

Sub-agent events have a non-empty namespace tuple in `chunk["ns"]` whose segments include `tools:<tool_call_id>`. In LangSmith traces, sub-agent runs are nested under the parent and labelled with `lc_agent_name`.

## Sub-agent structured output

Pass `response_format` on the `SubAgent` dict to require the sub-agent to produce structured output. The result is JSON-serialised and returned as the `ToolMessage` content to the parent — so the parent sees clean structured data rather than free-form prose.

```python
from pydantic import BaseModel, Field

class ResearchFindings(BaseModel):
    key_facts: list[str] = Field(description="3-5 most important facts found.")
    sources: list[str] = Field(description="URLs of sources cited.")
    confidence: str = Field(description="One of: high, medium, low.")

research_subagent = {
    "name": "research-agent",
    "description": "Research a topic and return structured findings.",
    "system_prompt": "Research the topic. Always return structured findings.",
    "tools": [internet_search],
    "model": "anthropic:claude-sonnet-4-6",
    "response_format": ResearchFindings,
}
```

## When to reach for a sub-agent (and when not to)

**Use a sub-agent** when:
- The subtask is **context-heavy** and the parent only needs a summary back. Search-heavy research is the textbook case.
- You want **parallelism** across independent subtasks (e.g. researching three competitors at once — fire three `task` calls).
- You need a **different model** for the sub-task (e.g. supervisor on Sonnet, sub-agent on a cheaper model for bulk processing).
- You need a **different tool palette** for the sub-task (e.g. a sub-agent that only has read-only access while the supervisor can write).

**Don't use a sub-agent** when:
- The work is a simple parallel tool call. Calling three independent APIs doesn't need three sub-agents — the model can just call the tools in parallel.
- The sub-task needs to share lots of in-flight context with the parent. Sub-agents start fresh and only see what the parent passes in the `description` field.
- The result you need from the sub-agent is the entire transcript, not a summary. By design only the last message comes back.

## Inheritance summary

| Feature | Declarative `SubAgent` | `CompiledSubAgent` | `AsyncSubAgent` |
|---|---|---|---|
| Standard middleware (todos, FS, summarization) | Auto-applied | You configure inside the graph | Configured on the remote |
| Parent `interrupt_on` | Inherits, override possible | **Does not inherit** | **Does not inherit** |
| Parent `skills` | Pass `skills=[...]` to opt in | You configure inside | You configure on the remote |
| Parent backend / filesystem | Shares it | Up to you | Independent (remote) |
| Parent tools | Does not auto-share — list explicitly under `tools` | Up to you | Independent (remote) |

The `general-purpose` sub-agent is the one exception: it inherits both tools and skills from the parent unless overridden.
