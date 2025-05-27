import argparse, asyncio, signal, uvicorn, os
from pathlib import Path
from one_prompt_agents.agents_loader import discover_configs, topo_sort, load_agents

from one_prompt_agents.chat_patterns import chat_worker, user_chat, autonomous_chat, get_chat_strategy, submit_job
from one_prompt_agents.mcp_agent import start_agent
from one_prompt_agents.mcp_servers_loader import collect_servers
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from fastmcp import FastMCP
from agents.mcp import MCPServerSse

# Logging setup

import sys
from pathlib import Path

import logging
from one_prompt_agents.logging_setup import setup_logging
from one_prompt_agents.http_start import ensure_server, trigger

def uvicorn_log_level() -> str | None:
    """Return the right string (or None) for uvicorn.log_level."""
    root = logging.getLogger()
    if root.manager.disable >= logging.CRITICAL:
        return None                      # logging globally disabled

    name = logging.getLevelName(root.getEffectiveLevel()).lower()
    return name if name in {"critical","error","warning","info","debug","trace"} else "warning"

# --- HTTP app setup ---
app = FastAPI()
class RunRequest(BaseModel):
    prompt: str = ""

# Will be populated after agent loading
agents = {}

@app.get("/")
async def root():
    return {"message": "Server is running"}

@app.post("/{agent_name}/run")
async def run_agent_endpoint(agent_name: str, req: RunRequest):
    print(f"Received request for agent {agent_name} with prompt: {req.prompt}")
    print(f"Agents: {agents.keys()}")
    if agent_name not in agents.keys():
        raise HTTPException(422, f"Unknown agent {agent_name}")
    # fire-and-forget
    start_agent(agents[agent_name], req.prompt)
    return {"status": "started", "agent": agent_name}

MAIN_MCP_PORT = os.getenv("MAIN_MCP_PORT", 22222)

mcp = FastMCP(
    name="one-prompt-agent-mcp",
    version="0.2.0",
    description="This MCP allows to get all links from an email file path.",
)

def change_agent_model(inputs):
    """Change the model of the agent."""
    agent_name = inputs.get("agent_name")
    new_model = inputs.get("new_model")
    if agent_name not in agents:
        raise ValueError(f"Agent {agent_name} not found.")
    if new_model is None:
        raise ValueError("New model not provided.")
    
    # Change the model of the agent
    agents[agent_name].agent.model = new_model
    return f"Model of agent {agent_name} changed to {new_model}."

mcp.add_tool(
    name="change_agent_model",
    description="Changes the model of the agent.",
    fn=lambda inputs: change_agent_model(inputs))


def start_mcp():
    import asyncio
    loop = asyncio.get_event_loop()
    task = loop.create_task(
        mcp.run_sse_async(
            host='127.0.0.1',
            port=MAIN_MCP_PORT,
            log_level='debug'
        )
    )
    return task

def run_server():
    parser = argparse.ArgumentParser()
    parser.add_argument("agent_name",
                        help="Agent to target")
                        
    parser.add_argument("prompt", help="Input prompt")
    args = parser.parse_args()
    if ensure_server(args.agent_name, args.prompt):
        trigger(args.agent_name, args.prompt)


