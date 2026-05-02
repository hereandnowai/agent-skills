"""
04_hitl_with_checkpointer.py — Human-in-the-loop with explicit decisions.

Demonstrates:
- interrupt_on for `delete_file` (approve / edit / reject) and `send_email`
  (approve / reject only — no edit).
- The mandatory pairing of `interrupt_on` with a checkpointer.
- Resuming with one decision per pending interrupt, in the order LangGraph
  reports them.
- Editing tool args via `Command(resume=[{"type": "edit", "args": {...}}])`.

Run:
    export ANTHROPIC_API_KEY=...
    python 04_hitl_with_checkpointer.py
"""
from deepagents import create_deep_agent
from langchain.tools import tool
from langgraph.checkpoint.memory import MemorySaver
from langgraph.types import Command


@tool
def delete_file(path: str) -> str:
    """Delete a file from the filesystem (mock — pretends to delete)."""
    return f"Deleted {path}"


@tool
def send_email(to: str, subject: str, body: str) -> str:
    """Send an email (mock — pretends to send)."""
    return f"Sent email to {to} (subject: {subject})"


def build_agent(checkpointer):
    return create_deep_agent(
        model="anthropic:claude-sonnet-4-6",
        tools=[delete_file, send_email],
        system_prompt=(
            "You are an ops assistant. You can delete files and send emails. "
            "Be precise and explain what you intend to do before doing it."
        ),
        interrupt_on={
            "delete_file": True,                                          # all decisions
            "send_email":  {"allowed_decisions": ["approve", "reject"]},  # no edit
        },
        checkpointer=checkpointer,    # required — without this, no interrupts fire
        name="ops-agent",
    )


def display_interrupts(interrupts):
    print(f"\n{'='*60}\n{len(interrupts)} interrupt(s) pending — please decide\n{'='*60}")
    for i, intr in enumerate(interrupts):
        print(f"\n[{i}]")
        print(intr)


if __name__ == "__main__":
    checkpointer = MemorySaver()
    agent = build_agent(checkpointer)
    config = {"configurable": {"thread_id": "ops-session-1"}}

    # Initial run.
    result = agent.invoke(
        {"messages": [{
            "role": "user",
            "content": "Delete /tmp/old.log and email finance@acme.com about the cleanup.",
        }]},
        config=config,
    )

    # Loop until the agent runs out of interrupts.
    while True:
        interrupts = result.get("__interrupt__") or result.get("interrupts") or []
        if not interrupts:
            break
        display_interrupts(interrupts)

        # In a real app, prompt the user. Here we hardcode:
        # - approve the delete as proposed
        # - edit the email so it goes to ops@ instead, then approve
        decisions = []
        for intr in interrupts:
            tool_name = getattr(intr, "value", {}).get("name") if hasattr(intr, "value") else None
            if tool_name == "send_email":
                decisions.append({
                    "type": "edit",
                    "args": {
                        "to": "ops@acme.com",
                        "subject": "Cleanup completed",
                        "body": "Removed /tmp/old.log per scheduled rotation.",
                    },
                })
            else:
                decisions.append({"type": "approve"})

        result = agent.invoke(Command(resume=decisions), config=config)

    print("\n=== FINAL ===")
    print(result["messages"][-1].content)
