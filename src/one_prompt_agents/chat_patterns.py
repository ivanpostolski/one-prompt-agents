import asyncio, itertools, sys
from typing import Any, Tuple, List, Set, Dict, Optional
from agents import Runner, trace, enable_verbose_stdout_logging, RunHooks
from contextlib import asynccontextmanager
import uuid
from dataclasses import dataclass, field

import logging
logger = logging.getLogger(__name__) 

SPINNER_FRAMES = "⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏" 

# ────── STRATEGY BASE CLASS ────── #
class ChatEndStrategy:
    start_instruction: str = "Start by making a plan"
    def next_turn(self, final_output, history, agent, job_id: str) -> Tuple[bool, Optional[str]]:
        raise NotImplementedError

# ────── CONTINUE LAST UNCHECKED STRATEGY ────── #
class ContinueLastUncheckedStrategy(ChatEndStrategy):
    start_instruction: str = "Start by making a plan"
    def next_turn(self, final_output, history, agent, job_id: str) -> Tuple[bool, Optional[str]]:
        job = JOBS.get(job_id)
        if not job or job.status != 'in_progress':
            logger.info(f"ContinueLastUncheckedStrategy for job {job_id}: job status is '{job.status if job else 'not found'}'. Signaling agent run to end.")
            return False, None

        if len(final_output.plan) == 0:
            return False, "Plan shouldn't be empty. Revisit the conversation history and generate a new plan according to your goals."
        elif all(step.checked for step in final_output.plan):
            return True, None
        else:
            return False, "Continue with the first step of the plan that is not checked yet. And after verifing the step goal mark it as checked."


class PlanWatcherStrategy(ChatEndStrategy):
    start_instruction: str = "Start by making a plan"
    def __init__(self):
        super().__init__()
        self.plan_dict = {}  # step_name -> step data

    def next_turn(self, final_output, history, agent, job_id: str) -> Tuple[bool, Optional[str]]:
        job = JOBS.get(job_id)
        if not job or job.status != 'in_progress':
            logger.info(f"PlanWatcherStrategy for job {job_id}: job status is '{job.status if job else 'not found'}'. Signaling agent run to end.")
            return False, None

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


async def connect_mcps(agent, retries = 3):
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
    chat_history: List[Dict[str, str]] = field(default_factory=list)
    summary: str | None = ""

# Global dict to track all jobs
JOBS: Dict[str, Job] = {}

def get_done_jobs() -> Set[str]:
    return {job_id for job_id, job in JOBS.items() if job.status == 'done'}

def get_job(job_id: str) -> Optional[Job]:
    """Retrieve a job by its ID."""
    return JOBS.get(job_id)

async def submit_job(queue: "asyncio.Queue[Job]", agent, text, strategy_name, depends_on=None) -> str:
    """Helper to submit a job to the queue with dependencies. Returns the job_id."""
    job_id = str(uuid.uuid4())[-6:] # Shortened job_id to last 6 characters
    job = Job(job_id=job_id, agent=agent, text=text, strategy_name=strategy_name, depends_on=depends_on or [], status='in_queue')
    JOBS[job_id] = job
    await queue.put(job)
    return job_id

