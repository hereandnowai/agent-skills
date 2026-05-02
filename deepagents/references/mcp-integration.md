# MCP integration

`deepagents` connects to MCP (Model Context Protocol) servers via the `langchain-mcp-adapters` package. MCP tools are async, so almost always use `async_create_deep_agent` and `agent.ainvoke` / `agent.astream`.

## Install

```bash
pip install langchain-mcp-adapters
```

Plus the MCP servers themselves — these are usually Node.js or Python processes the client launches via stdio, or HTTP endpoints. Common ones used in examples:

```bash
# Node-based servers via npx (no install required, fetched on demand):
#   @modelcontextprotocol/server-filesystem
#   @modelcontextprotocol/server-github
#   @modelcontextprotocol/server-postgres
# Python servers — install whatever package they ship in
```

## Multi-server example

```python
import asyncio
from langchain_mcp_adapters.client import MultiServerMCPClient
from deepagents import async_create_deep_agent

async def main():
    mcp_client = MultiServerMCPClient({
        "filesystem": {
            "command": "npx",
            "args": ["-y", "@modelcontextprotocol/server-filesystem", "/path/to/workspace"],
            "transport": "stdio",
        },
        "github": {
            "command": "npx",
            "args": ["-y", "@modelcontextprotocol/server-github"],
            "env": {"GITHUB_PERSONAL_ACCESS_TOKEN": os.environ["GITHUB_TOKEN"]},
            "transport": "stdio",
        },
        "weather": {
            "url": "http://localhost:8000/mcp",
            "transport": "http",
        },
    })

    mcp_tools = await mcp_client.get_tools()

    agent = async_create_deep_agent(
        model="anthropic:claude-sonnet-4-6",
        tools=mcp_tools,
        system_prompt=(
            "You are a senior engineer. You have read/write access to the workspace, "
            "GitHub access, and a weather API. Plan, execute, summarize."
        ),
    )

    async for chunk in agent.astream(
        {"messages": [{"role": "user", "content": "Open issue #42 and propose a fix."}]},
        stream_mode="values",
    ):
        if "messages" in chunk:
            chunk["messages"][-1].pretty_print()

asyncio.run(main())
```

## Transport types

`MultiServerMCPClient` accepts three transports:

- **`stdio`** (default if `command`/`args` given): client spawns a subprocess and communicates over stdin/stdout. Best for local-only servers (filesystem, git, sqlite).
- **`http`** (also called `streamable-http`): client connects to an HTTP endpoint. Best for remote / shared / network-isolated MCP servers.
- **`sse`**: legacy Server-Sent Events transport; supported but `http` is preferred.

## Filtering tools

By default `get_tools()` returns every tool from every server, which can be a lot. Two common patterns to keep the agent's tool list manageable:

**Per-session** — only connect to one server at a time:

```python
async with mcp_client.session("github") as session:
    github_tools = await session.list_tools()
    # Build a sub-agent dedicated to GitHub work
```

**Manual filtering** — drop tools whose names you don't want:

```python
ALLOWED = {"read_file", "list_directory", "search_files",
           "create_issue", "list_issues", "get_issue"}
mcp_tools = [t for t in await mcp_client.get_tools() if t.name in ALLOWED]
```

## Putting MCP tools on a sub-agent

A clean architecture: the supervisor has lightweight tools (`internet_search`, planning), and a sub-agent owns the MCP toolbelt. Keeps the supervisor's context lean even when the MCP server exposes 30+ tools.

```python
from deepagents import async_create_deep_agent

github_subagent = {
    "name": "github-agent",
    "description": "Use for any GitHub operation — issues, PRs, code, search.",
    "system_prompt": "You are a GitHub specialist. Use the GitHub tools to fulfil requests precisely.",
    "tools": github_tools,                        # filtered MCP tools
    "model": "anthropic:claude-sonnet-4-6",
}

agent = async_create_deep_agent(
    model="anthropic:claude-sonnet-4-6",
    tools=[],                                     # supervisor has no tools of its own — pure router
    subagents=[github_subagent],
    system_prompt="You are a coordinator. Delegate GitHub work to github-agent.",
)
```

## Auth and secrets

For HTTP MCP servers that need auth, pass `headers`:

```python
"servicenow": {
    "url": "https://mcp.servicenow.example/v1",
    "transport": "http",
    "headers": {"Authorization": f"Bearer {os.environ['SN_TOKEN']}"},
},
```

For stdio servers that need env vars (most third-party servers), pass `env`:

```python
"github": {
    "command": "npx",
    "args": ["-y", "@modelcontextprotocol/server-github"],
    "env": {"GITHUB_PERSONAL_ACCESS_TOKEN": os.environ["GITHUB_TOKEN"]},
    "transport": "stdio",
},
```

Never hardcode credentials. Use environment variables and document them in your project's README.

## Lifecycle and cleanup

Stdio servers spawn subprocesses. For short-lived scripts, the OS will reclaim them on exit. For long-running services, manage the lifecycle explicitly:

```python
mcp_client = MultiServerMCPClient({...})
try:
    tools = await mcp_client.get_tools()
    agent = async_create_deep_agent(...)
    ...
finally:
    await mcp_client.close()    # terminates subprocesses gracefully
```

## Common MCP gotchas

1. **Calling `create_deep_agent` (sync) instead of `async_create_deep_agent`** — MCP tools are coroutines; sync invocation may work in some setups but is fragile, prefer the async factory.
2. **Stdio server can't be found** — `npx -y` will fetch on demand but needs network and Node installed; pre-install with `npm i -g @modelcontextprotocol/server-foo` for production.
3. **Tool name collisions across servers** — `langchain-mcp-adapters` namespaces tool names. If two servers both expose `read_file`, you'll see them as e.g. `filesystem__read_file` and `git__read_file`. Verify names from `mcp_tools = await mcp_client.get_tools(); print([t.name for t in mcp_tools])` before writing prompts.
4. **Tool too many** — many MCP servers expose 20+ tools. If your agent gets confused, filter aggressively or move them to a sub-agent.
5. **Filesystem MCP server vs. `deepagents` filesystem tools** — these are independent. The MCP filesystem server hits real disk; the `deepagents` virtual filesystem may be in-state or routed differently. Be explicit in the system prompt about which to use for what (e.g. "use MCP filesystem tools to read the user's source tree; use `write_file` to draft outputs").
