"""
03_coding_agent_with_sandbox.py — Coding agent with a Modal sandbox + HITL.

Patterns shown:
- ModalSandbox backend → real `execute` tool runs in an isolated VM.
- interrupt_on gates destructive filesystem writes for human approval.
- MemorySaver checkpointer is required for HITL (without it, interrupts are no-ops).

Replace ModalSandbox with RunloopSandbox / DaytonaSandbox / LangSmithSandbox if you
prefer a different provider — the rest of the file is identical.

Run:
    export ANTHROPIC_API_KEY=...
    pip install deepagents langchain-modal modal
    modal token new                          # one-time auth
    python 03_coding_agent_with_sandbox.py
"""
import modal
from deepagents import create_deep_agent
from langchain_anthropic import ChatAnthropic
from langchain_modal import ModalSandbox
from langgraph.checkpoint.memory import MemorySaver
from langgraph.types import Command


SUPERVISOR_PROMPT = """\
You are an expert Python engineer. Your workspace lives at / inside a sandboxed VM.

Workflow:
1. Use `write_todos` to plan the work before any code.
2. Use `glob`/`grep` to scout the workspace before reading large files.
3. Use `write_file` and `edit_file` to create or modify code.
4. Use `execute` to run pytest / pip / linting in the sandbox.
5. When you finish a task, summarize what you did and which tests pass.

Conventions:
- Python 3.11+. Type hints on every public function.
- Tests in tests/, fixtures in tests/fixtures/.
- Keep changes minimal and focused.
"""


def build_agent(checkpointer):
    """Build the coding agent with a fresh Modal sandbox.

    Returns (agent, sandbox). Caller is responsible for sandbox.terminate().
    """
    app = modal.App.lookup("deepagents-coder", create_if_missing=True)
    sandbox = modal.Sandbox.create(app=app)
    backend = ModalSandbox(sandbox=sandbox)

    agent = create_deep_agent(
        model=ChatAnthropic(model="claude-sonnet-4-6", max_retries=10, timeout=180),
        backend=backend,
        system_prompt=SUPERVISOR_PROMPT,
        # Gate destructive operations behind human approval.
        interrupt_on={
            "write_file": True,
            "edit_file":  True,
            "execute":    {"allowed_decisions": ["approve", "reject"]},  # no edit on shell
            # safe ops left untouched:
            "read_file":  False,
            "ls":         False,
            "grep":       False,
            "glob":       False,
        },
        checkpointer=checkpointer,    # required for HITL
        name="coding-agent",
    )
    return agent, sandbox


if __name__ == "__main__":
    checkpointer = MemorySaver()
    agent, sandbox = build_agent(checkpointer)
    config = {"configurable": {"thread_id": "code-session-1"}}

    try:
        # Initial run — will pause when the agent wants to write or execute.
        result = agent.invoke(
            {"messages": [{
                "role": "user",
                "content": "Create a Python package `greetings` with a `hello(name)` function and a passing pytest.",
            }]},
            config=config,
        )

        # Approval loop — keep resuming until the agent finishes.
        while result.get("__interrupt__") or result.get("interrupts"):
            interrupts = result.get("__interrupt__") or result.get("interrupts") or []
            print(f"\n--- {len(interrupts)} pending interrupt(s) ---")
            for i, intr in enumerate(interrupts):
                print(f"[{i}] {intr}")
            decisions = [{"type": "approve"} for _ in interrupts]
            print(f"Auto-approving all (replace with real prompt in production).")
            result = agent.invoke(Command(resume=decisions), config=config)

        print("=== FINAL ===")
        print(result["messages"][-1].content)
    finally:
        sandbox.terminate()