def main():
    global agents
    NUM_WORKERS = 4 # Define the number of workers

    parser = argparse.ArgumentParser()
    parser.add_argument("agent_name", nargs="?",
                        help="Agent to target")
                        
    parser.add_argument("prompt", nargs="?", help="If provided, runs autonomous mode")

    parser.add_argument("--log", 
        action="store_const",          # flag present? drop const into dest
        const=True,           # numeric DEBUG level
        dest="log_to_file",              # name that ends up in args
        default=False,          # level when flag omitted
        help="redirects logs to a file"
    )
    
    # ―― verbose flag ――
    parser.add_argument(
        "-v", "--verbose",
        action="store_const",          # flag present? drop const into dest
        const=logging.DEBUG,           # numeric DEBUG level
        dest="log_level",              # name that ends up in args
        default=None,          # level when flag omitted
        help="Enable verbose output (sets logging level to DEBUG)"
    )


    args = parser.parse_args()

    if not args.log_level:
        print('Logging disabled')
        logging.disable(logging.CRITICAL)
    else:
        print('Enabling logging')
        setup_logging(args.log_to_file) 

    logging.info("Starting main mcp server...")
    main_mcp_task = start_mcp()

    logging.info("Collecting MCP servers...")

    # 1. Prepare static servers
    mcp_servers, mcp_tasks = collect_servers()

    mcp_tasks.append(main_mcp_task)

    logging.info(f"Servers collected:{list(mcp_servers.keys())}")
    

    # 2. Discover + order agents
    configs    = discover_configs(Path("agents_config"))
    load_order = topo_sort(configs)

    # 3. Start event loop + queue
    loop       = asyncio.get_event_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, loop.stop)

    job_queue  = asyncio.Queue()
    # worker     = loop.create_task(chat_worker(job_queue)) # Old single worker
    worker_tasks = [loop.create_task(chat_worker(job_queue)) for _ in range(NUM_WORKERS)] # Create multiple worker tasks
    logging.info(f"Started {NUM_WORKERS} chat workers.")

    try:
        # 4. Load all agents
        logging.info("Loading agents...")
        agents = load_agents(configs, load_order, mcp_servers, job_queue)
        logging.info(f"Loaded agents:{list(agents.keys())}")

        
        if args.agent_name and not args.prompt:
            # kick off interactive REPL
            target = agents[args.agent_name]
            loop.run_until_complete(user_chat(target.agent))
            raise ValueError("Interactive REPL terminated")
        
        elif args.agent_name and args.prompt:
            # kick off console autonomous run mode
            target = agents[args.agent_name]
            logging.info(f'Target agent {target}')
            
            # New block to submit job and wait
            async def run_job_and_wait():
                job_id = await submit_job(job_queue, target.agent, args.prompt, target.strategy_name)
                logging.info(f"Submitted job {job_id} for agent {args.agent_name}")
                await job_queue.join() # Wait for all jobs to be processed
                logging.info(f"Job {job_id} and all other queued jobs completed.")

            loop.run_until_complete(run_job_and_wait())
        
        
        # kick off HTTP server mode
        config = uvicorn.Config(app, host="127.0.0.1", port=9000, loop="asyncio", log_level=uvicorn_log_level()) 
        server = uvicorn.Server(config)
        # start the FastAPI server as a background task
        server_task = loop.create_task(server.serve())

        try:
            loop.run_forever()
        except KeyboardInterrupt:
            loop.run_until_complete(server.close())
            loop.run_until_complete(server.cleanup())
            pass

    except ValueError as err:
        pass


    finally:
        logging.info(f"Shutting down agents: {agents.keys()}")
        for agent in agents.values():
            loop.run_until_complete(agent.end_and_cleanup())
        logging.info(f"Agents shut down")
        logging.info(f"Shutting down servers: {mcp_servers.keys()}")
        for srv in mcp_servers.values():
            loop.run_until_complete(srv.cleanup())
        for mcp_task in mcp_tasks:
            mcp_task.cancel()                  # cancel the server tasks
            loop.run_until_complete(asyncio.gather(mcp_task, return_exceptions=True))
        logging.info(f"Servers shut down")
        # worker.cancel() # Old single worker cancellation
        # logging.info(f"Worker shut down") # Old single worker log
        logging.info(f"Shutting down {len(worker_tasks)} chat workers...")
        for worker_task in worker_tasks: # Cancel all worker tasks
            worker_task.cancel()
        # Wait for all worker tasks to be cancelled
        loop.run_until_complete(asyncio.gather(*worker_tasks, return_exceptions=True))
        logging.info(f"All chat workers shut down.")
        loop.close()
        logging.info(f"Event loop closed")