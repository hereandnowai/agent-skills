---
name: deepagents
description: Comprehensive guide for building Python apps with the LangChain `deepagents` library — an agent harness with built-in planning, virtual filesystem, sub-agents, human-in-the-loop, MCP integration, and pluggable backends for long-running, context-heavy tasks. Use whenever the user writes code with `deepagents`, calls `create_deep_agent` or `async_create_deep_agent`, or builds a research agent, coding agent, data-analysis agent, or multi-step LangChain/LangGraph agent that needs planning + sub-agents + virtual filesystem + context engineering. Trigger on any mention of "deepagents", "deep agent", "deep agents", "LangChain agent harness", "create_deep_agent", "agent with planning tool", "multi-agent orchestration with subagents", or when the user wants an agent that handles long-horizon tasks via context offloading, summarization, and isolation. Also use when migrating older 0.0.x code to the 0.4+ API. Prefer over generic LangChain guidance whenever `deepagents` is the framework.
---

# Building with `deepagents` (LangChain Python)

`deepagents` is a Python agent harness built on LangChain + LangGraph. Calling `create_deep_agent(...)` returns a compiled LangGraph graph that already knows how to plan, write to a virtual filesystem, spawn sub-agents, and manage its own context window. Your job, when writing code that uses it, is to **wire the right capabilities together — not to reinvent them**.

This skill is the navigation hub. It contains the mental model, the 80% patterns, the gotchas, and an index into deeper reference files. **Load reference files only when needed** — they exist to keep the top-level lean while still giving you authoritative depth on demand.

---

## 1. When `deepagents` is (and isn't) the right fit

Reach for `deepagents` when **all** of these are true:
- The task is multi-step and long-horizon — the model would otherwise blow through its context window.
- The agent benefits from **planning** (writing down a todo list and updating it as it goes).
- Intermediate results, drafts, search hits, or large tool outputs need to be **stashed somewhere** other than the running message history.
- You'd want to **delegate** sub-tasks into isolated context windows (e.g. "go research X, return a summary").

For simpler agents — single tool, one-shot answer, no planning needed — use `langchain.agents.create_agent` instead. For maximum control over graph topology, use raw LangGraph. `deepagents` sits on top of both and is the right pick when you'd otherwise be re-implementing planning + filesystem + sub-agents by hand.

## 2. Mental model — the four pillars

Every `deepagents` application is built on these four pieces. Understand all four before writing code; the API only makes sense in this frame.

1. **Detailed system prompt** — a Claude-Code-inspired base prompt teaches the model how to use the planning, filesystem, and sub-agent tools. Anything you pass as `system_prompt=` is **prepended** (not replaced).
2. **Planning tool (`write_todos`)** — a near-no-op tool whose purpose is to force the model to externalize a plan. The act of writing the plan, not the tool's return value, is what improves long-horizon execution.
3. **Virtual filesystem (`ls`/`read_file`/`write_file`/`edit_file`/`glob`/`grep`)** — context offloading. Big tool outputs and intermediate artefacts go to files instead of the message stream. Backend is pluggable (state, real disk, store, sandbox).
4. **Sub-agents (the `task` tool)** — context isolation. The supervisor delegates a focused subtask, only the **last message** of the subagent comes back, the rest of the subagent's context is discarded.

These map to four context-engineering strategies: **offload** (filesystem), **isolate** (subagents), **summarize** (auto-summarization middleware), **quarantine** (sandboxes for shell). Keep that vocabulary in your head — it's how the docs talk and how to reason about adding capabilities.

## 3. Install

```bash
pip install deepagents
```

Plus the model provider package(s) you'll use:

```bash
pip install langchain-anthropic    # default model is anthropic:claude-sonnet-4-6
# or langchain-openai, langchain-google-genai, langchain-ollama, "langchain[aws]", etc.
```

API keys come from environment variables (`ANTHROPIC_API_KEY`, `OPENAI_API_KEY`, `TAVILY_API_KEY`, …). Python 3.10+.

