# ---------------------------------------------------------------------------------------------------
# File: mcp_agent.py
# ---------------------------------------------------------------------------------------------------
import asyncio
from fastmcp import FastMCP
from agents.mcp import MCPServerStdio, MCPServerSse
from agents import Agent, Runner, trace, enable_verbose_stdout_logging, RunHooks
from typing import Any, List
from one_prompt_agents.utils import uvicorn_log_level

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
            description=f"Starts the {name} agent.",
            fn=lambda inputs: self._start(inputs)
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

    def _start(self, inputs) -> str:
        start_agent(self, inputs)
        return 'Agent is running.'

    async def end_and_cleanup(self):
        if self.mcp_task:
            self.mcp_task.cancel()
            await asyncio.gather(self.mcp_task, return_exceptions=True)
        # cleanup SSE client
        await asyncio.gather(self.cleanup())

def start_agent(mcp_agent: MCPAgent, inputs):
    mcp_agent.job_queue.put_nowait((mcp_agent.agent, str(inputs)))
