"""
05_mcp_integration.py — Loading MCP server tools into a deep agent.

Patterns shown:
- MultiServerMCPClient with two stdio servers and one HTTP server.
- async_create_deep_agent (MCP tools are async, so the async factory is required).
- Passing MCP tools directly as the agent's toolbelt.
- Streaming with subgraphs=True so sub-agent tool calls appear in the stream.

Run:
    export ANTHROPIC_API_KEY=...
    export GITHUB_TOKEN=...           # if using the GitHub MCP server
    pip install deepagents langchain-mcp-adapters
    # MCP servers are fetched on demand via npx; you need Node.js installed.
    python 05_mcp_integration.py
"""
import asyncio
import os

from deepagents import async_create_deep_agent
from langchain_mcp_adapters.client import MultiServerMCPClient


async def main():
    mcp_client = MultiServerMCPClient({
        "filesystem": {
            "command": "npx",
            "args": ["-y", "@modelcontextprotocol/server-filesystem", "/tmp/agent-workspace"],
            "transport": "stdio",
        },
        "github": {
            "command": "npx",
            "args": ["-y", "@modelcontextprotocol/server-github"],
            "env": {"GITHUB_PERSONAL_ACCESS_TOKEN": os.environ.get("GITHUB_TOKEN", "")},
            "transport": "stdio",
        },
        # Example of an HTTP MCP server — comment out if you don't have one running.
        # "weather": {
        #     "url": "http://localhost:8000/mcp",
        #     "transport": "http",
        # },
    })

    try:
        all_tools = await mcp_client.get_tools()
        print(f"Loaded {len(all_tools)} MCP tools:")
        for t in all_tools:
            print(f"  - {t.name}: {t.description[:80] if t.description else ''}")

        agent = async_create_deep_agent(
            model="anthropic:claude-sonnet-4-6",
            tools=all_tools,
            system_prompt=(
                "You are a senior engineer. You have read/write access to the local "
                "workspace at /tmp/agent-workspace and to GitHub. "
                "Plan, execute, summarize."
            ),
            name="mcp-agent",
        )

        async for chunk in agent.astream(
            {"messages": [{
                "role": "user",
                "content": (
                    "Find any open issues in our repo labeled 'good first issue', "
                    "pick one, and write a quick proposal to /tmp/agent-workspace/proposal.md."
                ),
            }]},
            stream_mode="values",
            subgraphs=True,
            version="v2",
        ):
            if "messages" in chunk:
                chunk["messages"][-1].pretty_print()
    finally:
        # Tear down stdio subprocesses cleanly.
        await mcp_client.close()


if __name__ == "__main__":
    asyncio.run(main())
