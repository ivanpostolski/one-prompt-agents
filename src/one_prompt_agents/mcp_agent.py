# ---------------------------------------------------------------------------------------------------
# File: mcp_agent.py
# ---------------------------------------------------------------------------------------------------
import asyncio
from fastmcp import FastMCP
from agents.mcp import MCPServerStdio, MCPServerSse
from agents import Agent, Runner, trace, enable_verbose_stdout_logging, RunHooks
from typing import Any, List
from one_prompt_agents.utils import uvicorn_log_level
from one_prompt_agents.job_manager import submit_job, get_job
from one_prompt_agents.chat_utils import CaptureLastAssistant

import logging
logger = logging.getLogger(__name__) 

next_port = 8000


class MCPAgent(MCPServerSse):
    """Represents an agent that is also an MCP SSE (Server-Sent Events) server.

    This class encapsulates an `Agent` and exposes it as a tool through a `FastMCP`
    server. It allows other agents or systems to interact with this agent via SSE.
    It manages a job queue for processing requests and can interact with other MCP servers.

    Attributes:
        url (str): The SSE URL where this MCPAgent is listening.
        job_queue (asyncio.Queue): The queue used to submit jobs to this agent.
        mcp_servers (List[Any]): A list of other MCP servers this agent can interact with.
        prompt_file (str): Path to the file containing the agent's instructions.
        return_type (Any): The expected Pydantic model or type for the agent's output.
        inputs_description (str): A description of the inputs this agent expects.
        strategy_name (str): The name of the chat strategy to use for jobs processed by this agent.
        agent (Agent): The underlying `agents.Agent` instance.
        mcp (FastMCP): The `FastMCP` server instance that exposes this agent as tools.
        mcp_task (asyncio.Task): The asyncio task running the `FastMCP` server.
    """
    def __init__(
        self,
        name: str,
        prompt_file: str,
        return_type: Any,
        inputs_description: str,
        mcp_servers: List[Any],
        job_queue: asyncio.Queue,
        model: str,
        strategy_name: str = "default",
    ):
        """Initializes the MCPAgent.

        Args:
            name (str): The name of the agent.
            prompt_file (str): Path to the file containing the agent's instructions.
            return_type (Any): The Pydantic model or type for the agent's output.
            inputs_description (str): A description of the inputs this agent expects.
            mcp_servers (List[Any]): List of other MCP servers for the agent to use.
            job_queue (asyncio.Queue): The job queue for submitting tasks to this agent's chat worker.
            model (str): The model name (e.g., "gpt-4-1106-preview") for the underlying agent.
            strategy_name (str, optional): The chat strategy to use. Defaults to "default".
        """
        global next_port
        next_port += 1
        self.url = f"http://127.0.0.1:{next_port}/sse"
        super().__init__(
            params={
                'url': self.url,
                'timeout': 8,
                'sse_read_timeout': 100
            },
            cache_tools_list=True,
            client_session_timeout_seconds=120,
            name=name,
        )
        self.job_queue = job_queue
        self.mcp_servers = mcp_servers
        self.prompt_file = prompt_file
        self.return_type = return_type
        self.inputs_description = inputs_description
        self.strategy_name = strategy_name

        with open(prompt_file, 'r', encoding='utf-8') as f:
            instructions = f.read()

        self.agent = Agent(
            name=name,
            instructions=instructions,
            model=model,
            output_type=return_type,
            mcp_servers=mcp_servers,
        )

        # FastMCP server to expose this agent as a tool
        self.mcp = FastMCP(
            name=f"{name}_mcp",
            version='0.2.0',
            description=f"This MCP allows to call the {name} agent.",
        )
        self.mcp.add_tool(
            name=f"start_agent_{name}",
            description=f"Starts the {name} agent async. No wait for it's response.",
            fn=lambda inputs: self._start(inputs)
        )
        self.mcp.add_tool(
            name=f"_start_and_wait_{name}",
            description=f"Starts a new job for the agent {name} and waits until it's finished.",
            fn=self._start_and_wait
        )


        # Start FastMCP SSE for other agents to call
        loop = asyncio.get_event_loop()
        self.mcp_task = loop.create_task(
            self.mcp.run_sse_async(
                host='127.0.0.1',
                port=next_port,
                log_level=uvicorn_log_level(),
            )
        )

    async def _start(self, inputs) -> str:
        """Handles a simple start request for the agent.

        Submits a job to the agent's queue and returns a job ID.
        This is exposed as an MCP tool: `start_agent_{name}`.

        Args:
            inputs: The input prompt or data for the agent.

        Returns:
            str: A message indicating the job has started, along with the job ID.
        """
        # Submit a job for this agent, no dependencies
        job_id = await submit_job(self.job_queue, self.agent, str(inputs), self.strategy_name)
        return f'Agent is running. Job started: {job_id}'


    async def _start_and_wait(self, agent_inputs: str, your_job_id: str) -> str:
        """Starts a job for this agent and makes the calling agent's job wait for its completion.

        This method is exposed as an MCP tool: `_start_and_wait_{name}`.
        It submits a job for the current MCPAgent. Then, it modifies the job specified
        by `your_job_id` (the calling agent's job) to depend on the newly created job.
        The calling agent's job status is set to 'in_queue' and it's put back on the
        job queue to wait.

        Args:
            agent_inputs (str): The input/prompt for the job of this MCPAgent.
            your_job_id (str): The job ID of the agent that is calling this tool and needs to wait.

        Returns:
            str: A message indicating the job has started and the calling agent should wait.
                 Returns an error message if `your_job_id` is not found.
        """
        # Submit a job for this agent, no dependencies
        job_id = await submit_job(self.job_queue, self.agent, agent_inputs, self.strategy_name)

        waiter = get_job(your_job_id)

        if not waiter:
            return f"Job {your_job_id} not found. You must provide your own job id to wait for another job."
        else:# change the waiter job status to in_queue 
            waiter.status = 'in_queue'
            # add the job id to the waiter's depends_on
            waiter.depends_on.append(job_id)
            # add the job id to the waiter's chat_history
            waiter.chat_history += f"Job {job_id} has been started.\n"
            # put the waiter back in the job queue
            await self.job_queue.put(waiter)

        return f"Job {job_id} has been started. To wait for it's completion return your plan."



    async def end_and_cleanup(self):
        """Shuts down the MCPAgent's FastMCP server and cleans up SSE client resources.

        This method should be called during application shutdown to ensure graceful
        termination of background tasks and network connections.
        """
        if self.mcp_task:
            self.mcp_task.cancel()
            await asyncio.gather(self.mcp_task, return_exceptions=True)
        # cleanup SSE client
        await asyncio.gather(self.cleanup())

async def start_agent(mcp_agent: MCPAgent, inputs, strategy_name=None):
    """Submits a job to the specified MCPAgent's job queue.

    This is a utility function to trigger an agent run. It should be called
    from an async context.

    Args:
        mcp_agent (MCPAgent): The MCPAgent instance to run.
        inputs: The input prompt or data for the agent.
        strategy_name (str, optional): The name of the chat strategy to use.
            If None, uses the `mcp_agent.strategy_name` or defaults to "default".
    """
    # Submit a job for this agent, no dependencies
    await submit_job(mcp_agent.job_queue, mcp_agent.agent, str(inputs), strategy_name or getattr(mcp_agent, 'strategy_name', 'default'))
