# Skills and memory

`deepagents` distinguishes two kinds of "memory":

1. **Working memory** — the virtual filesystem during a run (any backend). Drafts, intermediate results, search caches.
2. **Long-term memory** — content that survives across runs:
   - **`memory=[...]`** loads `AGENTS.md` files into the system prompt at startup. Always-on context.
   - **`StoreBackend`** persists actual files across threads. On-demand context the agent can read/write at will.
   - **`skills=[...]`** mounts reusable workflows (`SKILL.md` files) with progressive disclosure — only metadata is in context until the agent decides a skill is relevant.

Pick the right one by lifecycle and always-on-ness:

| Need… | Use |
|---|---|
| Project conventions / coding style / company facts the agent always needs | `memory=` (AGENTS.md) |
| Reusable workflows for specific tasks the agent occasionally does | `skills=` (SKILL.md) |
| Notes the agent itself writes for its own future runs | `StoreBackend` mounted under `/memories/` |
| Throwaway scratch within a single conversation | default `StateBackend` (any file path) |

## Memory — `AGENTS.md`

Pass `memory=["/AGENTS.md"]` and seed the file. The contents go into the system prompt at startup, every run, no exceptions:

```python
from deepagents import create_deep_agent
from deepagents.backends.utils import create_file_data
from langgraph.checkpoint.memory import MemorySaver

agents_md = """\
# Project conventions

- Python 3.11+, type hints required.
- Use ruff for linting; max line length 100.
- Tests live in `tests/`, fixtures in `tests/fixtures/`.
- Never modify generated files in `_pb2.py` or `_pb2_grpc.py`.
"""

agent = create_deep_agent(
    model="anthropic:claude-sonnet-4-6",
    memory=["/AGENTS.md"],
    checkpointer=MemorySaver(),
)

result = agent.invoke(
    {
        "messages": [{"role": "user", "content": "What's our line length limit?"}],
        "files": {"/AGENTS.md": create_file_data(agents_md)},
    },
    config={"configurable": {"thread_id": "abc"}},
)
```

A few `AGENTS.md` rules of thumb:

- **Keep it short.** Every token in `AGENTS.md` rides on every turn forever. Aim for a tight 1-2 page brief.
- **Conventions, not data.** It's for "how we work here," not "everything the agent might need to know." Reach for skills or `StoreBackend` files for the latter.
- **Multiple `AGENTS.md` files are allowed.** `memory=["/AGENTS.md", "/team/AGENTS.md"]` loads both, in order.
- **Use it for cross-cutting policies.** Things like "always escalate to a human before taking destructive actions on production data" live well in `AGENTS.md`.

## Skills — `SKILL.md`

Skills follow the [Agent Skills specification](https://agentskills.io/specification). Each skill is a directory with at minimum a `SKILL.md`, optionally with bundled `references/`, `examples/`, `assets/`, `scripts/`. Skills are **progressively disclosed**: the agent sees only the skill's name and short description in context until it decides the skill is relevant, at which point the harness reads the full `SKILL.md`.

```python
from deepagents import create_deep_agent
from deepagents.backends.utils import create_file_data
from langgraph.checkpoint.memory import MemorySaver

skill_md = """\
---
name: write-changelog
description: Use when the user asks for a changelog or release notes for a git range.
---

# Writing a changelog

Group commits by type (feat / fix / chore / docs / refactor / test).
Skip merge commits and reverts. ...
"""

agent = create_deep_agent(
    model="anthropic:claude-sonnet-4-6",
    skills=["/skills/"],          # one or more skill source directories
    checkpointer=MemorySaver(),
)

agent.invoke(
    {
        "messages": [{"role": "user", "content": "Draft release notes for v1.4."}],
        "files": {
            "/skills/write-changelog/SKILL.md": create_file_data(skill_md),
        },
    },
    config={"configurable": {"thread_id": "rn-1"}},
)
```

A few key rules:

- **Multiple sources, last wins.** `skills=["/skills/built-in/", "/skills/user/"]` — if both have a `write-changelog` skill, the user one wins.
- **Sub-agents don't auto-inherit skills.** Add `skills=[...]` to a `SubAgent` dict to opt that sub-agent in. Exception: the auto-injected `general-purpose` sub-agent inherits the supervisor's skills.
- **Make `description` precise.** The agent only loads the full skill when its description matches the situation. Vague descriptions either over-trigger (wasting context) or under-trigger (skill is invisible).

For authoring guidance see the Agent Skills spec; the patterns are very close to the SKILL.md you're reading right now.

## Persistent files via `StoreBackend`

For files the agent itself reads and writes across runs (e.g. "remember that the user prefers metric units" or "carry research notes between sessions"), mount a `StoreBackend` under a known prefix:

```python
from deepagents import create_deep_agent
from deepagents.backends import CompositeBackend, StateBackend, StoreBackend
from langgraph.store.memory import InMemoryStore
from langgraph.checkpoint.memory import MemorySaver

agent = create_deep_agent(
    model="anthropic:claude-sonnet-4-6",
    backend=CompositeBackend(
        default=StateBackend(),
        routes={
            "/memories/": StoreBackend(namespace=lambda ctx: (ctx.runtime.context.user_id,)),
        },
    ),
    store=InMemoryStore(),
    checkpointer=MemorySaver(),
    system_prompt=(
        "You are a personal assistant. Persistent notes about the user live in /memories/. "
        "Read them at the start of every session. Update them when you learn something new."
    ),
)
```

For production, use a Postgres-backed store (`langgraph-checkpoint-postgres`) — `InMemoryStore` is dev-only. On LangSmith Deployment, omit `store=` (the platform provides one).

## "Memory-first protocol" pattern (from the CLI)

The `deepagents-cli` follows what it calls a Memory-First Protocol: at the start of every turn, the agent reads everything under `/memories/`, decides if anything is relevant, and only then engages with the user's message. After the turn, it writes notable new facts back. To replicate:

```
You are a memory-aware assistant. Follow this protocol:
1. At the start of every turn, ls /memories/ and read each file there.
2. Decide which memories are relevant and weight your response accordingly.
3. After answering, if you learned a durable new fact about the user or task,
   write or update a memory file under /memories/.
4. Use file names like /memories/preferences.md, /memories/projects/<name>.md.
```

Place this in the `system_prompt`, mount `/memories/` on a `StoreBackend`, and the agent self-manages.

## Cross-checking: what to put where

A real production setup typically uses all three:

```python
agent = create_deep_agent(
    model="anthropic:claude-sonnet-4-6",
    system_prompt="You are an engineering assistant for ACME Corp.",
    memory=["/AGENTS.md"],                 # always-on conventions
    skills=["/skills/"],                   # workflows: write-changelog, run-migration, etc.
    backend=CompositeBackend(
        default=StateBackend(),
        routes={
            "/memories/": StoreBackend(namespace=lambda c: (c.runtime.context.user_id,)),
            "/skills/":   StoreBackend(namespace=lambda _: ("skills",)),
        },
    ),
    store=InMemoryStore(),
    checkpointer=MemorySaver(),
)
```

- `/AGENTS.md` rides every turn — keep tiny.
- `/skills/` is shared and loaded only when needed — verbose is fine.
- `/memories/` is per-user, written by the agent itself.
- Everything else (`/scratch.md`, `/draft.md`) is ephemeral.
