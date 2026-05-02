"""
06_structured_output.py — Force a typed final answer via response_format.

Patterns shown:
- Pydantic model passed as response_format.
- Reading the typed result from result["structured_response"].
- Same pattern on a sub-agent so the supervisor receives clean structured data
  rather than free-form prose.

Run:
    export ANTHROPIC_API_KEY=...
    export TAVILY_API_KEY=...
    pip install deepagents tavily-python pydantic
    python 06_structured_output.py
"""
from typing import Literal

from deepagents import create_deep_agent
from langchain.tools import tool
from pydantic import BaseModel, Field
from tavily import TavilyClient


_tavily = TavilyClient()


@tool
def internet_search(query: str, max_results: int = 5) -> dict:
    """Search the internet."""
    return _tavily.search(query=query, max_results=max_results)


# --- Top-level structured response: company brief -----------------------------

class CompanyBrief(BaseModel):
    """A concise structured brief about a company."""
    name: str = Field(description="The official company name.")
    industry: str = Field(description="Primary industry (e.g. 'cloud infrastructure').")
    founded_year: int | None = Field(description="Year founded, if known.")
    headquarters: str | None = Field(description="HQ city/country, if known.")
    one_line_pitch: str = Field(description="A single-sentence description of what the company does.")
    key_products: list[str] = Field(description="3-5 main products or services.")
    notable_recent_news: list[str] = Field(description="2-4 noteworthy items from the past 12 months.")


# --- Sub-agent structured response: per-source finding ------------------------

class SourceFinding(BaseModel):
    """A single fact backed by a source URL."""
    fact: str = Field(description="The fact, in one tight sentence.")
    source_url: str = Field(description="URL where this fact was found.")
    confidence: Literal["high", "medium", "low"]


class ResearchFindings(BaseModel):
    """Aggregated findings from a focused research subtask."""
    findings: list[SourceFinding] = Field(description="3-7 individual findings.")


def build_agent():
    research_subagent = {
        "name": "research-agent",
        "description": "Use for focused web research. Returns structured findings.",
        "system_prompt": (
            "Research the question using internet_search. Return ResearchFindings — "
            "each finding must cite the URL it came from. Be ruthless about relevance."
        ),
        "tools": [internet_search],
        "model": "anthropic:claude-sonnet-4-6",
        "response_format": ResearchFindings,
    }

    return create_deep_agent(
        model="anthropic:claude-sonnet-4-6",
        tools=[internet_search],
        system_prompt=(
            "You are a research lead. Plan with write_todos, delegate research subtopics "
            "to the research-agent sub-agent, then assemble a CompanyBrief as your final answer."
        ),
        subagents=[research_subagent],
        response_format=CompanyBrief,
        name="company-brief-agent",
    )


if __name__ == "__main__":
    agent = build_agent()
    result = agent.invoke({
        "messages": [{"role": "user", "content": "Write a brief on Anthropic."}],
    })

    brief = result["structured_response"]
    assert isinstance(brief, CompanyBrief)

    print(f"Company: {brief.name}")
    print(f"Industry: {brief.industry}")
    print(f"Founded:  {brief.founded_year}")
    print(f"HQ:       {brief.headquarters}")
    print(f"\nPitch: {brief.one_line_pitch}")
    print(f"\nProducts:")
    for p in brief.key_products:
        print(f"  - {p}")
    print(f"\nRecent news:")
    for n in brief.notable_recent_news:
        print(f"  - {n}")
