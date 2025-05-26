import asyncio, itertools, sys
from typing import Any, Tuple, List, Set, Dict, Optional
from agents import Runner, trace, enable_verbose_stdout_logging, RunHooks
from contextlib import asynccontextmanager
import uuid
from dataclasses import dataclass, field

from one_prompt_agents.mcp_agent import MCPAgent
import logging
logger = logging.getLogger(__name__) 

SPINNER_FRAMES = "⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏"   # braille spinner ± → pick what you like

# ────── STRATEGY BASE CLASS ────── #
class ChatEndStrategy:
    start_instruction: str = "Start by making a plan"
    def next_turn(self, final_output, history, agent):
        raise NotImplementedError

# ────── CONTINUE LAST UNCHECKED STRATEGY ────── #
class ContinueLastUncheckedStrategy(ChatEndStrategy):
    start_instruction: str = "Start by making a plan"
    def next_turn(self, final_output, history, agent):
        if len(final_output.plan) == 0:
            return False, "Plan shouldn't be empty. Revisit the conversation history and generate a new plan according to your goals."
        elif all(step.checked for step in final_output.plan):
            return True, None
        else:
            return False, "Continue with the first step of the plan that is not checked yet. And after verifing the step goal mark it as checked."

# For backward compatibility, keep the old function as a reference to the class method
continue_last_unchecked_strategy = ContinueLastUncheckedStrategy().next_turn


class PlanWatcherStrategy(ChatEndStrategy):
    start_instruction: str = "Start by making a plan"
    def __init__(self):
        self.plan_dict = {}  # step_name -> step data

    def next_turn(self, final_output, history, agent):
        plan = getattr(final_output, 'plan', [])
        new_plan_dict = {getattr(step, 'step_name', str(i)): step for i, step in enumerate(plan)}
        messages = []

        # Check for removed steps that were not checked
        for step_name, old_step in self.plan_dict.items():
            if step_name not in new_plan_dict:
                if not getattr(old_step, 'checked', False):
                    messages.append(f"The step: {step_name} was unexpectedly removed from your plan, please review it and add it again properly.")

        # Update internal plan_dict with the latest plan
        self.plan_dict = new_plan_dict.copy()

        if len(plan) == 0:
            messages.append("Plan shouldn't be empty. Revisit the conversation history and generate a new plan according to your goals.")
            return False, " ".join(messages)
        elif all(getattr(step, 'checked', False) for step in plan):
            return True, None
        else:
            if not messages:
                messages.append("Continue with the first step of the plan that is not checked yet. And after verifying the step goal mark it as checked.")
            return False, " ".join(messages)

@asynccontextmanager
async def spinner(text: str = ""):
    """Async context manager that shows an animated spinner.

    Usage:
        async with spinner("thinking "):
            await long_call()
    """
    stop = asyncio.Event()

    async def _spin() -> None:
        frames = itertools.cycle(SPINNER_FRAMES)
        while not stop.is_set():
            frame = next(frames)
            sys.stdout.write(f"\r{frame} {text}")
            sys.stdout.flush()
            try:
                await asyncio.wait_for(stop.wait(), 0.1)   # ~10 FPS
            except asyncio.TimeoutError:
                pass
        # wipe the whole line, not just some characters
        sys.stdout.write("\r\033[2K\r")
        sys.stdout.flush()

    task = asyncio.create_task(_spin())
    try:
        yield
    finally:
        stop.set()
        await task


async def connect_mcps(agent: MCPAgent, retries = 3):
    logger.info(f"Connecting to {agent} MCP servers")
    logger.info(f"Connecting to {agent.name} MCP servers {agent.mcp_servers}")

    for mcp_server in agent.mcp_servers:
        logger.info(f"Connecting to {mcp_server.name}")
        for attempt in range(1, retries + 1):
            try:
                await asyncio.wait_for(mcp_server.connect(), timeout=10)
                logger.info(f"✅ Connected on attempt {attempt}")
                break
            except Exception as err:
                if attempt == retries:
                    raise                         # bubble the final error
                logger.info(f"❌ Attempt {attempt} failed ({err!r}); retrying in {2}s…")
                await asyncio.sleep(2)
          


class CaptureLastAssistant(RunHooks):
    def __init__(self):
        self.history = []

    async def on_generation_end(self, item, ctx):
        # item.output.content is the assistant text
        logger.info(f"[CAPTURE HOOK] Assistant: {item.output.content}")
        self.history += [item.output.content]

    async def on_tool_start(self,
        context,
        agent, 
        tool
    ) -> None:
        # This is called when the agent starts a tool call.
        # You can use this to log or modify the context before the tool is called.
        logger.info(f"[CAPTURE HOOK] Tool started: {tool.name}")

capture = CaptureLastAssistant()

@dataclass
class Job:
    job_id: str
    agent: Any
    text: str
    strategy_name: str
    depends_on: List[str] = field(default_factory=list)
    status: str = 'in_draft'  # 'in_draft', 'in_queue', 'in_progress', 'done'
    chat_history: str = ''

# Global dict to track all jobs
JOBS: Dict[str, Job] = {}

def get_done_jobs() -> Set[str]:
    return {job_id for job_id, job in JOBS.items() if job.status == 'done'}

