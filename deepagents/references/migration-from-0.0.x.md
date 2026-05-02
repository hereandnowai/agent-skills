# Migrating from `deepagents` 0.0.x to 0.4+

This is the file to load when the user has older `deepagents` code (or copy-pasted an older blog post / README example) and asks you to make it run on the current API. The migration is mechanical — same shape, mostly renames and a few new requirements.

## At a glance

| 0.0.x | 0.4+ |
|---|---|
| `create_deep_agent(model, instructions=..., tools=..., subagents=...)` | `create_deep_agent(model=..., tools=..., system_prompt=..., subagents=...)` |
| `prompt=` on top-level (alias of `instructions`) | `system_prompt=` only |
| `SubAgent(prompt=..., tools=..., model=...)` — `tools`/`model` optional | `SubAgent(system_prompt=..., tools=..., model=...)` — both required |
| Default model `claude-sonnet-4-20250514` | `anthropic:claude-sonnet-4-6` |
| FS only had ls/read/write/edit | adds `glob`, `grep` |
| `execute` always present | only with a `SandboxBackendProtocol` backend |
| No `skills=`, `memory=`, `permissions=`, `interrupt_on=` | All four available |
| Single hardcoded backend | Pluggable backends (`StateBackend`, `FilesystemBackend`, `StoreBackend`, `CompositeBackend`, sandboxes) |

## Step 1 — Rename `instructions` / `prompt` → `system_prompt`

```python
# Before (0.0.x):
agent = create_deep_agent(
    model,
    instructions="You are a research assistant.",
    tools=[search],
)

# After (0.4+):
agent = create_deep_agent(
    model="anthropic:claude-sonnet-4-6",
    tools=[search],
    system_prompt="You are a research assistant.",
)
```

`instructions=` is gone. `prompt=` is gone. The single replacement is `system_prompt=`.

## Step 2 — Make every `SubAgent` complete

```python
# Before (0.0.x):
research_subagent = {
    "name": "research-agent",
    "description": "Research things",
    "prompt": "You are a researcher.",
    # tools and model often omitted; harness inherited them
}

# After (0.4+):
research_subagent = {
    "name": "research-agent",
    "description": "Research things",
    "system_prompt": "You are a researcher.",      # was `prompt`
    "tools": [search],                             # now required
    "model": "anthropic:claude-sonnet-4-6",        # now required
}
```

In 0.4+, the validator raises `ValueError` if `tools` or `model` is missing on a declarative `SubAgent`. There's no implicit inheritance — list explicitly.

## Step 3 — Pin the model

The default has shifted at least twice (`claude-sonnet-4-20250514` → `claude-sonnet-4-5-20250929` → `claude-sonnet-4-6`). Don't rely on the default; pass an explicit `model=` everywhere.

```python
# Before (relying on default):
agent = create_deep_agent(instructions="...", tools=[...])

# After:
agent = create_deep_agent(
    model="anthropic:claude-sonnet-4-6",
    tools=[...],
    system_prompt="...",
)
```

## Step 4 — Decide whether you need `execute`

In 0.0.x, `execute` was on by default. In 0.4+, it's only present if the backend implements `SandboxBackendProtocol`. If your old agent expected to run shell commands, plug in a sandbox:

```python
# Before:
agent = create_deep_agent(model, instructions="...")    # `execute` was magic-on

# After:
from langchain_modal import ModalSandbox
import modal

modal_sandbox = modal.Sandbox.create(app=modal.App.lookup("...") )
agent = create_deep_agent(
    model="anthropic:claude-sonnet-4-6",
    system_prompt="...",
    backend=ModalSandbox(sandbox=modal_sandbox),
)
```

For local-only trusted dev, `LocalShellBackend(root_dir=".")` is the closest 0.4 analogue — but never use it in production. See `references/backends-and-sandboxes.md`.

## Step 5 — Re-check the filesystem tools

In 0.4+ the filesystem additionally exposes `glob` and `grep`. If your old prompts said "use `read_file` to scan the repo," update them to use `glob`/`grep` first — much cheaper.

Also: read-truncation behavior is more aggressive in 0.4+ (large reads are clipped with a "[Output was truncated…]" marker). If your prompts assume `read_file` always returns the full content, adjust them to use `slice_read_response` semantics or pre-filter via `grep`.

## Step 6 — If you used custom tools that return long strings

The auto-offload behavior in 0.4+ writes large tool outputs to the virtual FS instead of the message stream. If your old code consumed long outputs directly from `result["messages"]`, switch to reading them from `result["files"]` (or have the tool itself return the path it wrote to).

## Step 7 — If you wrapped sub-agents in custom graphs

`CompiledSubAgent` is the supported wrapper now. Old code that constructed a sub-agent's graph and shoved it into the `subagents` list directly will break — re-wrap it:

```python
# Before (rough shape):
subagents = [{
    "name": "data-analyzer",
    "description": "...",
    "graph": custom_graph,    # variable shape, sometimes accepted
}]

# After:
from deepagents import CompiledSubAgent
subagents = [
    CompiledSubAgent(
        name="data-analyzer",
        description="...",
        runnable=custom_graph,
    ),
]
```

Custom graph constraint: the state schema **must include `messages`**, because `SubAgentMiddleware` extracts the last message to return.

## Step 8 — If you relied on the default `general-purpose` sub-agent's tools

In 0.4+, the auto-injected `general-purpose` sub-agent inherits the supervisor's tools and skills. If you customised it, override by including a sub-agent dict named exactly `"general-purpose"`:

```python
subagents=[{
    "name": "general-purpose",
    "description": "General helper",
    "system_prompt": "You are a careful generalist.",
    "tools": [...],
    "model": "anthropic:claude-sonnet-4-6",
}]
```

## Step 9 — Adopt the new capabilities you missed

Once the migration runs, consider whether to take advantage of the 0.4+ features that didn't exist before:

- `memory=["/AGENTS.md"]` for project conventions.
- `skills=["/skills/"]` for reusable workflows.
- `interrupt_on={...}` + `checkpointer=...` for HITL.
- `permissions=[...]` for filesystem ACL.
- `response_format=MyPydantic` for structured final output.
- `AsyncSubAgent(...)` for long-running remote work (v0.5).

## Quick migration check script

Drop this in `tests/test_migration_smoke.py` to catch the most common breakages:

```python
from deepagents import create_deep_agent

def test_agent_builds():
    agent = build_agent()                      # your factory
    # The compiled graph should expose these:
    assert hasattr(agent, "invoke")
    assert hasattr(agent, "ainvoke")

def test_subagents_have_required_fields():
    # Every declarative SubAgent dict must include both tools and model.
    from my_agent.subagents import all_subagents
    for sa in all_subagents:
        if isinstance(sa, dict):
            assert "tools" in sa, f"{sa['name']} missing `tools`"
            assert "model" in sa, f"{sa['name']} missing `model`"
            assert "system_prompt" in sa, f"{sa['name']} missing `system_prompt` (was `prompt`?)"

def test_no_legacy_kwargs():
    import inspect, my_agent.agent as m
    src = inspect.getsource(m)
    assert "instructions=" not in src, "Use system_prompt= instead of instructions="
    assert "prompt=" not in src or "system_prompt=" in src, "Likely stale `prompt=`"
```

That's enough to catch ~90% of stalled migrations.
