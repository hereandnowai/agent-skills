# Production considerations

This file collects the things that matter once you move past a notebook: cost, observability, security, deployment, and resilience.

## Tracing with LangSmith

Set two environment variables:

```bash
export LANGSMITH_TRACING=true
export LANGSMITH_API_KEY=lsv2_pt_...
```

Then pass `name=` to every agent so traces are readable:

```python
agent = create_deep_agent(
    model="anthropic:claude-sonnet-4-6",
    name="research-supervisor",
    subagents=[{
        "name": "research-agent",   # also surfaces as lc_agent_name
        ...
    }],
)
```

In the LangSmith UI, every agent's runs and every sub-agent's runs are nested under the parent. Tool calls show args and results. Sub-agents are tagged with their `name`.

## Token cost — what drives it

`deepagents` is more token-hungry than a raw `create_agent` because of the planning + filesystem + sub-agent toolset. The primary drivers, in order:

1. **The standard system prompt.** Hundreds of tokens explaining tool use. Always present.
2. **Tool schemas.** Each tool's name, description, and JSON schema is in context every turn. Sub-agents inflate this — each registered sub-agent contributes a `task` tool variant.
3. **Sub-agent calls.** Each `task` invocation spins up a fresh model call sequence in the sub-agent. The per-call overhead is modest, but parallel sub-agents multiply quickly.
4. **Long conversations.** Until the auto-summarization threshold trips, every prior message rides every turn.

What you can do:

- **Anthropic prompt caching** is auto-enabled — leave it on. It dramatically reduces cost on long Anthropic conversations.
- **Pick a smaller model for sub-agents.** Supervisor on Sonnet, sub-agent on Haiku for bulk extraction. Set `model=` on the `SubAgent` dict.
- **Filter MCP tools aggressively** before passing them. 30+ tools = bloated schema list every turn.
- **Use `RateLimitMiddleware`** to cap throughput when you'd otherwise hit provider limits.
- **Use `compact_conversation`.** `create_summarization_tool_middleware` adds a tool the agent can call to summarise itself between tasks rather than waiting for the auto threshold.
- **Move heavy artefacts to files.** If a tool returns a 50KB blob, the auto-offload writes it to a file and gives the model a short reference; relying on this is fine.
- **Cap max_tokens on the model.** Long unstructured replies cost on output-token rates that are usually higher than input.

## Resilience

LangChain chat models retry up to 6 times by default with exponential backoff for network errors, 429s, and 5xx. For unreliable networks or aggressive rate-limit regimes, bump it:

```python
from langchain.chat_models import init_chat_model

agent = create_deep_agent(
    model=init_chat_model("anthropic:claude-sonnet-4-6", max_retries=15, timeout=180),
    name="my-agent",
    checkpointer=AsyncPostgresSaver(...),
)
```

Pair with a checkpointer so a transient failure doesn't lose state — the next invocation resumes from the last checkpoint.

## Security model

The `deepagents` README is explicit: it follows a "trust the LLM" model. **The agent can do anything its tools allow.** Boundaries must be enforced at the tool/sandbox level; expecting the model to self-police is unsafe.

The four levers you have:

1. **Sandbox `execute`.** Never use `LocalShellBackend` in production. Use `ModalSandbox` / `RunloopSandbox` / `DaytonaSandbox` / `LangSmithSandbox` so shell commands run in an isolated VM that you can throw away.
2. **Gate sensitive tools with `interrupt_on`.** Anything destructive or external (`delete_file`, `send_email`, `make_payment`, `execute`) should require human approval.
3. **Filesystem `permissions=` rules.** Restrict where the agent can read or write — e.g. deny `/.env*`, deny `/.git/**`, allow `/**`. First match wins, default permissive, so order rules from most-specific-deny to broad-allow.
4. **Tool-level auth.** When a tool calls an external API, pass scoped credentials. Don't share the same admin token across read-only and write-capable tools.

Additional hardening:

- **Don't trust user input as a system prompt.** Prompt injection is real; user content goes in the user message, not the system prompt.
- **Rotate credentials regularly** — long-lived agents that touch secrets should pick them up from a secret manager rather than env vars baked at start.
- **Log every interrupt decision** for audit. The `interrupt_on` flow goes through a checkpointer, but you should also persist a separate audit trail for compliance.

