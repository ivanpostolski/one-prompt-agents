"""
This MCP server is used to get the status of a job using its job_id.
"""
from datetime import datetime, timedelta


from pymongo import MongoClient, ASCENDING, TEXT
from pymongo.collection import Collection
from pymongo.errors import PyMongoError

from fastmcp import FastMCP
from agents.mcp import MCPServerSse
from types import MethodType

import logging
logger = logging.getLogger(__name__)

# ── Config ────────────────────────────────────────────────────────────────── #


PORT = 9002 # New port for this server

# This server will host the get_job_status tool
job_status_processor_server = MCPServerSse(
    params={
        "url": f"http://localhost:{PORT}/sse",   # FastMCP default
        "timeout": 8,                     # connect timeout
        "sse_read_timeout": 100,          # how long the client waits for a tool call to finish
    },
    cache_tools_list=True,
    client_session_timeout_seconds=120,
    name="job-status-mcp", # New name for this specific server
)

# Re-using the one_prompt_agent_mcp definition from the other file
# This MCP is called by our new tool
one_prompt_agent_mcp = MCPServerSse(
    params={
        "url": f"http://localhost:22222/sse",   # Assuming this is the correct URL for one_prompt_agent_mcp
        "timeout": 8,                     # connect timeout
        "sse_read_timeout": 100,          # how long the client waits for a tool call to finish
        # No headers needed; GAFFA_API_KEY is already injected by your wrapper.
    },
    cache_tools_list=True,
    client_session_timeout_seconds=120,
    name="one-prompt-agent-mcp",
)

# Wrapper to ensure one_prompt_agent_mcp connects when job_status_processor_server connects
_job_status_connect = job_status_processor_server.connect

async def _wrapped_connect(self, *args, **kwargs):
    await one_prompt_agent_mcp.connect() # Connect to the agent MCP
    result = await _job_status_connect(*args, **kwargs) # Connect to self
    return result

job_status_processor_server.connect = MethodType(_wrapped_connect, job_status_processor_server)

# Define the FastMCP instance for this server
mcp = FastMCP(
    name="job-status-mcp", # Name for the FastMCP instance
    version="0.1.0",
    description="This MCP allows to get the status of a job using its job_id.",
)

@mcp.tool()
def get_job_details(job_id: str):
    """
    Retrieves the complete details of a job by its ID.
    """
    try:
        return one_prompt_agent_mcp.call_tool(
            "get_job_details",
            {"job_id": job_id}, # Parameters for the 'get_job' tool
        )
    except Exception as e:
        logger.error(f"Error calling get_job+details tool: {e}")

@mcp.tool()
def get_job_status(job_id: str):
    """
    Retrieves the status of a job by its ID by calling the 'get_job' tool
    on the one_prompt_agent_mcp.
    """
    try:
        return one_prompt_agent_mcp.call_tool(
            "get_job",
            {"job_id": job_id}, # Parameters for the 'get_job' tool
        )
    except Exception as e:
        logger.error(f"Error calling get_job tool: {e}")
        return {"error": str(e)}

def main():
    import asyncio
    loop = asyncio.get_event_loop()
    # Ensure pro_reasoning_processor_server (or the relevant server object) is started
    # This task will run job_status_processor_server
    task = loop.create_task(
        mcp.run_sse_async( # This runs the mcp instance which implicitly uses job_status_processor_server
            host='127.0.0.1',
            port=PORT,
            log_level='debug'
        )
    )
    # If you need to run other MCPs (like one_prompt_agent_mcp or pro_reasoning_mcp_server)
    # they should be started in their own processes or managed by a supervisor.
    # This main function only starts the job_status_mcp.
    return task