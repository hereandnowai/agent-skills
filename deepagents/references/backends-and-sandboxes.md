# Backends and sandboxes

Backends are the storage layer behind the virtual filesystem tools (`ls`, `read_file`, `write_file`, `edit_file`, `glob`, `grep`). They share a `BackendProtocol`. Sandbox backends additionally implement `SandboxBackendProtocol`, which adds the `execute(command, timeout=...)` method — and **only sandbox backends expose the `execute` shell tool** to the model. With the default `StateBackend`, calling `execute` returns an error.

Pick the backend by **persistence model** and **whether you need shell access**:

| Need… | Backend |
|---|---|
| Throwaway working memory for a single conversation | `StateBackend` (default) |
| Real disk on the host (notes, configs, source files) | `FilesystemBackend(root_dir=..., virtual_mode=True)` |
| Local shell + real disk for trusted dev | `LocalShellBackend(root_dir=...)` ⚠️ unrestricted |
| Cross-thread / cross-session persistence | `StoreBackend(namespace=...)` + a `BaseStore` |
| Mix of the above by path prefix | `CompositeBackend(default=..., routes={...})` |
| Isolated remote VM with shell, network, package install | `ModalSandbox` / `RunloopSandbox` / `DaytonaSandbox` / `LangSmithSandbox` |

## `StateBackend` — the default

In-state, per-thread, ephemeral. Files live inside the LangGraph state under the `files` key. Good for:
- single-session work,
- demos, notebooks, tests,
- agents whose only artefacts are intermediate drafts.

Seed the FS at invoke time:

```python
from deepagents import create_deep_agent
from deepagents.backends.utils import create_file_data

agent = create_deep_agent(model="anthropic:claude-sonnet-4-6")

result = agent.invoke({
    "messages": [{"role": "user", "content": "Summarize the briefing then write a reply."}],
    "files": {
        "/briefing.md": create_file_data("…long briefing text…"),
    },
})

# Read out files the agent wrote:
for path, file_data in result["files"].items():
    print(path, "→", file_data["content"][:200])
```

Combine with a `checkpointer` if you need the in-state files to survive across turns of a conversation.

## `FilesystemBackend` — real disk

Maps virtual paths to real disk under `root_dir`. The agent now reads/writes actual files. Use this for:
- coding agents on a local repo,
- agents that consume real config/data files,
- producing artefacts (reports, scripts) the user wants on disk.

```python
from deepagents.backends import FilesystemBackend

agent = create_deep_agent(
    model="anthropic:claude-sonnet-4-6",
    backend=FilesystemBackend(root_dir="/path/to/workspace", virtual_mode=True),
    system_prompt="You are a coding assistant. The repo is at /.",
)
```

`virtual_mode=True` is the safe default — it prevents path traversal outside `root_dir`. Only set `virtual_mode=False` if you genuinely want the agent to roam the host filesystem.

`FilesystemBackend` does **not** expose `execute` — it doesn't implement `SandboxBackendProtocol`. If you need shell access on the local host, use `LocalShellBackend`.

## `LocalShellBackend` — real disk + shell ⚠️

Same disk semantics as `FilesystemBackend`, plus an `execute` tool that runs commands on the **local machine** with no sandboxing. There is no resource limit, no network jail, no rollback. Use only on:
- a developer's own machine, in a dev workflow,
- short-lived CI containers you control fully.

For anything else, use a real sandbox backend (Modal, Runloop, Daytona, LangSmith). For production agents that touch user data or run untrusted code, **never** use `LocalShellBackend`.

## `StoreBackend` — durable cross-thread storage

Backed by a LangGraph `BaseStore`. Files survive across conversation threads and (with a persistent store) across processes. The `namespace` callable takes a runtime context and returns a tuple — typically used for multi-tenant isolation:

```python
from deepagents import create_deep_agent
from deepagents.backends import StoreBackend
from langgraph.store.memory import InMemoryStore

agent = create_deep_agent(
    model="anthropic:claude-sonnet-4-6",
    backend=StoreBackend(namespace=lambda ctx: (ctx.runtime.context.user_id,)),
    store=InMemoryStore(),     # use a Postgres store in production
)
```

For production: use one of the `langgraph-checkpoint-*` store packages (Postgres, Redis). On LangSmith Deployment, omit `store=` — the platform provisions one and double-providing is an error.

## `CompositeBackend` — route by path prefix

The most common production pattern: per-thread state for working memory, persistent store for long-term memory, all behind one filesystem.

```python
from deepagents import create_deep_agent
from deepagents.backends import CompositeBackend, StateBackend, StoreBackend
from langgraph.store.memory import InMemoryStore

agent = create_deep_agent(
    model="anthropic:claude-sonnet-4-6",
    backend=CompositeBackend(
        default=StateBackend(),
        routes={
            "/memories/": StoreBackend(namespace=lambda ctx: (ctx.runtime.context.user_id,)),
            "/skills/":   StoreBackend(namespace=lambda _: ("skills",)),
        },
    ),
    store=InMemoryStore(),
    skills=["/skills/"],
)
```

