# ---------------------------------------------------------------------------------------------------
# File: mcp_agent.py
# ---------------------------------------------------------------------------------------------------
import asyncio
from fastmcp import FastMCP
from agents.mcp import MCPServerStdio, MCPServerSse
from agents import Agent, Runner, trace, enable_verbose_stdout_logging, RunHooks
from typing import Any, List
from one_prompt_agents.utils import uvicorn_log_level
from one_prompt_agents.chat_patterns import submit_job, get_job

import logging
logger = logging.getLogger(__name__) 

next_port = 8000



class CaptureLastAssistant(RunHooks):
    def __init__(self):
        self.history: List[str] = []

    async def on_generation_end(self, item, ctx):
        logger.info(f"[CAPTURE] {item.output.content}")
        self.history.append(item.output.content)

    async def on_tool_start(self, context, agent, tool):
        logger.info(f"[CAPTURE] Tool started: {tool.name}")

class MCPAgent(MCPServerSse):
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
        # self.mcp.add_tool(
        #     name=f"start_and_notify_when_done_{name}",
        #     description=f"Starts a new job for the agent {name} and marks it as notify you when done, with a callback message returned once finished. Don't wait for it's response as is async.",
        #     fn=self._start_and_notify
        # )

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
        # Submit a job for this agent, no dependencies
        job_id = await submit_job(self.job_queue, self.agent, str(inputs), self.strategy_name)
        return f'Agent is running. Job started: {job_id}'

    async def _start_and_notify(self, inputs: str, notify_job_id: str, callback_prompt: str) -> str:
        # Expects inputs to be a dict with 'job_description' and 'notify_job_id'

        # Submit the first job (target agent)
        first_job_id = await submit_job(self.job_queue, self.agent, inputs, self.strategy_name)
        
        notify_job = get_job(notify_job_id)
        # Submit the notification job, which depends on the first job
        await submit_job(self.job_queue, notify_job.agent, f"In this prior run, you requested to be notified when the job {first_job_id} was finished: \n Prior run: \n {notify_job.chat_history}. \n Now the job has finished: \n {callback_prompt}.", notify_job.strategy_name, depends_on=[first_job_id])
        return f'Job started: {first_job_id} and will notify you when finished.'
    

    async def _start_and_wait(self, agent_inputs: str, your_job_id: str) -> str:
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
        if self.mcp_task:
            self.mcp_task.cancel()
            await asyncio.gather(self.mcp_task, return_exceptions=True)
        # cleanup SSE client
        await asyncio.gather(self.cleanup())

def start_agent(mcp_agent: MCPAgent, inputs, strategy_name=None):
    # Submit a job for this agent, no dependencies
    asyncio.get_event_loop().run_until_complete(
        submit_job(mcp_agent.job_queue, mcp_agent.agent, str(inputs), strategy_name or getattr(mcp_agent, 'strategy_name', 'default'))
    )
