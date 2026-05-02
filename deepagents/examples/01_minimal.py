"""
01_minimal.py — The smallest possible deep agent.

One custom tool, no sub-agents, no checkpointer. The harness still gives the
model planning + virtual filesystem + general-purpose sub-agent for free.

Run:
    export ANTHROPIC_API_KEY=...
    python 01_minimal.py
"""
from deepagents import create_deep_agent


def get_weather(city: str) -> str:
    """Get the current weather in a city."""
    return f"It's always sunny in {city}!"


def build_agent():
    return create_deep_agent(
        model="anthropic:claude-sonnet-4-6",
        tools=[get_weather],
        system_prompt="You are a friendly weather assistant. Be concise.",
        name="weather-agent",
    )


if __name__ == "__main__":
    agent = build_agent()
    result = agent.invoke({
        "messages": [{"role": "user", "content": "What's the weather in San Francisco?"}],
    })
    print(result["messages"][-1].content)
