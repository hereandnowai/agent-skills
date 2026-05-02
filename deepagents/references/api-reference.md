# API reference — `create_deep_agent`

This file is the authoritative parameter reference. Load it when you need exact types, semantics, or edge cases. The canonical entry points are:

```python
from deepagents import create_deep_agent, async_create_deep_agent
```

Both factories share an identical signature; the async variant just sets `is_async=True` on the underlying agent builder, which changes how `SubAgentMiddleware` invokes tools and sub-agents. **Use `async_create_deep_agent` whenever any tool is async** (e.g. tools loaded via `langchain-mcp-adapters`).

## Full signature (v0.4.x / 0.5)

```python
create_deep_agent(
    model: str | BaseChatModel | None = None,
    tools: Sequence[BaseTool | Callable | dict[str, Any]] | None = None,
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

## Per-parameter reference

### `model`
- **Type:** `str | BaseChatModel | None`.
- **Default:** `None`, which resolves to `"anthropic:claude-sonnet-4-6"` via `get_default_model()`.
- **String form:** `"<provider>:<model>"`. Recognised providers include `anthropic:`, `openai:`, `azure_openai:`, `google_genai:`, `bedrock_converse`, `huggingface`, `openrouter:`, `fireworks:`, `baseten:`, `ollama:`. The string is passed to `langchain.chat_models.init_chat_model` with default kwargs.
- **Instance form:** any LangChain chat model that supports tool calling. Use this when you need custom kwargs (timeouts, retries, base URL, etc.):
  ```python
  from langchain.chat_models import init_chat_model
  model = init_chat_model("claude-sonnet-4-6", max_retries=10, timeout=120)
  ```
- **Hard requirement:** the model must support tool calling. Models without function calling will not work.
- **Best practice:** always set this explicitly. Pinning the model avoids breakage when defaults shift across versions.

### `tools`
- **Type:** `Sequence[BaseTool | Callable | dict[str, Any]] | None`.
- **Default:** `None` (i.e. only the built-in tools are exposed).
- **Behavior:** custom tools are **merged** with the built-ins (`write_todos`, `ls`, `read_file`, `write_file`, `edit_file`, `glob`, `grep`, `task`, optionally `execute`). You don't replace them.
- **Accepted forms:** plain Python callables (auto-wrapped using their docstring/typehints), `@tool`-decorated objects, `BaseTool` instances, or LangChain dict tool specs.
- **Best practice:** use `@tool` so docstrings become the description the model sees:
  ```python
  from langchain.tools import tool

  @tool
  def search_code(query: str) -> list[str]:
      """Search the codebase for occurrences of `query` and return matching files."""
      ...
  ```

### `system_prompt`
- **Type:** `str | SystemMessage | None`.
- **Default:** `None` (just the harness prompt).
- **Critical semantics:** **prepended** to the deep-agent base prompt, not replacing it. Each middleware appends its own tool-use instructions on top. The final prompt the model sees is roughly:
  `<your system_prompt>` + `<base deep-agent prompt>` + `<filesystem instructions>` + `<todos instructions>` + `<subagents instructions>` + `<memory files>` + `<skill metadata>`.
- **Best practice:** describe the agent's role, the user, and the desired output style. Don't try to redefine how to use `write_todos` — the harness already does that.

### `middleware`
- **Type:** `Sequence[AgentMiddleware]`.
- **Default:** `()`.
- **Inserted between** the standard stack (`TodoListMiddleware`, `FilesystemMiddleware`, `SubAgentMiddleware`, `SummarizationMiddleware`) and the tail middleware (`AnthropicPromptCachingMiddleware`, `PatchToolCallsMiddleware`).
- **Conditional middleware** (added automatically when their parameters are present): `MemoryMiddleware` (when `memory=`), `SkillsMiddleware` (when `skills=`), `HumanInTheLoopMiddleware` (when `interrupt_on=`), `_PermissionMiddleware` (when filesystem `permissions` are passed).
- **See:** `references/middleware.md` for hooks, ordering rules, and concurrency safety.

### `subagents`
- **Type:** `list[SubAgent | CompiledSubAgent | AsyncSubAgent] | None`.
- **Default:** `None` (a `general-purpose` sub-agent is auto-added regardless).
- **See:** `references/subagents.md` for the three sub-agent types, validation rules, and inheritance semantics.

### `skills`
- **Type:** `list[str] | None`.
- **Default:** `None`.
- **Semantics:** POSIX paths (relative to the backend root) where `SKILL.md` files live. Loaded via progressive disclosure — only the metadata is in context until the agent decides a skill is relevant. Last source wins for same-named skills.
- **See:** `references/skills-and-memory.md`.

### `memory`
- **Type:** `list[str] | None`.
- **Default:** `None`.
- **Semantics:** paths to `AGENTS.md` files loaded **at startup** and injected into the system prompt. Use for project conventions, style guides, persistent context the agent always needs.
- **See:** `references/skills-and-memory.md`.

### `response_format`
- **Type:** `ResponseFormat | type[BaseModel] | dict | None`.
- **Default:** `None`.
- **Semantics:** when set, the agent produces a typed final answer accessible via `result["structured_response"]`. Accepts any `create_agent`-compatible schema (Pydantic class, `ToolStrategy(...)`, `ProviderStrategy(...)`, raw JSON schema).
- **See:** `references/streaming-and-output.md`.

### `context_schema`
- **Type:** `type[Any] | None`.
- **Default:** `None`.
- **Semantics:** immutable run-scoped context schema, passed through to LangGraph's `create_agent`. Use this for per-run configuration the agent shouldn't mutate (user IDs, tenant IDs, feature flags).

### `checkpointer`
- **Type:** `langgraph.checkpoint.base.Checkpointer | None`.
- **Default:** `None`.
- **Required for:** human-in-the-loop (`interrupt_on`), cross-turn conversation persistence, time-travel debugging.
- **Common choices:** `MemorySaver()` for dev, `AsyncPostgresSaver` / `AsyncSqliteSaver` for production. On LangSmith Deployment, the platform provisions one.

### `store`
- **Type:** `langgraph.store.base.BaseStore | None`.
- **Default:** `None`.
- **Required for:** any backend that uses `StoreBackend` (cross-thread persistence). Pass `InMemoryStore()` for dev. **Omit on LangSmith Deployment** — the platform provisions one and double-providing is an error.

### `backend`
- **Type:** `BackendProtocol | BackendFactory | None`.
- **Default:** `None` → resolves to `StateBackend()` (in-state, per-thread, ephemeral).
- **Factory form:** a callable `(runtime) -> BackendProtocol`. Useful when the backend depends on runtime context (e.g. a per-tenant `StoreBackend` namespace).
- **`SandboxBackendProtocol`:** subset that adds `execute(command, timeout=...) -> ExecuteResponse`. Only sandbox backends expose the `execute` tool.
- **See:** `references/backends-and-sandboxes.md`.

### `interrupt_on`
- **Type:** `dict[str, bool | InterruptOnConfig] | None`.
- **Default:** `None`.
- **Shorthand:** `True` → all decisions allowed (`approve` / `edit` / `reject`); `False` → never interrupt.
- **Full config:** `{"allowed_decisions": ["approve", "reject"]}` to restrict decision types.
- **See:** `references/human-in-the-loop.md`.

### `debug`
- **Type:** `bool`. Default `False`. Sets LangGraph debug mode — verbose logs, useful for development only.

### `name`
- **Type:** `str | None`.
- **Default:** `None`.
- **Semantics:** surfaced as `lc_agent_name` in tracing metadata. Set this in production for readable LangSmith traces.

### `cache`
- **Type:** `langchain.cache.BaseCache | None`. Default `None`. Standard LangChain cache for chat-model calls.

## Return value

`create_deep_agent(...)` returns a **compiled LangGraph `CompiledStateGraph`**. That means you get, without any adapter code:

- `agent.invoke(input, config=...)` — sync.
- `agent.ainvoke(input, config=...)` — async.
- `agent.stream(input, config=..., stream_mode=..., subgraphs=..., version="v2")` — sync streaming.
- `agent.astream(...)` — async streaming.
- LangGraph Studio rendering, LangSmith Deployment, time-travel, interrupts, checkpointing.

## Input schema

The state passed to `invoke`/`ainvoke`/`stream`:

```python
{
    "messages": [{"role": "user", "content": "..."}, ...],   # required
    "files": {                                                # optional, seeds the virtual FS
        "/notes.md": create_file_data("..."),
        "/skills/my-skill/SKILL.md": create_file_data("..."),
    },
    # plus any custom state fields added by middleware
}
```

`create_file_data` is from `deepagents.backends.utils`. Virtual paths must always start with `/`.

## Output schema

The result mirrors the input plus:

```python
{
    "messages": [...],                 # full updated history
    "files": {...},                    # virtual filesystem after the run (StateBackend only)
    "todos": [...],                    # final todo list
    "structured_response": <obj>,      # only if response_format was set
    # plus any custom state fields contributed by middleware
}
```

## Invocation patterns

```python
# Sync
result = agent.invoke({"messages": [{"role": "user", "content": "..."}]})

# Async
result = await agent.ainvoke({"messages": [...]})

# With persistence (any persistent checkpointer)
config = {"configurable": {"thread_id": "user-123"}}
result = agent.invoke({"messages": [...]}, config=config)
# Continue the same conversation later with the same thread_id and the messages will be remembered.

# Streaming updates (best for showing tool calls and results live)
for chunk in agent.stream(
    {"messages": [...]},
    stream_mode="updates",
    subgraphs=True,         # surface sub-agent events too
    version="v2",
):
    ns = chunk.get("ns") or ()
    where = "subagent" if ns else "main"
    print(where, chunk["data"])
```

## Quick gotcha checklist (top 5)

1. `tools` and `model` are **required** for declarative `SubAgent` dicts — not optional.
2. `system_prompt` is **prepended**, not replacement.
3. `execute` only works with a `SandboxBackendProtocol` backend.
4. `interrupt_on` is silently ignored without a `checkpointer`.
5. Virtual filesystem paths must start with `/`.