async def submit_job(queue: "asyncio.Queue[Job]", agent, text, strategy_name, depends_on=None) -> str:
    """Helper to submit a job to the queue with dependencies. Returns the job_id."""
    job_id = str(uuid.uuid4())
    job = Job(job_id=job_id, agent=agent, text=text, strategy_name=strategy_name, depends_on=depends_on or [], status='in_queue')
    JOBS[job_id] = job
    await queue.put(job)
    return job_id

async def autonomous_chat(agent, user_request: str, prompt_strategy_cls, agent_max_turns: int = 100, max_turns: int = 15, job_id: Optional[str] = None) -> None:
    enable_verbose_stdout_logging()          # keeps the "Exported … traces" line

    await connect_mcps(agent)

    trace_id = f"autonomous-chat-{agent.name}"
    with trace(trace_id) as tr: 
        history = []
        chat_history_str = ''
        prompt_strategy = prompt_strategy_cls()
        for check in range(1, max_turns + 1):
            try:
                logger.info(f"Check {check} of {max_turns}")
                if check == 1 and job_id is not None:
                    turn_input = [{"role": "user", "content": f"Your JOB_ID is {job_id},. {user_request} {prompt_strategy.start_instruction}"}]
                else:
                    turn_input = [{"role": "user", "content": user_request}]
                single_agent_run = await Runner.run(agent, input=history + turn_input, hooks=capture)
                logger.info("Agent run output:\n", single_agent_run.final_output)
                logger.info("Trace URL:", f"https://platform.openai.com/traces/{tr.trace_id}")
                history = single_agent_run.to_input_list()
                # Update chat_history
                chat_history_str += f"User: {user_request}\nAssistant: {getattr(single_agent_run.final_output, 'content', '')}\n"
                if job_id and job_id in JOBS:
                    JOBS[job_id].chat_history = chat_history_str
                end_agent_run, new_user_request = prompt_strategy.next_turn(single_agent_run.final_output, history, agent)
                if end_agent_run:
                    logger.info(f"Approved after {check} review cycle(s).")
                    return single_agent_run.final_output
                else:
                    user_request = new_user_request
                    logger.info(f"New user request: {user_request}")
            except Exception as e:
                logger.info(f"Error: {e}, retrying")
                user_request = f"Last command failed with error {e}. Please retry."
    return

# ────── MAIN CHAT LOOP ────── #
async def user_chat(agent):
    enable_verbose_stdout_logging()     # prints "Exported … traces" on success:contentReference[oaicite:0]{index=0}
    history     = []                    # list[dict]
    workflow_id = f"User-Chat-{agent.name}"

    loop = asyncio.get_running_loop()

    await connect_mcps(agent)

    # Every turn of the conversation is wrapped in ONE trace ↓
    with trace(workflow_id):            # SDK traces by default – this groups them:contentReference[oaicite:1]{index=1}
        while True:
            try:
                user_text = await loop.run_in_executor(
                        None,          # default ThreadPoolExecutor
                        input,         # the blocking function
                        "You: "        # its arg
                    )
                user_text = user_text.strip()
            except (EOFError, KeyboardInterrupt):
                logger.debug("User interrupted input")
                user_text = "/exit"

            if user_text.lower() in {"/exit", "/quit","exit", "quit"}:
                return
            
            async with spinner("processing"):
                # Build input for this turn
                turn_input = history + [{"role": "user", "content": user_text}]
                result     = await Runner.run(
                    starting_agent=agent,
                    input=turn_input,
                    max_turns=10
                )

                assistant_reply = result.final_output
                logger.info(f"Assistant: {assistant_reply}")
                print(f"Assistant:\n{assistant_reply.content}")

                # Persist conversation state for next round
                history = result.to_input_list()


chat_strategy_map = {
        "default": ContinueLastUncheckedStrategy,
        "plan_watcher": PlanWatcherStrategy,
        # Add more strategies here as needed
}

def get_chat_strategy(strategy_name: str) -> ChatEndStrategy:
    strategy_cls = chat_strategy_map.get(strategy_name, ContinueLastUncheckedStrategy)
    return strategy_cls()

async def chat_worker(queue: "asyncio.Queue[Job]") -> None:
    strategy_map = {
        "default": ContinueLastUncheckedStrategy,
        "plan_watcher": PlanWatcherStrategy,
        # Add more strategies here as needed
    }
    while True:
        job = await queue.get()
        # Check dependencies
        DONE_JOBS = get_done_jobs()
        unmet = [dep for dep in job.depends_on if dep not in DONE_JOBS]
        if unmet:
            logger.info(f"Job {job.job_id} waiting for dependencies: {unmet}. Requeuing with backoff (non-blocking).")
            async def requeue_later(job, delay, queue):
                await asyncio.sleep(delay)
                await queue.put(job)
            asyncio.create_task(requeue_later(job, 300, queue))
            queue.task_done()
            continue
        try:
            job.status = 'in_progress'
            prompt_strategy_cls = strategy_map.get(job.strategy_name, ContinueLastUncheckedStrategy)
            await autonomous_chat(job.agent, job.text, prompt_strategy_cls=prompt_strategy_cls, max_turns=30, job_id=job.job_id)
            job.status = 'done'
            logger.info(f"Job {job.job_id} completed. Status set to done.")
        except Exception:
            import traceback; traceback.print_exc()
        finally:
            queue.task_done()

