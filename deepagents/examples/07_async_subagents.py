"""
07_async_subagents.py — Long-running remote sub-agent (v0.5+).

Pattern shown:
- AsyncSubAgent points at an Agent-Protocol-compliant remote (typically a
  LangGraph deployment).
- The supervisor gains five fire-and-forget tools: start_async_task,
  check_async_task, update_async_task, cancel_async_task, list_async_tasks.
- The supervisor keeps responding to the user while the remote runs,
  and folds results in when they're ready.

Run:
    export ANTHROPIC_API_KEY=...
    # Set RESEARCH_AGENT_URL to your deployed LangGraph (or omit for in-process).
    python 07_async_subagents.py
"""
import os

from deepagents import AsyncSubAgent, create_deep_agent


SUPERVISOR_PROMPT = """\
You are a coordinator with access to a long-running remote `researcher` sub-agent.

When the user asks a research question:

1. Use `start_async_task` with subagent_type="researcher" to kick off the work.
2. Reply to the user immediately, telling them research is underway and giving the task ID.
3. When the user follows up, call `check_async_task` to see if results are ready.
4. If results are in, summarize them for the user.
5. If the user wants to add scope, use `update_async_task`.
6. If the user changes their mind, use `cancel_async_task`.

Never block waiting for the remote — always respond to the user first, then poll on follow-up turns.
"""


def build_agent():
    return create_deep_agent(
        model="anthropic:claude-sonnet-4-6",
        system_prompt=SUPERVISOR_PROMPT,
        subagents=[
            AsyncSubAgent(
                name="researcher",
                description=(
                    "Long-running deep research. Hand it a topic; it returns a thorough report "
                    "after several minutes. Use for any research that's worth waiting for."
                ),
                # Point at a deployed LangGraph; omit the url to run in-process via ASGI.
                url=os.environ.get("RESEARCH_AGENT_URL", "https://your-research-agent.example/graphs"),
                graph_id="research_agent",
                # headers={"Authorization": f"Bearer {os.environ['LANGSMITH_API_KEY']}"},
            ),
        ],
        name="async-coordinator",
    )


if __name__ == "__main__":
    agent = build_agent()

    # Turn 1 — user asks a research question.
    result = agent.invoke({
        "messages": [{
            "role": "user",
            "content": "Please research the impact of long-context LLMs on retrieval-augmented systems.",
        }],
    })
    print("[turn 1]", result["messages"][-1].content)

    # In a real app you'd persist `messages` across turns (and use a checkpointer with a thread_id).
    # Here we just demonstrate the supervisor checks back when the user follows up.
    result = agent.invoke({
        "messages": result["messages"] + [{
            "role": "user",
            "content": "Any update on that research?",
        }],
    })
    print("[turn 2]", result["messages"][-1].content)
