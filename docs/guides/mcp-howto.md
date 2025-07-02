# Connecting to Cloud MCPs & Building Your Own – Guide

The Model Context Protocol (MCP) gives agents super-powers by exposing external
APIs or local code as **tools** they can call autonomously.  This guide provides
a conceptual overview using two real examples from the codebase:

* **Cloud MCP (Apify)** – the MCP lives on someone else's server; you only need
  a tiny wrapper to give your agents access.
* **Custom MCP (Email)** – you run the server yourself and expose bespoke
  Python functions as tools.

No concrete project is created here – the goal is to understand *how* to wire
MCPs into your agents.

---

## 1  Connecting to a Cloud MCP

The `apify-mcp-server` wrapper (see
`docs/resources/webscrapping-with-apify/mcp_servers/apify_mcp_server.py`) shows
the minimal pattern:

```python
from agents.mcp import MCPServerSse

APIFY_TOKEN = os.getenv("APIFY_TOKEN")

apify_server = MCPServerSse(
    params={
        "url": "https://actors-mcp-server.apify.actor/sse?enableAddingActors=true",
        "headers": {"Authorization": f"Bearer {APIFY_TOKEN}"},
        "timeout": 180,
        "sse_read_timeout": 300,
    },
    cache_tools_list=True,
    name="apify-mcp-server",
)
```

Key points
1. **URL** points to an external SSE endpoint – you don't host anything.
2. **Headers** typically carry an API key/token.
3. **cache_tools_list** = True fetches and caches the list of available tools on
   first use (saves latency).
4. The instance is passive – *no* call to `run_sse_async` required.
5. Agents reference it by name in their `tools` array:
   ```json
   "tools": ["apify-mcp-server"]
   ```

That's it – your agent can now call any Apify actor exposed by the remote MCP.

---

## 2  Building a Custom MCP

`email_sender_mcp_server.py` demonstrates how to bundle arbitrary Python code
into an MCP that runs locally.

Skeleton recipe
```python
from fastmcp import FastMCP
from agents.mcp import MCPServerSse

mcp = FastMCP(name="my-mcp", version="0.1", description="…")

@mcp.tool()
def do_something(arg1: str) -> str:
    # your business logic
    return "done"

PORT = 9002
server = MCPServerSse(
    params={"url": f"http://localhost:{PORT}/sse", "timeout": 8, "sse_read_timeout": 100},
    cache_tools_list=True,
    name="my-mcp",
)

# run the FastMCP ASGI app via the helper
import asyncio
loop = asyncio.get_event_loop()
loop.create_task(mcp.run_sse_async(host="127.0.0.1", port=PORT))
```

Why two objects?
* `FastMCP` – collects and documents your **tools** (functions).
* `MCPServerSse` – lightweight SSE **client proxy** that agents talk to.  In the
  same process this is cheap; you could also host the ASGI app elsewhere and
  point the proxy to it via URL.

Linking the MCP to an agent is identical to the cloud case – list its `name` in
`tools`.

```json
"tools": ["my-mcp"]
```

Return values are up to you – strings, JSON-serialisable dicts, or binary blobs
(encoded).  Just document them in the tool's docstring.

---

## 3  Choosing Between Cloud & Custom

| Aspect             | Cloud MCP (Apify)              | Custom MCP (Email)                 |
|--------------------|--------------------------------|------------------------------------|
| Hosting            | 3rd-party                      | You                                |
| Latency            | Network round-trip             | Local / LAN                        |
| Security           | Depends on provider            | Full control                       |
| Tool flexibility   | Limited to provider's API      | Anything Python can do             |
| Maintenance        | None                           | You own uptime & scaling           |

Often a hybrid approach works best: connect to SaaS MCPs for commoditised tasks
( e.g. scraping ) and run sensitive or experimental logic in your own MCP.

---

## 4  Adding a New MCP to Your Project

1. **Decide** cloud vs. self-hosted.
2. **Implement** the wrapper script (one of the patterns above).
3. **Add** the MCP script to `mcp_servers/` so `mcp_servers_loader.py` finds it
   automatically on startup.
4. **Reference** the MCP's `name` in `agents_config/<YourAgent>/config.json`.
5. **(Custom only)** remember to run the server process in the background when
   deploying.

That's all – your agents will automatically discover and call the new tools. 🎉 