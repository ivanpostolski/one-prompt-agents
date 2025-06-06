"""
This module provides various utility functions and classes supporting chat operations
and agent interactions within the one-prompt-agents framework.

Contents:
- `spinner`: An asynchronous context manager that displays an animated console spinner
  to indicate background activity (e.g., while an agent is processing).
- `CaptureLastAssistant`: A `RunHooks` implementation used to intercept and store
  an agent's messages and log tool initiations. Useful for history tracking or debugging.
- `connect_mcps`: An asynchronous function to handle the connection logic for an agent
  to its associated MCP (Multi-Context Platform) servers, including retries.

These utilities are designed to be general-purpose helpers for different parts of the
chat and agent execution pipeline.
"""
import asyncio
import itertools
import sys
import logging
from contextlib import asynccontextmanager
from agents import RunHooks # Assuming RunHooks is from the 'agents' library
from typing import List, Any # Added Any for agent type hint

logger = logging.getLogger(__name__)

SPINNER_FRAMES = "⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏"

@asynccontextmanager
async def spinner(text: str = ""):
    """An asynchronous context manager that displays an animated spinner in the console.

    Useful for indicating background activity during long-running asynchronous operations.
    The spinner is displayed next to the provided `text`.

    Args:
        text (str, optional): Text to display next to the spinner. Defaults to "".

    Example:
        async with spinner("Processing..."):
            await some_long_async_task()
    """
    stop = asyncio.Event()

    async def _spin() -> None:
        """Internal helper function to manage the spinner animation loop."""
        frames = itertools.cycle(SPINNER_FRAMES)
        while not stop.is_set():
            frame = next(frames)
            sys.stdout.write(f"\r{frame} {text}")
            sys.stdout.flush()
            try:
                await asyncio.wait_for(stop.wait(), 0.1)  # ~10 FPS
            except asyncio.TimeoutError:
                pass
        sys.stdout.write("\r\033[2K\r")  # Clear the spinner line
        sys.stdout.flush()

    task = asyncio.create_task(_spin())
    try:
        yield
    finally:
        stop.set()
        await task


async def connect_mcps(agent: Any, retries: int = 3):
    """Connects the agent to its associated MCP (Multi-Context Platform) servers.

    Attempts to connect to each MCP server defined in `agent.mcp_servers`.
    Retries connection up to `retries` times with a short delay between attempts.

    Args:
        agent: The agent instance, which should have an `mcp_servers` attribute list
               and a `name` attribute for logging.
        retries (int, optional): The number of connection attempts per server. Defaults to 3.

    Raises:
        Exception: Bubbles up the exception from the last failed connection attempt.
    """
    agent_name = getattr(agent, 'name', 'UnnamedAgent')
    mcp_servers_list = getattr(agent, 'mcp_servers', [])
    
    logger.info(f"Connecting to MCP servers for agent: {agent_name}")
    logger.debug(f"Agent {agent_name} MCP servers: {mcp_servers_list}")

    if not mcp_servers_list:
        logger.info(f"No MCP servers defined for agent {agent_name}.")
        return

    for mcp_server in mcp_servers_list:
        server_name = getattr(mcp_server, 'name', 'UnnamedMCPServer')
        logger.info(f"Connecting to MCP server: {server_name} for agent {agent_name}")
        for attempt in range(1, retries + 1):
            try:
                # Assuming mcp_server objects have a connect() method that is awaitable
                await asyncio.wait_for(mcp_server.connect(), timeout=10)
                logger.info(f"✅ Successfully connected to {server_name} on attempt {attempt} for agent {agent_name}")
                break
            except Exception as err:
                logger.warning(f"❌ Attempt {attempt} to connect to {server_name} for agent {agent_name} failed: {err!r}")
                if attempt == retries:
                    logger.error(f"Final attempt to connect to {server_name} for agent {agent_name} failed. Raising error.")
                    raise
                logger.info(f"Retrying connection to {server_name} in 2s…")
                await asyncio.sleep(2) 