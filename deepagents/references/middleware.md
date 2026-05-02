# Middleware

Middleware is how `deepagents` composes capabilities. The standard stack runs in this order, every time:

1. **`TodoListMiddleware`** — adds `write_todos` / `read_todos`, plus prompt instructions explaining when to use them.
2. **`FilesystemMiddleware`** — adds `ls` / `read_file` / `write_file` / `edit_file` / `glob` / `grep`, and `execute` if the backend is a sandbox. Also handles auto-offloading of large tool outputs.
3. **`SubAgentMiddleware`** — adds the `task` tool and dispatches to declarative `SubAgent` and `CompiledSubAgent` specs. (`AsyncSubAgentMiddleware` is added in addition when any `AsyncSubAgent` is in the list.)
4. **`SummarizationMiddleware`** — auto-compacts older messages once the conversation exceeds a model-aware threshold (computed via `compute_summarization_defaults`).
5. **`AnthropicPromptCachingMiddleware`** — enabled when on an Anthropic model; turns on Anthropic's prompt caching for substantial cost savings on long conversations.
6. **`PatchToolCallsMiddleware`** — fixes dangling/cancelled tool calls in history (rare but real failure mode that wedges agents).

Conditionally added based on parameters:

| Added when | Middleware | Effect |
|---|---|---|
| `memory=[...]` | `MemoryMiddleware` | Loads `AGENTS.md` files into the system prompt at startup |
| `skills=[...]` | `SkillsMiddleware` | Progressive disclosure of skill metadata + `SKILL.md` reading |
| `interrupt_on={...}` | `HumanInTheLoopMiddleware` | Pauses on listed tool calls, awaits a `Command(resume=...)` |
| `permissions=[...]` | `_PermissionMiddleware` | Filesystem ACL; appended last so it sees all tool calls |

Custom middleware you pass via `middleware=[...]` is inserted **after** the standard stack but **before** the tail (`AnthropicPromptCachingMiddleware`, `PatchToolCallsMiddleware`). Order matters because middleware can wrap one another's tool calls.

## Why the order matters (a worked example)

If you add a `RateLimitMiddleware` and a `HumanInTheLoopMiddleware`, you almost always want this order:

```
... standard stack ...
→ RateLimitMiddleware       # wait for a token before doing anything else
→ HumanInTheLoopMiddleware  # then pause for approval
→ AnthropicPromptCachingMiddleware
→ PatchToolCallsMiddleware
```

If HITL ran before rate limiting, the user might approve a call only to have it stalled minutes later by rate-limit waiting. If caching ran before HITL, you'd cache the pre-approval prompt rather than the post-approval one. Always think through "what wraps what" when adding middleware.

## Custom middleware (the simple case)

For most ad-hoc needs, the `wrap_tool_call` decorator is enough:

```python
from langchain.tools import tool
from langchain.agents.middleware import wrap_tool_call
from deepagents import create_deep_agent

@tool
def get_weather(city: str) -> str:
    """Get the weather in a city."""
    return f"The weather in {city} is sunny."

call_count = [0]   # use a list, not a closure variable, to allow mutation

@wrap_tool_call
def log_tool_calls(request, handler):
    call_count[0] += 1
    print(f"[middleware] #{call_count[0]} {request.name}({request.args})")
    response = handler(request)
    print(f"[middleware] -> {str(response)[:200]}")
    return response

agent = create_deep_agent(
    model="anthropic:claude-sonnet-4-6",
    tools=[get_weather],
    middleware=[log_tool_calls],
)
```

Use `wrap_tool_call` for: logging, metrics, retries, redaction, request/response transformation.

## Custom middleware (class-based)

For middleware that hooks into the agent loop more broadly, subclass `AgentMiddleware`:

```python
from langchain.agents.middleware import AgentMiddleware

class TurnCounterMiddleware(AgentMiddleware):
    def before_agent(self, state, runtime):
        # Returning a dict updates the graph state.
        return {"turn_count": state.get("turn_count", 0) + 1}

    def after_agent(self, state, runtime):
        print(f"Turn complete: {state.get('turn_count')}")
        return None
```

**Critical concurrency rule:** never mutate `self` from inside hooks. Sub-agents and parallel tool calls run concurrently — `self` will be shared and you'll get races. Always update graph state by returning a dict.

```python
# ❌ wrong
class BadMiddleware(AgentMiddleware):
    def __init__(self):
        self.x = 0
    def before_agent(self, state, runtime):
        self.x += 1   # race condition under parallel sub-agents

# ✅ correct
class GoodMiddleware(AgentMiddleware):
    def before_agent(self, state, runtime):
        return {"x": state.get("x", 0) + 1}
```

Available hooks (in execution order): `before_agent` → `wrap_tool_call` (per tool) → `after_agent`. Provider-specific middleware can also intercept the model call itself (`wrap_model_call`) for things like prompt caching.

## Pre-built middleware worth knowing

These come from `langchain` itself, not from `deepagents`, but stack cleanly with the harness:

- **`SummarizationMiddleware`** — `deepagents` already includes one, but you can replace it with `create_summarization_middleware(...)` if you want different thresholds. The companion `create_summarization_tool_middleware` exposes a `compact_conversation` tool the agent can call manually between tasks rather than waiting for the auto threshold.
- **`AnthropicPromptCachingMiddleware`** — already auto-included on Anthropic models. Don't add it twice.
- **`RateLimitMiddleware`** — manual rate limiting in front of the model.
- **PII detection / redaction middleware** — see LangChain's "prebuilt middleware" docs for the current list (the catalog grows).
- **Retry / fallback middleware** — for resilient model calls.

## When to write custom middleware vs. just a tool

The line is fuzzy but practical:

- **Tool** — when the model decides to call it. Logic the model should reason about.
- **Middleware** — when *you* decide to run it on every turn or every tool call. Logic the model shouldn't even know about (logging, redaction, rate limiting, audit trails, structured-output validation).

If the model needs to know "this thing exists," it's a tool. If you want the thing to happen no matter what the model does, it's middleware.

## Adding state fields via middleware

Middleware can declare new state fields by setting `state_schema` on the class. This is how `FilesystemMiddleware` adds `files`, `TodoListMiddleware` adds `todos`, etc. For custom state:

```python
from typing import TypedDict, Annotated
from operator import add

class CallLogState(TypedDict, total=False):
    call_log: Annotated[list[str], add]   # `add` is the reducer; new entries are appended

class CallLoggerMiddleware(AgentMiddleware):
    state_schema = CallLogState

    def before_agent(self, state, runtime):
        return {"call_log": [f"Started turn at {now_iso()}"]}
```

The `Annotated[..., reducer]` pattern is standard LangGraph — without a reducer, two parallel updates to the same key would conflict.