async def autonomous_chat(job: Job, prompt_strategy_cls, max_turns: int = 15) -> None:
    enable_verbose_stdout_logging()

    # It's good practice to ensure mcps are connected before each autonomous session if they can disconnect.
    # If connect_mcps is idempotent or handles already connected state, this is fine.
    await connect_mcps(job.agent)

    trace_id = f"autonomous-chat-{job.agent.name}-{job.job_id}"
    with trace(trace_id) as tr:
        prompt_strategy = prompt_strategy_cls()
        
        current_conversation_history: List[Dict[str, str]]
        current_user_message_content: str

        if not job.chat_history:  # New job
            current_conversation_history = []
            # Combine JOB_ID, original request, and strategy's start instruction for the very first turn
            initial_prompt_parts = []
            if job.job_id: # Add JOB_ID if present
                initial_prompt_parts.append(f"Your JOB_ID is {job.job_id}.")
            initial_prompt_parts.append(job.text) # Original user request for the job
            if prompt_strategy.start_instruction: # Strategy specific start instruction
                initial_prompt_parts.append(prompt_strategy.start_instruction)
            current_user_message_content = " ".join(initial_prompt_parts)
            logger.info(f"Starting new job {job.job_id} with initial prompt: {current_user_message_content}")
        else:  # Resuming job
            current_conversation_history = job.chat_history.copy()
            current_user_message_content = "Jobs waited have ended. Resume your task."
            logger.info(f"Resuming job {job.job_id} with history. Resume prompt: {current_user_message_content}")

        for check in range(1, max_turns + 1):
            try:
                logger.info(f"Job {job.job_id}: Check {check} of {max_turns}")
                
                # Construct input for Runner.run
                # The history part is current_conversation_history
                # The new user message is current_user_message_content
                turn_input_for_api = current_conversation_history + [{"role": "user", "content": current_user_message_content}]
                
                single_agent_run = await Runner.run(job.agent, input=turn_input_for_api, hooks=capture) # Consider Runner's own max_turns if applicable
                
                logger.info(f"Job {job.job_id}: Agent run output:\n{single_agent_run.final_output}")
                logger.info(f"Job {job.job_id}: Trace URL: https://platform.openai.com/traces/{tr.trace_id}")

                # Update history from the agent's run
                current_conversation_history = single_agent_run.to_input_list()
                # Persist the full, updated history to the job object
                job.chat_history = current_conversation_history.copy()

                if "summary" in single_agent_run.final_output:
                    job.summary = single_agent_run.final_output.summary

                end_agent_run, new_user_request_content = prompt_strategy.next_turn(
                    single_agent_run.final_output,
                    current_conversation_history, # Pass the most up-to-date history
                    job.agent,
                    job.job_id # Pass job_id
                )

                if end_agent_run:
                    logger.info(f"Job {job.job_id}: Approved by strategy after {check} review cycle(s).")
                    job.status = 'done' # Set job status to done if strategy indicates completion
                    logger.info(f"Job {job.job_id}: Status set to done by autonomous_chat.")
                    return  # Job completed its autonomous cycle successfully
                else:
                    if job.status == "in_queue":
                        return # If the job is modified to queue, don't continue
                    current_user_message_content = new_user_request_content
                    logger.info(f"Job {job.job_id}: New user request for next turn: {current_user_message_content}")

            except Exception as e:
                logger.error(f"Job {job.job_id}: Error during check {check}: {e}", exc_info=True)
                # Prepare a user message to inform the agent about the error for the next attempt
                current_user_message_content = f"The last attempt failed with an error: {e}. Please review the situation, check your plan, and try to recover and continue the task."
                # Potentially add a small delay or specific error handling strategy here
        
        logger.info(f"Job {job.job_id}: Max turns ({max_turns}) reached. Current history saved. The job remains 'in_progress'.")
    return # Implicitly returns None

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

def get_chat_strategy(strategy_name: str) -> type[ChatEndStrategy]:
    strategy_cls = chat_strategy_map.get(strategy_name, ContinueLastUncheckedStrategy)
    return strategy_cls

async def chat_worker(queue: "asyncio.Queue[Job]") -> None:
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
            job.status = 'in_progress' # Worker sets to in_progress before starting
            prompt_strategy_cls = chat_strategy_map.get(job.strategy_name, ContinueLastUncheckedStrategy)
            await autonomous_chat(job=job, prompt_strategy_cls=prompt_strategy_cls, max_turns=30)
            
            # autonomous_chat now handles setting job.status to 'done' if strategy completes.
            # If autonomous_chat finishes and job.status is not 'done', it means max_turns was reached.
            if job.status == 'in_progress':
                logger.info(f"Job {job.job_id} finished autonomous_chat (likely max_turns reached), status remains 'in_progress'. Will be picked up again if requeued.")
            elif job.status == 'done':
                logger.info(f"Job {job.job_id} completed and marked as done by autonomous_chat.")
            elif job.status == 'in_queue':
                logger.info(f"Job {job.job_id} moved to the queue.")

        except Exception:
            job.status = 'error'
            logger.error(f"Job {job.job_id} failed with exception in chat_worker.", exc_info=True)
        finally:
            queue.task_done()

