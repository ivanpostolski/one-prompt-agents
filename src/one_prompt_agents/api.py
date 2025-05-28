"""
Handles all things FastAPI for the one-prompt-agents framework.

This includes setting up the FastAPI application instance, defining
Pydantic models for request and response validation, and registering
the HTTP API endpoints (like health checks and agent run triggers).
It relies on the main CLI module to populate its agent registry.
"""
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from one_prompt_agents.mcp_agent import start_agent
import logging

logger = logging.getLogger(__name__)

# Will be populated after agent loading, imported from cli.py or a shared state module if needed
# For now, assuming it will be managed/populated by the main application logic in cli.py
# If direct access is needed here for some reason, this might need adjustment.
agents = {} 

app = FastAPI()

class RunRequest(BaseModel):
    """Defines the request model for running an agent.

    This Pydantic model is used to validate the incoming request body
    for the `/{agent_name}/run` endpoint. It expects a single field, `prompt`.

    Attributes:
        prompt (str): The prompt to be processed by the agent. Defaults to "".
    """
    prompt: str = ""

@app.get("/")
async def root():
    """Handles GET requests to the root path.

    This endpoint is a simple health check that returns a message
    indicating the server is running.

    Returns:
        dict: A dictionary with a "message" key.
    """
    return {"message": "Server is running"}

@app.post("/{agent_name}/run")
async def run_agent_endpoint(agent_name: str, req: RunRequest):
    """Handles POST requests to run a specific agent.

    This endpoint triggers an agent to process a given prompt.
    The agent is run asynchronously (fire-and-forget).

    Args:
        agent_name (str): The name of the agent to run.
        req (RunRequest): The request body containing the prompt.

    Raises:
        HTTPException: If the specified agent_name is not found.

    Returns:
        dict: A dictionary confirming the agent has started.
    """
    logger.info(f"Received request for agent {agent_name} with prompt: {req.prompt}")
    logger.info(f"Available agents: {list(agents.keys())}")
    if agent_name not in agents:
        logger.error(f"Agent {agent_name} not found. Available: {list(agents.keys())}")
        raise HTTPException(422, f"Unknown agent {agent_name}")
    
    # Ensure the agent object is correctly retrieved
    agent_instance = agents.get(agent_name)
    if not agent_instance:
        # This case should ideally be caught by the 'agent_name not in agents' check,
        # but as a safeguard:
        logger.error(f"Agent object for {agent_name} is None or empty.")
        raise HTTPException(500, f"Internal error retrieving agent {agent_name}")

    try:
        # fire-and-forget
        start_agent(agent_instance, req.prompt)
        logger.info(f"Successfully started agent {agent_name}")
        return {"status": "started", "agent": agent_name}
    except Exception as e:
        logger.error(f"Error starting agent {agent_name}: {e}", exc_info=True)
        raise HTTPException(500, f"Error starting agent {agent_name}")

# Placeholder for agents global, to be populated by the main CLI module
# This allows api.py to be imported without circular dependencies issues
# if main.py (soon to be cli.py) is what populates it.
def set_agents_for_api(loaded_agents: dict):
    global agents
    agents.update(loaded_agents)
    logger.info(f"API module updated with agents: {list(agents.keys())}") 