import asyncio, itertools, sys
from typing import Any, Tuple
from agents import Runner, trace, enable_verbose_stdout_logging, RunHooks
from contextlib import asynccontextmanager

from one_prompt_agents.mcp_agent import MCPAgent
import logging
logger = logging.getLogger(__name__) 

SPINNER_FRAMES = "⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏"   # braille spinner ± → pick what you like

# ────── STRATEGY BASE CLASS ────── #
class ChatEndStrategy:
    def next_turn(self, final_output, history, agent):
        raise NotImplementedError

# ────── CONTINUE LAST UNCHECKED STRATEGY ────── #
class ContinueLastUncheckedStrategy(ChatEndStrategy):
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

async def autonomous_chat(agent, user_request: str, end_strategy, agent_max_turns: int = 100, max_turns: int = 15, ) -> None:
    enable_verbose_stdout_logging()          # keeps the "Exported … traces" line

    await connect_mcps(agent)

    trace_id = f"autonomous-chat-{agent.name}"
    with trace(trace_id) as tr: 
        # groups all spans in one dashboard row
        history = []

        for check in range(1, max_turns + 1):
            try:
                logger.info(f"Check {check} of {max_turns}")

                # run the agent with the user request
                # and the trace context from the outer scope
                turn_input = [{"role": "user", "content": user_request}]

                single_agent_run = await Runner.run(agent, input=history + turn_input, hooks=capture)
                
                logger.info("Agent run output:\n", single_agent_run.final_output)
                logger.info("Trace URL:",
                    f"https://platform.openai.com/traces/{tr.trace_id}")
                
                
                history = single_agent_run.to_input_list()

                # Use the end_strategy abstraction
                end_agent_run, new_user_request = end_strategy(single_agent_run.final_output, history, agent)
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

async def chat_worker(queue: "asyncio.Queue[Tuple[Any, str, str]]") -> None:
    """Background task that consumes (agent, text, strategy_name) jobs forever."""
    # Map strategy names to classes
    
    while True:
        agent, text, strategy_name = await queue.get()
        try:
            # Instantiate the strategy for each job
            strategy_instance = get_chat_strategy(strategy_name)
            await autonomous_chat(agent, text, max_turns=30, end_strategy=strategy_instance.next_turn)
        except Exception:
            # log / report as you prefer
            import traceback; traceback.print_exc()
        finally:
            queue.task_done()    # let join() know we're done

