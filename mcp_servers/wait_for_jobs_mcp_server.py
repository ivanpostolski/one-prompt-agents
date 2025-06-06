"""
This module provides an MCP (Multi-Context Platform) server that acts as a
proxy for the 'wait_for_jobs' tool from the main MCP server.

It connects to the central `one-prompt-agent-mcp` server, discovers the
`wait_for_jobs` tool, and re-exposes it on its own MCP endpoint. This allows
agents to be granted access to job waiting functionality without giving them
access to all the tools on the main MCP server.
"""

import asyncio
import logging
import os
from types import MethodType
from fastmcp import FastMCP
from agents.mcp import MCPServerSse

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

# --- Configuration ---
PROXY_PORT = os.getenv("WAIT_FOR_JOBS_MCP_PORT", 9003)
MAIN_MCP_PORT = os.getenv("MAIN_MCP_PORT", 22222)

# --- MCP Client for Main Server ---
# This client connects to the central 'one-prompt-agent-mcp' to call the real tool.
one_prompt_agent_mcp = MCPServerSse(
    params={
        "url": f"http://127.0.0.1:{MAIN_MCP_PORT}/sse",
        "timeout": 8,
        "sse_read_timeout": 100,
    },
    cache_tools_list=True,
    client_session_timeout_seconds=120,
    name="one-prompt-agent-mcp-client-for-wait", # Unique name for this client instance
)

# --- MCP Server for this Proxy ---
# This is the actual server that agents will connect to.
wait_for_jobs_proxy_server = MCPServerSse(
    params={
        "url": f"http://127.0.0.1:{PROXY_PORT}/sse",
        "timeout": 8,
        "sse_read_timeout": 100,
    },
    cache_tools_list=True,
    client_session_timeout_seconds=120,
    name="wait_for_jobs_mcp_proxy", # The public name for this proxy server
)

# --- Connection Wrapper ---
# Ensures the client to the main MCP is connected before this proxy server accepts connections.
_original_connect = wait_for_jobs_proxy_server.connect
async def _wrapped_connect(self, *args, **kwargs):
    logger.info("Connecting to main MCP server before starting proxy...")
    await one_prompt_agent_mcp.connect()
    logger.info("Connection to main MCP successful. Starting proxy server connection...")
    result = await _original_connect(*args, **kwargs)
    return result
wait_for_jobs_proxy_server.connect = MethodType(_wrapped_connect, wait_for_jobs_proxy_server)

# --- FastMCP Instance for this Proxy ---
mcp = FastMCP(
    name="wait_for_jobs_mcp_proxy",
    version="0.1.0",
    description="This MCP exposes the system-level 'wait_for_jobs' tool.",
)

@mcp.tool()
def wait_for_jobs(your_job_id: str, job_ids_to_wait_for: list):
    """
    Pauses the calling agent's job and waits for a list of other jobs to complete.
    This is a proxy tool that calls the main system's 'wait_for_jobs' function.
    """
    try:
        logger.info(f"Proxying 'wait_for_jobs' call for job {your_job_id}, waiting for {job_ids_to_wait_for}")
        return one_prompt_agent_mcp.call_tool(
            "wait_for_jobs",
            {"your_job_id": your_job_id, "job_ids_to_wait_for": job_ids_to_wait_for},
        )
    except Exception as e:
        logger.error(f"Error proxying 'wait_for_jobs' call: {e}", exc_info=True)
        return {"error": str(e)}

def main():
    """Main function to run the proxy server."""
    loop = asyncio.get_event_loop()
    task = loop.create_task(
        mcp.run_sse_async(
            host='127.0.0.1',
            port=PROXY_PORT,
            log_level='debug'
        )
    )
    logger.info(f"Wait for Jobs MCP Proxy Server starting on http://127.0.0.1:{PROXY_PORT}")
    return task

# This allows running the server directly via 'python -m mcp_servers.wait_for_jobs_mcp_server'
if __name__ == '__main__':
    main_task = main()
    loop = asyncio.get_event_loop()
    loop.run_forever() 