Now `/memories/notes.md` survives across threads, while `/scratch.md` is ephemeral. The path prefix routing is invisible to the agent — it just sees one filesystem.

## Sandbox backends — isolated remote VMs

Sandbox backends implement `SandboxBackendProtocol`, so the model gets the full kit including a real `execute` tool that runs in a remote, isolated environment.

### Modal

```python
import modal
from deepagents import create_deep_agent
from langchain_anthropic import ChatAnthropic
from langchain_modal import ModalSandbox

app = modal.App.lookup("your-app")
sandbox = modal.Sandbox.create(app=app)
backend = ModalSandbox(sandbox=sandbox)

agent = create_deep_agent(
    model=ChatAnthropic(model="claude-sonnet-4-6"),
    backend=backend,
    system_prompt="You are a Python coding assistant. The workspace is /workspace.",
)
try:
    result = agent.invoke({"messages": [{"role": "user", "content": "Create a package, write a test, run pytest."}]})
finally:
    sandbox.terminate()
```

Always wrap in `try/finally` and call `sandbox.terminate()` — sandboxes cost money per second.

### Other sandbox options

- **Runloop** (`langchain-runloop`): isolated Devbox VMs, persistent across invocations.
- **Daytona** (`langchain-daytona`): self-hosted dev environments.
- **LangSmith Sandbox** (`langsmith[sandbox]`, currently private beta): Anthropic-managed, integrates with LangSmith Deployment.

All four follow the same pattern: instantiate the sandbox class, pass to `backend=`, dispose at the end.

## File data shape

Every backend stores files as the same shape, accessible via `result["files"]` with `StateBackend`:

```python
{
    "content": str,         # utf-8 text or base64-encoded binary
    "encoding": "utf-8" | "base64",
    "created_at": str,      # ISO 8601
    "modified_at": str,     # ISO 8601
}
```

Helpers from `deepagents.backends.utils` (use these instead of constructing dicts by hand):

- `create_file_data(content, encoding="utf-8")` — make a fresh `FileData`.
- `update_file_data(existing, new_content)` — bumps `modified_at`.
- `file_data_to_string(file_data)` — extract the content for display.
- `validate_path(path)` — enforce the `/`-prefix rule.
- `format_content_with_line_numbers(text)` — what `read_file` shows the model.
- `perform_string_replacement(...)` — what `edit_file` uses; raises if occurrence count is wrong.
- `truncate_if_too_long(text, limit)` — for custom backends to mimic the auto-truncation.

## Filesystem permissions

For finer-grained control than "is the backend sandboxed" you can pass a `permissions=[...]` list of `FilesystemPermission` rules. Rules are evaluated in declaration order, **first match wins**, default is permissive:

```python
from deepagents import create_deep_agent
from deepagents.backends import FilesystemBackend
# from deepagents... import FilesystemPermission   # check current import path

agent = create_deep_agent(
    model="anthropic:claude-sonnet-4-6",
    backend=FilesystemBackend(root_dir="/repo"),
    # permissions=[
    #     FilesystemPermission(action="deny",  pattern="/.env*"),
    #     FilesystemPermission(action="deny",  pattern="/.git/**"),
    #     FilesystemPermission(action="allow", pattern="/**"),
    # ],
)
```

Sub-agents inherit the parent's permissions unless they specify their own. The `_PermissionMiddleware` is appended last in the middleware stack so it sees every tool call, including those added by other middleware.

## Path conventions and edge cases

- **Always `/`-prefixed.** `read_file("notes.md")` fails; `read_file("/notes.md")` works. The `validate_path` helper enforces this.
- **Empty files.** `read_file` returns the literal string `"System reminder: File exists but has empty contents"` — by design, so the model knows the file exists and isn't a missing-file error.
- **Read truncation.** Reads larger than `tool_token_limit_before_evict` are clipped with a `[Output was truncated due to size limits...]` notice. Hint the agent to use `grep` / `glob` / `jq` for large outputs instead of `read_file`.
- **Auto-offload.** Big tool outputs (above ~20k tokens by default) are written to a file in the virtual FS rather than stuffed into the message stream. This is `FilesystemMiddleware` doing its job; you don't have to opt in.
- **`ls` output.** Directories include a trailing `/` so the model can distinguish them from files.

## Decision tree

```
Need shell execution?
├── Yes → Sandbox backend (Modal / Runloop / Daytona / LangSmith)
│       └── Trusted local-only dev? → LocalShellBackend
└── No
    ├── Files must survive past this thread?
    │   ├── Yes → StoreBackend (or CompositeBackend with /memories/ route)
    │   └── No
    │       ├── Need real disk? → FilesystemBackend(root_dir=..., virtual_mode=True)
    │       └── Otherwise → StateBackend (default)
```
