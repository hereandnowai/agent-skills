"""
02_research_agent.py — Supervisor + research sub-agent + Tavily search.

The canonical deepagents pattern. The supervisor plans the work, delegates each
research subtask to the `research-agent` sub-agent (which has its own context
window), and writes the final report. The supervisor's context stays small
because each sub-agent's search noise is discarded after a summary.

Run:
    export ANTHROPIC_API_KEY=...
    export TAVILY_API_KEY=...
    pip install deepagents tavily-python
    python 02_research_agent.py
"""
from deepagents import create_deep_agent
from langchain.tools import tool
from tavily import TavilyClient

_tavily = TavilyClient()


@tool
def internet_search(
    query: str,
    max_results: int = 5,
    topic: str = "general",
) -> dict:
    """Search the internet for information.

    Args:
        query: The search query.
        max_results: Maximum number of results to return (default 5).
        topic: Either 'general' or 'news'.
    """
    return _tavily.search(query=query, max_results=max_results, topic=topic)


SUPERVISOR_PROMPT = """\
You are a senior research lead. Your job is to:

1. Plan the research using `write_todos` — break the question into 3-6 focused subtopics.
2. Delegate each subtopic to the `research-agent` sub-agent via the `task` tool. Hand it
   one precise question at a time. Do NOT do the research yourself directly.
3. As findings come back, save them to /notes/<subtopic>.md using `write_file`.
4. Once all subtopics are covered, write a polished report to /report.md and return it.

Keep the final report tight: clear thesis, citations to sources from the sub-agent's
findings, no filler.
"""

RESEARCH_AGENT_PROMPT = """\
You are an expert researcher. Given a focused question:

1. Run 2-4 internet_search calls with diverse queries.
2. Read the most relevant snippets and identify the 3-5 strongest facts.
3. Return a tight summary: thesis sentence, then bullet points of facts with source URLs.

Be ruthless about relevance. Don't return everything you found — return what answers the question.
"""


def build_agent():
    research_subagent = {
        "name": "research-agent",
        "description": (
            "Use for in-depth research on a single focused topic. "
            "Hand it one precise question at a time, not a multi-part one."
        ),
        "system_prompt": RESEARCH_AGENT_PROMPT,
        "tools": [internet_search],                     # required in 0.4.x
        "model": "anthropic:claude-sonnet-4-6",          # required in 0.4.x
    }

    return create_deep_agent(
        model="anthropic:claude-sonnet-4-6",
        tools=[internet_search],
        system_prompt=SUPERVISOR_PROMPT,
        subagents=[research_subagent],
        name="research-supervisor",
    )


if __name__ == "__main__":
    agent = build_agent()
    result = agent.invoke({
        "messages": [{
            "role": "user",
            "content": "What are the most important advances in long-context LLMs in 2025-2026?",
        }],
    })
    # Print the final user-facing message and any files the agent wrote.
    print("=== FINAL ANSWER ===")
    print(result["messages"][-1].content)
    print("\n=== FILES WRITTEN ===")
    for path, fd in result.get("files", {}).items():
        print(f"\n--- {path} ---\n{fd['content'][:500]}")