## Concurrency

Sub-agents and parallel tool calls run concurrently. **Never mutate `self` in a custom middleware** — race conditions are silent and intermittent. Always update graph state via the return dict pattern (see `references/middleware.md`).

For per-thread-safe state, use the LangGraph `Annotated[..., reducer]` pattern. For per-tenant isolation in `StoreBackend`, set `namespace=lambda ctx: (ctx.runtime.context.user_id,)` so two users can never see each other's files.

## Deployment targets

Because `create_deep_agent` returns a compiled LangGraph graph, every LangGraph deployment target works with no adapter code:

- **LangSmith Deployment** (formerly LangGraph Platform). The platform provisions checkpointer and store; omit them. `langgraph dev` for local dev, `langgraph build` to deploy.
- **Self-hosted FastAPI.** Wrap `agent.ainvoke` / `agent.astream` in your own routes. Bring your own checkpointer (Postgres / SQLite / Redis).
- **AWS Bedrock AgentCore.** Recent guides show `deepagents` running under AgentCore — see the LangChain blog "Deep Agents on Bedrock".
- **Modal / Cloud Run / Lambda.** Standard Python ASGI hosting; just be aware of cold-start cost when loading skill files.

## File / runtime layout for a real app

The structure below is what most production apps end up with — borrow it:

```
my_agent/
├── agent.py             # build_agent() factory, returns the compiled graph
├── tools/               # custom @tool functions, one module per domain
│   ├── search.py
│   ├── github.py
│   └── data.py
├── subagents/           # SubAgent dicts as builder functions
│   ├── researcher.py
│   └── reviewer.py
├── prompts/             # system_prompt strings (txt/md), kept out of code
│   └── supervisor.md
├── skills/              # SKILL.md files mounted via skills=["/skills/"]
│   └── write-changelog/
│       └── SKILL.md
├── AGENTS.md            # mounted via memory=["/AGENTS.md"]
├── tests/
│   └── test_agent.py    # use a fake checkpointer + canned tool returns
├── main.py              # FastAPI / langgraph dev entrypoint
└── pyproject.toml
```

Two practical rules from this layout:

1. **One `build_agent()` factory.** All construction logic lives there. Tests, notebooks, and the main entrypoint all call it. No ad-hoc `create_deep_agent(...)` scattered around.
2. **Prompts in files.** Markdown files loaded with `pathlib.Path(...).read_text()`. Easier to diff, review, and (eventually) version.

## Testing

Three layers:

1. **Tool unit tests.** Plain Python — call the tool function directly. The hardest bugs hide here, not in the agent loop.
2. **Sub-agent integration tests.** Build the `SubAgent` dict, call its model with a fixed prompt, assert on the output. Use a fake or recorded model client to avoid burning tokens in CI.
3. **End-to-end smoke tests.** A handful of canonical user prompts × `agent.invoke(...)`, asserting on shape (last message non-empty, no errors, expected files written). Use LangSmith's eval framework or a snapshot tester.

Always test with a `MemorySaver` checkpointer in CI — flushes out HITL bugs and "thread_id missing" mistakes early.

## Operational checklist before shipping

- [ ] `model=` is pinned (not relying on the harness default).
- [ ] `name=` is set on every `create_deep_agent` and every sub-agent.
- [ ] LangSmith tracing is on (`LANGSMITH_TRACING=true`, `LANGSMITH_API_KEY` set).
- [ ] Checkpointer is persistent (Postgres/SQLite/Redis) — not `MemorySaver`.
- [ ] If `interrupt_on={...}` is used, the checkpointer is wired and the resume flow is tested.
- [ ] Shell access only via a real sandbox backend; no `LocalShellBackend` in prod.
- [ ] Filesystem `permissions=` rules deny secrets, `.git`, etc.
- [ ] MCP credentials come from env / secret manager, never hardcoded.
- [ ] `max_retries` raised, `timeout` set on the model.
- [ ] `RateLimitMiddleware` configured to provider quotas.
- [ ] Audit log of HITL approvals lives outside the agent's checkpointer.
- [ ] Cost dashboards (LangSmith + provider) wired up before the agent is exposed to traffic.
