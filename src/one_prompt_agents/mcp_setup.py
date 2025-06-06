"""
This file is responsible for setting up and managing the main FastMCP (Multi-Context Platform)
server instance for the one-prompt-agents system.

It defines the main MCP server and its system-level tools, which are available to all agents
that have this server in their `mcp_servers` configuration.

Key System-Level Tools Provided:
- `get_job_details`: Retrieves the full state and summary of a specified job.
- `wait_for_jobs`: Allows a running agent to pause its own execution and wait for a list
  of other jobs to complete before it resumes. This is crucial for orchestrating
  complex workflows, such as parallel job execution followed by a final aggregation step.

The agent registry and job queue used by these tools are populated by the main CLI module
during application startup.
"""
import os
import asyncio
import logging
from typing import Dict, List, TYPE_CHECKING
from fastmcp import FastMCP
from one_prompt_agents.job_manager import JOBS, get_job
from one_prompt_agents.utils import uvicorn_log_level

if TYPE_CHECKING:
    from one_prompt_agents.mcp_agent import MCPAgent

logger = logging.getLogger(__name__)

# This will hold the loaded agents, populated by cli.py
AGENTS_REGISTRY: Dict[str, "MCPAgent"] = {}
JOB_QUEUE: asyncio.Queue = None

MAIN_MCP_PORT = os.getenv("MAIN_MCP_PORT", 22222)

mcp = FastMCP(
    name="one-prompt-agent-mcp",
    version="0.2.0",
    description="Main MCP for the One-Prompt Agents framework, offering agent and job management tools.",
)

def get_job_mcp_tool(job_id: str):
    """Retrieves the status and summary of a job from the job queue for MCP.

    This function is exposed as an MCP tool. It checks the global `JOBS`
    dictionary for a job with the given ID.

    Args:
        job_id (str): The ID of the job to retrieve.

    Returns:
        str: A string containing the job status and summary, or "Job not found."
    """
    if job_id not in JOBS:
        return f"Job with ID '{job_id}' not found."
    
    job = JOBS.get(job_id)
    if job.summary:
        return f"{job.job_id}: {job.status}. Summary: {job.summary}"
    else:
        return f"{job.job_id}: {job.status}"


def get_job_mcp_tool_details(job_id: str):
    """Retrieves all details of a job from the job queue for MCP."""
    if job_id not in JOBS:
        return f"Job with ID '{job_id}' not found."
    
    job = JOBS.get(job_id)
    return job

mcp.add_tool(
    name="get_job_details", # Renamed for clarity to avoid conflict with chat_patterns.get_job
    description="Get the status and summary of a specific job by its ID.",
    fn=get_job_mcp_tool_details
)

# Add an alias for compatibility with agents expecting "get_job"
mcp.add_tool(
    name="get_job",
    description="Alias for get_job_details. Get the status and summary of a specific job by its ID.",
    fn=get_job_mcp_tool
)

def start_mcp_server():
    """Starts the main MCP server as an asynchronous task.

    This function initializes and runs the `FastMCP` server in the background,
    allowing other operations to proceed. It uses the `MAIN_MCP_PORT` environment
    variable or a default port.

    Returns:
        asyncio.Task: The task representing the running MCP server.
    """
    # uvicorn_log_level needs to be available here, or passed as an argument
    # For now, hardcoding to 'debug' for the MCP server as it's often for inter-service comms
    # This should be revisited to use the one from utils.py if appropriate for this context
    from one_prompt_agents.utils import uvicorn_log_level # Ensure this import is valid

    loop = asyncio.get_event_loop()
    task = loop.create_task(
        mcp.run_sse_async(
            host='127.0.0.1',
            port=MAIN_MCP_PORT,
            log_level=uvicorn_log_level() or 'debug' # Fallback if uvicorn_log_level returns None
        )
    )
    logger.info(f"Main MCP server starting on 127.0.0.1:{MAIN_MCP_PORT}")
    return task

# Placeholder for agents global, to be populated by the main CLI module
def set_agents_for_mcp_setup(loaded_agents: dict):
    global AGENTS_REGISTRY
    AGENTS_REGISTRY.update(loaded_agents)
    logger.info(f"MCP_setup module updated with agents: {list(AGENTS_REGISTRY.keys())}") 

def set_job_queue_for_mcp_setup(job_queue: asyncio.Queue):
    """Receives the global job queue from the main CLI module and adds queue-dependent tools."""
    global JOB_QUEUE
    JOB_QUEUE = job_queue
    mcp.add_tool(
        name="wait_for_jobs",
        description="Makes the calling agent's job wait for a list of other jobs to complete.",
        fn=wait_for_jobs
    )

def list_agents_sync() -> Dict[str, str]:
    """Synchronous wrapper to list agents. The tool function for FastMCP must be sync."""
    return {name: agent.url for name, agent in AGENTS_REGISTRY.items()}

async def wait_for_jobs(your_job_id: str, job_ids_to_wait_for: List[str]) -> str:
    """Makes the calling agent's job wait for a list of other jobs to complete.

    This is a system-level MCP tool. It finds the job specified by `your_job_id`,
    appends the `job_ids_to_wait_for` to its `depends_on` list, sets its
    status to 'in_queue', and puts it back on the job queue to wait.

    Args:
        your_job_id (str): The job ID of the agent that is calling this tool and needs to wait.
        job_ids_to_wait_for (List[str]): A list of job IDs to wait for.

    Returns:
        str: A message indicating that the job is now waiting for the specified jobs.
                Returns an error message if `your_job_id` is not found.
    """
    if not JOB_QUEUE:
        return "Error: The system's job queue is not available to the MCP server."

    waiter = get_job(your_job_id)

    if not waiter:
        return f"Job {your_job_id} not found. You must provide your own job id to wait for other jobs."

    # Add the new dependencies
    waiter.depends_on.extend(job_ids_to_wait_for)
    
    # Reset status and requeue
    waiter.status = 'in_queue'
    waiter.chat_history += f"Now waiting for jobs: {', '.join(job_ids_to_wait_for)}.\n"
    await JOB_QUEUE.put(waiter)

    return f"Your job ({your_job_id}) is now in queue, waiting for jobs {', '.join(job_ids_to_wait_for)} to complete."