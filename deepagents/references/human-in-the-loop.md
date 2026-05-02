# Human-in-the-loop (HITL)

`interrupt_on` lets you pause the agent before specific tool calls and require explicit human approval before they execute. It's built on LangGraph's `interrupt()` primitive plus `HumanInTheLoopMiddleware`.

## Two non-negotiable requirements

1. **You must pass a `checkpointer`** — without one, `interrupt_on` is silently a no-op. The checkpointer is what lets the run pause and resume.
2. **You must drive the agent with a `thread_id`** — the same one for the original invocation and the resume. Without a stable thread ID, the resume won't find the paused run.

## Minimal example

```python
from langchain.tools import tool
from deepagents import create_deep_agent
from langgraph.checkpoint.memory import MemorySaver
from langgraph.types import Command

@tool
def delete_file(path: str) -> str:
    """Delete a file from the filesystem."""
    return f"Deleted {path}"

@tool
def send_email(to: str, subject: str, body: str) -> str:
    """Send an email."""
    return f"Sent email to {to}"

checkpointer = MemorySaver()
agent = create_deep_agent(
    model="anthropic:claude-sonnet-4-6",
    tools=[delete_file, send_email],
    interrupt_on={
        "delete_file": True,                                          # all decision types allowed
        "read_file":   False,                                         # never interrupt
        "send_email":  {"allowed_decisions": ["approve", "reject"]},  # no edit
    },
    checkpointer=checkpointer,    # required
)

config = {"configurable": {"thread_id": "user-42"}}

# 1) Initial run — will pause if the agent decides to call delete_file or send_email.
result = agent.invoke(
    {"messages": [{"role": "user", "content": "Delete /tmp/old.log and email finance@acme.com about it."}]},
    config=config,
)

# 2) Inspect the interrupt(s) — `result` includes pending interrupts when paused.
#    LangGraph batches interrupts: if multiple tools want to fire in one turn,
#    you'll get them all and must respond to each, in order.

# 3) Resume with one decision per pending interrupt.
result = agent.invoke(
    Command(resume=[
        {"type": "approve"},                                       # approve delete_file as proposed
        {"type": "edit", "args": {"to": "ops@acme.com",            # edit and run send_email
                                  "subject": "Cleanup",
                                  "body": "Removed /tmp/old.log."}},
    ]),
    config=config,
)
```

## Decision types

`InterruptOnConfig` allows three decision types out of the box:

| Decision | What happens |
|---|---|
| `approve` | The tool runs with the proposed args, unchanged. |
| `edit` | The tool runs with edited args (provided in the resume). |
| `reject` | The tool is **not** run; the agent sees a tool message saying it was rejected. |

Shorthand:
- `interrupt_on={"send_email": True}` — all three decisions allowed.
- `interrupt_on={"send_email": False}` — never interrupt (same as omitting it; useful when you're toggling rules dynamically).
- `interrupt_on={"send_email": {"allowed_decisions": ["approve", "reject"]}}` — restrict the decision menu.

A future `respond` decision type is being discussed (let the human reply directly without running the tool); not yet shipped.

## Multiple interrupts in one turn

If the agent emits multiple tool calls in a single step and **more than one** is on the interrupt list, LangGraph batches all of them. You'll receive a list of pending interrupts and must respond with a list of decisions in the same order:

```python
result = agent.invoke(
    Command(resume=[
        {"type": "approve"},
        {"type": "reject"},
        {"type": "edit", "args": {...}},
    ]),
    config=config,
)
```

If you mismatch the count, LangGraph raises.

## Inheritance into sub-agents

| Sub-agent type | Inherits parent's `interrupt_on`? |
|---|---|
| Declarative `SubAgent` dict | **Yes**, unless the dict has its own `interrupt_on` (which fully overrides). |
| `CompiledSubAgent` | **No.** Configure HITL inside the wrapped graph. |
| `AsyncSubAgent` | **No.** Configure HITL on the remote endpoint. |

That asymmetry is on purpose: declarative sub-agents are part of the same logical graph, so the supervisor's policy applies. Compiled and async sub-agents are independent runnables — their authors decide their own approval rules.

## Choosing what to gate

Reasonable defaults for an autonomous agent:

```python
interrupt_on = {
    # Destructive or irreversible:
    "delete_file":  True,
    "edit_file":    True,
    "write_file":   True,
    "execute":      True,        # any shell command
    # External side effects:
    "send_email":   {"allowed_decisions": ["approve", "reject"]},
    "create_jira":  True,
    "make_payment": True,
    # Cheap and safe — leave alone:
    "read_file":    False,
    "ls":           False,
    "grep":         False,
    "internet_search": False,
}
```

Two heuristics:
1. **Reversibility.** If the tool's effect is irreversible, gate it.
2. **Externality.** If the tool talks to the outside world (email, payment, third-party API), gate it.

For research/QA agents you often need none of these. For coding agents touching real files, gate `write_file` / `edit_file` / `execute`. For ops agents, gate everything that mutates production.

## Production checkpointer

For real apps, swap `MemorySaver` for a persistent checkpointer:

```python
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver

async with AsyncPostgresSaver.from_conn_string(POSTGRES_URL) as checkpointer:
    await checkpointer.setup()
    agent = create_deep_agent(
        model="anthropic:claude-sonnet-4-6",
        tools=[...],
        interrupt_on={"write_file": True},
        checkpointer=checkpointer,
    )
    ...
```

Other persistent checkpointers: `AsyncSqliteSaver` (single-host), Redis (via langgraph-checkpoint-redis). On LangSmith Deployment, the platform provisions one — you don't pass anything.

## Driving HITL from a UI

The full pattern in a web app:

1. POST `/runs` with the user's message → backend calls `agent.invoke(...)` → returns either a final answer or a list of pending interrupts (because the agent paused).
2. Front-end renders the interrupt(s): "Agent wants to call `delete_file('/tmp/old.log')`. Approve, edit args, or reject?"
3. POST `/runs/<thread_id>/resume` with `{"decisions": [...]}` → backend calls `agent.invoke(Command(resume=...), config={"configurable": {"thread_id": ...}})` → either finishes or returns more interrupts.

The same pattern works over WebSocket / SSE; LangGraph's `useStream` React hook (see frontend docs) wraps it.

## Common HITL mistakes

1. **Forgetting `checkpointer`.** No interrupt will ever fire.
2. **Different `thread_id` between invoke and resume.** The resume can't find the paused run.
3. **Resuming with the wrong number of decisions.** If three tools were paused, you must send three decisions.
4. **`edit` with malformed args.** The edited args go through the same tool schema validation as a fresh call. Bad args raise.
5. **Trying to gate `task` calls.** Sub-agent dispatch is opaque to the supervisor's `interrupt_on`. Gate the sub-agent's individual tools instead — declarative `SubAgent` specs inherit the parent's rules by default.
6. **Setting `interrupt_on` on `read_file` for "audit" purposes.** That's middleware territory, not HITL — pause-on-read murders agent throughput. Use a logging middleware instead.