For LangSmith tracing: `LANGSMITH_TRACING=true` and `LANGSMITH_API_KEY`.

## 4. Minimum viable agent

```python
from deepagents import create_deep_agent

def get_weather(city: str) -> str:
    """Get the weather in a city."""
    return f"It's always sunny in {city}!"

agent = create_deep_agent(
    model="anthropic:claude-sonnet-4-6",
    tools=[get_weather],
    system_prompt="You are a helpful weather assistant.",
)

result = agent.invoke({
    "messages": [{"role": "user", "content": "what is the weather in sf"}]
})
print(result["messages"][-1].content)
```

The agent already has `write_todos`, `ls`, `read_file`, `write_file`, `edit_file`, `glob`, `grep`, and `task` even though we passed only one custom tool. They are merged in by middleware automatically.

A complete, runnable version of this and six more end-to-end examples are in `examples/` — see §10.

## 5. Core API at a glance

```python
from deepagents import create_deep_agent  # or async_create_deep_agent

create_deep_agent(
    model: str | BaseChatModel | None = None,        # "anthropic:claude-sonnet-4-6" by default
    tools: Sequence[BaseTool | Callable | dict] | None = None,
    *,
    system_prompt: str | SystemMessage | None = None,
    middleware: Sequence[AgentMiddleware] = (),
    subagents: list[SubAgent | CompiledSubAgent | AsyncSubAgent] | None = None,
    skills: list[str] | None = None,
    memory: list[str] | None = None,
    response_format: ResponseFormat | None = None,
    context_schema: type[Any] | None = None,
    checkpointer: Checkpointer | None = None,
    store: BaseStore | None = None,
    backend: BackendProtocol | BackendFactory | None = None,
    interrupt_on: dict[str, bool | InterruptOnConfig] | None = None,
    debug: bool = False,
    name: str | None = None,
    cache: BaseCache | None = None,
) -> CompiledStateGraph
```

The return value is a compiled LangGraph graph, which means you also get `agent.invoke`, `agent.ainvoke`, `agent.stream`, `agent.astream`, checkpointing, time travel, LangGraph Studio, and LangSmith tracing for free — without any extra adaptation code.

**Always set `model=` and `system_prompt=` explicitly.** The defaults exist for demos but real applications should pin both for reproducibility and to make intent obvious to readers.

For the full per-parameter reference (types, semantics, edge cases), load `references/api-reference.md`.

## 6. Critical version notes — target the 0.4+ API

`deepagents` had a significant API rename between 0.0.x and the current 0.4.x line. **Old code samples on the internet may use parameters that no longer exist.** When generating code, always:

- Use `system_prompt=` (not `prompt=` / not `instructions=`).
- For declarative `SubAgent` dicts, use the key `system_prompt` and **always include `tools` and `model`** — these are now required for declarative subagents (the factory raises if they're missing).
- The default model is `anthropic:claude-sonnet-4-6`. Older docs say `claude-sonnet-4-5-20250929` or `claude-sonnet-4-20250514` — these are stale.
- `glob` and `grep` are filesystem tools (added in 0.4); the `execute` shell tool is **only** available when the backend implements `SandboxBackendProtocol`. Without a sandbox backend, calling it returns an error.

If the user's existing code uses old names, see `references/migration-from-0.0.x.md` before changing anything.

## 7. Capability map — when to load each reference

This is the index you should consult when a task involves more than the basics. **Don't read all of these up front.** Load them as the task demands.

| When the task involves… | Load this reference |
|---|---|
| Exact parameter semantics, types, return shape, edge cases | `references/api-reference.md` |
| Spawning sub-agents (declarative, compiled, or async/remote) | `references/subagents.md` |
| Choosing/configuring a filesystem backend, or running shell commands safely | `references/backends-and-sandboxes.md` |
| Adding custom middleware, summarization, prompt caching, rate limits | `references/middleware.md` |
| Approval gates / `interrupt_on` / resuming after interrupts | `references/human-in-the-loop.md` |
| Wiring MCP servers (`langchain-mcp-adapters`) into the agent | `references/mcp-integration.md` |
| Loading `AGENTS.md`, sharing skills, cross-thread memory | `references/skills-and-memory.md` |
| Streaming modes, sub-agent stream events, `response_format` Pydantic output | `references/streaming-and-output.md` |
| Deployment, tracing, cost/token control, security model | `references/production.md` |
| Migrating an existing 0.0.x codebase | `references/migration-from-0.0.x.md` |

## 8. The 80/20 architectural patterns

These are the shapes most real `deepagents` apps take. Pick the closest one and adapt; full runnable code is in `examples/`.

### 8.1 Research agent (the canonical pattern)

A supervisor with a `research-agent` sub-agent. The supervisor plans, the sub-agent does the heavy retrieval, only a summary returns. See `examples/02_research_agent.py`.

```python
from deepagents import create_deep_agent
from tavily import TavilyClient

tavily = TavilyClient()

def internet_search(query: str, max_results: int = 5, topic: str = "general") -> dict:
    """Search the web."""
    return tavily.search(query=query, max_results=max_results, topic=topic)

research_subagent = {
    "name": "research-agent",
    "description": "Use for in-depth research on a single topic. Provide a clear, focused question.",
    "system_prompt": "You are an expert researcher. Search thoroughly, then summarize.",
    "tools": [internet_search],            # ← required in 0.4.x
    "model": "anthropic:claude-sonnet-4-6", # ← required in 0.4.x
}

agent = create_deep_agent(
    model="anthropic:claude-sonnet-4-6",
    tools=[internet_search],
    system_prompt="You are a senior research lead. Plan, delegate research, then write a polished report.",
    subagents=[research_subagent],
)
```

Why this works: the supervisor's context stays small because each sub-agent's search noise is discarded after summary. Use `write_file` to stash drafts of the report between sub-agent calls.

### 8.2 Coding agent (sandbox + HITL)

Use a sandbox backend so the `execute` tool is real, and gate destructive filesystem writes with `interrupt_on`. See `examples/03_coding_agent_with_sandbox.py`.

Pick a sandbox by environment:
- **Modal / Runloop / Daytona / LangSmith** for managed remote VMs (production).
- `LocalShellBackend` only for fully trusted local development — it's an unrestricted local shell.

### 8.3 MCP-backed agent

Use `MultiServerMCPClient` from `langchain-mcp-adapters` to load tools from any MCP server (filesystem, GitHub, Slack, Postgres, …) and pass them to `async_create_deep_agent`. MCP tools are async, so use the async factory. See `examples/05_mcp_integration.py` and `references/mcp-integration.md`.

### 8.4 Human-in-the-loop agent

Pair `interrupt_on={"tool_name": True}` with a `checkpointer` (mandatory). Resume with `Command(resume=...)`. See `examples/04_hitl_with_checkpointer.py` and `references/human-in-the-loop.md`.

### 8.5 Long-running / async sub-agent (v0.5+)

For sub-agents that run for minutes or hours (deep research, long compilation), wrap a remote LangGraph deployment in an `AsyncSubAgent`. The supervisor gets `start_async_task` / `check_async_task` / `cancel_async_task` tools and uses fire-and-forget semantics. See `examples/07_async_subagents.py` and the `AsyncSubAgent` section in `references/subagents.md`.

### 8.6 Structured output

Pass a Pydantic model (or any `create_agent`-compatible schema) to `response_format=`. Read the typed result from `result["structured_response"]`. See `examples/06_structured_output.py`.

## 9. Common pitfalls (read this list before debugging)

These are the issues you'll keep hitting. Skim them every time you start a new `deepagents` project.

1. **`SubAgent` dict missing `tools` or `model`** — in 0.4.x both are required for declarative sub-agents. The factory raises a validation error. (Older 0.0.x examples on the web omit these.)
2. **Using `prompt=` or `instructions=`** — renamed to `system_prompt=` in 0.4.x.
3. **`execute` returns "no sandbox" error** — the default `StateBackend` doesn't ship `execute`. Plug in `ModalSandbox` / `LocalShellBackend` / etc.
4. **HITL interrupts don't fire** — you forgot the `checkpointer`. `interrupt_on` without a checkpointer is silently a no-op.
5. **Files vanish between invocations** — that's `StateBackend` working as designed (per-thread, ephemeral). Use `StoreBackend` (with `store=`) for cross-thread persistence, or `FilesystemBackend` for real disk.
6. **MCP tools timeout / can't `await`** — switch from `create_deep_agent` to `async_create_deep_agent` and use `agent.ainvoke` / `agent.astream`.
7. **System prompt seems ignored** — your custom prompt is **prepended** to the harness prompt, not replacing it. The base behaviors (planning, filesystem, sub-agent dispatch) stay in effect. To dramatically alter behavior, write detailed instructions, don't try to "override" the harness.
8. **Sub-agent events not streaming** — pass `subgraphs=True` and `version="v2"` to `agent.stream(...)`. Check `chunk["ns"]` to identify which subgraph.
9. **Mutating `self` in custom middleware** — race conditions across parallel sub-agents/tools. Always update graph state instead.
10. **Path errors** — virtual filesystem paths must start with `/`. `read_file("notes.md")` fails; `read_file("/notes.md")` works.
11. **`ChatAnthropic` rate limits in long runs** — bump `max_retries=10`, set a `timeout`, and add `RateLimitMiddleware` for production. See `references/production.md`.
12. **General-purpose subagent uses the wrong tools** — by default it inherits the main agent's tools. To override, include a sub-agent named exactly `"general-purpose"` in the `subagents` list.

## 10. Examples — runnable starters

The `examples/` directory contains seven progressively-more-complex working scripts. Treat these as the fastest path to a working application; copy one and adapt.

| File | Pattern shown |
|---|---|
| `examples/01_minimal.py` | The tiniest possible agent (one tool, no subagents). |
| `examples/02_research_agent.py` | Supervisor + research sub-agent + Tavily search. The canonical example. |
| `examples/03_coding_agent_with_sandbox.py` | Sandbox backend + `execute` + HITL on destructive writes. |
| `examples/04_hitl_with_checkpointer.py` | `interrupt_on` + `MemorySaver` + resume via `Command(resume=...)`. |
| `examples/05_mcp_integration.py` | `async_create_deep_agent` + `MultiServerMCPClient`. |
| `examples/06_structured_output.py` | Pydantic `response_format` and reading `structured_response`. |
| `examples/07_async_subagents.py` | `AsyncSubAgent` for long-running remote tasks. |

## 11. House style for code generation

When writing `deepagents` code, follow these defaults so the output is consistent and easy to review:

- Always pass `model=` and `system_prompt=` explicitly. Readers should see what model and what role the agent has without grepping for defaults.
- Group the agent setup (`tools`, `subagents`, the `create_deep_agent` call) into a single `build_agent()` factory function. Tests and notebooks call this; nothing else should construct the agent ad-hoc.
- Wrap network-IO tools in `@tool` from `langchain.tools` — gives proper schemas and clear docstrings the model uses for routing.
- Put the user-visible "role" of each sub-agent in its `description` field, in the imperative ("Use for…", "Use when…"). The supervisor reads only this to choose between sub-agents.
- For HITL, **always** include the `checkpointer` in the same expression as `interrupt_on`. Reviewers should never have to verify it was set somewhere else.
- For production, set `name=` so traces are readable in LangSmith.

That's the skill. Start with §4, pick a pattern from §8, copy the matching `examples/` file, and load reference files from §7 only when the task pushes past the basics.
