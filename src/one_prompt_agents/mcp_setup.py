"""
This file is responsible for setting up and managing the main FastMCP (Multi-Context Platform)
server instance for the one-prompt-agents system.

It defines the MCP server, its tools (like changing an agent's model or getting job details),
and the function to start this server. The agent registry used by MCP tools is populated
by the main CLI module.
"""
import os
import asyncio
import logging
from fastmcp import FastMCP
from one_prompt_agents.job_manager import JOBS # JOBS is defined in job_manager.py

logger = logging.getLogger(__name__)

# This agents dictionary will need to be populated by the main application logic (cli.py)
# similar to how it's done for api.py. This is crucial for change_agent_model.
agents = {}

MAIN_MCP_PORT = os.getenv("MAIN_MCP_PORT", 22222)

mcp = FastMCP(
    name="one-prompt-agent-mcp",
    version="0.2.0",
    description="Main MCP for the One-Prompt Agents framework, offering agent and job management tools.",
)

def change_agent_model(inputs):
    """Changes the model of a specified agent.

    This function is exposed as an MCP tool. It allows changing the
    underlying model of an agent at runtime.

    Args:
        inputs (dict): A dictionary containing "agent_name" and "new_model".

    Raises:
        ValueError: If the agent is not found or new_model is not provided.

    Returns:
        str: A confirmation message.
    """
    agent_name = inputs.get("agent_name")
    new_model = inputs.get("new_model")
    if agent_name not in agents:
        raise ValueError(f"Agent {agent_name} not found. Available: {list(agents.keys())}")
    if new_model is None:
        raise ValueError("New model not provided.")
    
    agent_instance = agents.get(agent_name)
    if not agent_instance or not hasattr(agent_instance, 'agent'):
        raise ValueError(f"MCPAgent instance for {agent_name} is invalid or does not have an 'agent' attribute.")

    # Change the model of the agent
    agent_instance.agent.model = new_model
    logger.info(f"Model of agent {agent_name} changed to {new_model}.")
    return f"Model of agent {agent_name} changed to {new_model}."

mcp.add_tool(
    name="change_agent_model",
    description="Changes the model of a specified agent at runtime.",
    fn=change_agent_model # Direct reference, lambda was not strictly necessary
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
    global agents
    agents.update(loaded_agents)
    logger.info(f"MCP_setup module updated with agents: {list(agents.keys())}") 