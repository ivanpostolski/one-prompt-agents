"""
This module contains the core logic for managing chat interactions and agent execution
flows within the one-prompt-agents framework.

Key functionalities:
- `autonomous_chat`: Manages an autonomous, multi-turn conversation between an agent
  and a chat strategy. It handles job lifecycle, history, agent calls,
  and applies a selected strategy to determine continuation or termination.
- `user_chat`: Provides an interactive REPL (Read-Eval-Print Loop) for a user to directly
  chat with an agent via the console.
- `chat_worker`: An asynchronous worker that processes jobs from a queue. It checks job
  dependencies and then uses `autonomous_chat` to execute each job.

This module relies on other components:
- `strategies.py` for selecting and applying chat termination strategies.
- `job_manager.py` for accessing job details and status.
- `chat_utils.py` for utilities like `spinner`, `connect_mcps`.
"""
import asyncio
import logging
from typing import Any, List, Dict, Optional, TYPE_CHECKING

from agents import Runner, trace, enable_verbose_stdout_logging
from agents.exceptions import ModelBehaviorError # <-- Import ModelBehaviorError

# Imports from newly created modules
from .strategies import get_chat_strategy, ChatEndStrategy # Assuming ChatEndStrategy is needed for type hints
from .job_manager import Job, get_job, get_done_jobs # JOBS is managed within job_manager
from .chat_utils import spinner, connect_mcps

if TYPE_CHECKING:
    from one_prompt_agents.mcp_agent import MCPAgent

logger = logging.getLogger(__name__)


async def autonomous_chat(job: Job, max_turns: int = 15) -> None:
    """Manages an autonomous chat session for a given job.

    Handles the lifecycle of an agent's autonomous run including MCP connection,
    history management, iterative agent calls guided by a strategy, and job status updates.

    Args:
        job (Job): The job to be processed.
        max_turns (int, optional): Maximum number of turns for the autonomous session. Defaults to 15.
    """
    enable_verbose_stdout_logging()
    await connect_mcps(job.agent) # connect_mcps is now in chat_utils

    trace_id = f"autonomous-chat-{job.agent.name}-{job.job_id}"
    with trace(trace_id) as tr:
        # get_chat_strategy and get_job are imported from their respective new modules
        prompt_strategy_cls = get_chat_strategy(job.strategy_name)
        prompt_strategy = prompt_strategy_cls()
        
        current_conversation_history: List[Dict[str, str]]
        current_user_message_content: str

        if not job.chat_history:  # New job
            current_conversation_history = []
            initial_prompt_parts = []
            if job.job_id:
                initial_prompt_parts.append(f"Your JOB_ID is {job.job_id}.")
            initial_prompt_parts.append(job.text)
            if prompt_strategy.start_instruction:
                initial_prompt_parts.append(prompt_strategy.start_instruction)
            current_user_message_content = " ".join(initial_prompt_parts)
            logger.info(f"Starting new job {job.job_id} with initial prompt: {current_user_message_content}")
        else:  # Resuming job
            current_conversation_history = job.chat_history.copy()
            current_user_message_content = "Jobs waited have ended. Resume your task."
            logger.info(f"Resuming job {job.job_id} with history. Resume prompt: {current_user_message_content}")

        for check in range(1, max_turns + 1):
            try:
                logger.info(f"Job {job.job_id}: Turn {check}/{max_turns}")
                turn_input_for_api = current_conversation_history + [{"role": "user", "content": current_user_message_content}]
                
                try:                    
                    single_agent_run = await Runner.run(job.agent, input=turn_input_for_api)
                    
                    logger.debug(f"Job {job.job_id}: Agent run output object: {single_agent_run}")
                    final_output_data = single_agent_run.final_output # This is already the parsed Pydantic model or dict
                    logger.info(f"Job {job.job_id}: Agent run final output: {final_output_data}")
                    logger.info(f"Job {job.job_id}: Trace URL: https://platform.openai.com/traces/{tr.trace_id}")

                    current_conversation_history = single_agent_run.to_input_list()
                    job.chat_history = current_conversation_history.copy()

                    # Safely access summary from the final_output_data
                    if isinstance(final_output_data, dict) and "summary" in final_output_data:
                        job.summary = final_output_data["summary"]
                    elif hasattr(final_output_data, "summary"):
                        job.summary = final_output_data.summary

                    # Pass get_job from job_manager to the strategy's next_turn method
                    end_agent_run, new_user_request_content = prompt_strategy.next_turn(
                        final_output_data,
                        current_conversation_history,
                        job.agent, # This is agents.Agent instance
                        job.job_id,
                        get_job # Pass the get_job function
                    )

                    if end_agent_run:
                        logger.info(f"Job {job.job_id}: Strategy indicates completion after {check} turn(s)." )
                        job.status = 'done'
                        logger.info(f"Job {job.job_id}: Status set to 'done' by autonomous_chat.")
                        return
                    else:
                        if job.status == "in_queue": # If job was re-queued by a tool like _start_and_wait
                            logger.info(f"Job {job.job_id} was moved back to queue. Halting autonomous_chat for this iteration.")
                            return
                        current_user_message_content = new_user_request_content
                        if not current_user_message_content:
                            logger.warning(f"Job {job.job_id}: Strategy returned no content for next turn. Ending run.")
                            job.status = 'error' # Or some other status to indicate an issue
                            job.summary = (job.summary or "") + " Error: Strategy returned no content for next turn."
                            return 
                        logger.info(f"Job {job.job_id}: New user request for next turn: {current_user_message_content[:100]}...")

                except ModelBehaviorError as e:
                    logger.error(f"Job {job.job_id}: ModelBehaviorError during turn {check}: {e}", exc_info=True)
                    # Attempt to get the raw output that caused the error.
                    # The ModelBehaviorError has arguments (json_str, type_adapter) but doesn't store json_str directly.
                    # The string representation of e includes it, but it's better if we can extract it more cleanly.
                    # Pydantic's ValidationError (often wrapped by ModelBehaviorError) has `input_value` in its error dicts.
                    raw_llm_output = "[Could not extract raw LLM output from error]"
                    if hasattr(e, 'errors') and callable(e.errors):
                        try:
                            error_details = e.errors()
                            if error_details and isinstance(error_details, list) and error_details[0].get('input_value'):
                                raw_llm_output = str(error_details[0]['input_value'])
                        except Exception as ex_extract:
                            logger.warning(f"Job {job.job_id}: Could not extract input_value from ModelBehaviorError: {ex_extract}")
                    
                    current_user_message_content = prompt_strategy.get_format_correction_prompt(
                        agent_name=job.agent.name,
                        agent_instructions=job.agent.instructions,
                        expected_return_type=job.agent.output_type,
                        raw_llm_output=raw_llm_output, # Pass the raw output if available
                        error_details=str(e) # Full error string for context
                    )
                    logger.info(f"Job {job.job_id}: Sending correction prompt to agent due to formatting error.")
                    # Add the error and correction attempt to chat history for context
                    job.chat_history.append({"role": "system", "content": f"Error during previous turn: {e}. Attempting to correct."})
                    continue # Continue to the next iteration of the loop with the corrective prompt
            except Exception as e:
                logger.error(f"Job {job.job_id}: Error during turn {check}: {e}", exc_info=True)
                current_user_message_content = f"The last attempt failed with an error: {e}. Please review the situation, check your plan, and try to recover and continue the task."
        
        logger.info(f"Job {job.job_id}: Max turns ({max_turns}) reached. Current history saved. Job status: '{job.status}'.")
    return

async def user_chat(mcp_agent: "MCPAgent"):
    """Manages an interactive chat session (REPL) between a user and an agent.

    This function is designed for direct, command-line interaction with an agent.
    It automatically uses the `interactive_agent` attribute of the passed-in
    `mcp_agent`. This ensures that all interactive chats use a consistent
    output format (`assistant_reply: str`) regardless of the main agent's
    configured return type.

    Args:
        mcp_agent (MCPAgent): The MCPAgent instance to chat with. This function will
            specifically use the `mcp_agent.interactive_agent` for the session.
    """
    enable_verbose_stdout_logging()
    history: List[Dict[str, str]] = []

    # The interactive agent is what we want to use here. It's an attribute of the MCPAgent.
    chat_agent = mcp_agent.interactive_agent
    workflow_id = f"User-Chat-{getattr(chat_agent, 'name', 'UnnamedAgent')}"

    loop = asyncio.get_running_loop()
    await connect_mcps(mcp_agent) # connect_mcps is now in chat_utils

    with trace(workflow_id):
        while True:
            try:
                # The prompt should show the main agent name (the MCPAgent's name).
                user_text = await loop.run_in_executor(None, input, f"{getattr(mcp_agent, 'name', 'Agent')} You: ")
                user_text = user_text.strip()
            except (EOFError, KeyboardInterrupt):
                logger.debug("User interrupted input via EOF/KeyboardInterrupt.")
                user_text = "/exit"

            if user_text.lower() in {"/exit", "/quit", "exit", "quit"}:
                logger.info("Exiting user chat session.")
                return
            
            async with spinner(f"{getattr(mcp_agent, 'name', 'Agent')} thinking..."): # spinner from chat_utils
                turn_input = history + [{"role": "user", "content": user_text}]
                
                result = await Runner.run(starting_agent=chat_agent, input=turn_input, max_turns=10)
                
                final_output_data = result.final_output
                history = result.to_input_list()
            
            # Prefer 'assistant_reply' if present
            assistant_reply_content = getattr(final_output_data, 'assistant_reply', None)
            
            logger.info(f"Assistant raw output: {final_output_data}")
            if assistant_reply_content:
                print(f"Assistant: {assistant_reply_content}")

async def chat_worker(queue: "asyncio.Queue[Job]") -> None:
    """A worker that processes jobs from an asyncio queue.

    Continuously fetches jobs, checks dependencies, and executes them using `autonomous_chat`.

    Args:
        queue (asyncio.Queue[Job]): The queue from which to fetch jobs.
    """
    while True:
        job = await queue.get()
        logger.info(f"Chat worker picked up job {job.job_id} for agent {getattr(job.agent, 'name', 'UnnamedAgent')}.")

        # Check dependencies - get_done_jobs is from job_manager
        DONE_JOBS = get_done_jobs()
        unmet_dependencies = [dep_id for dep_id in job.depends_on if dep_id not in DONE_JOBS]

        if unmet_dependencies:
            logger.info(f"Job {job.job_id} has unmet dependencies: {unmet_dependencies}. Requeuing with 30s delay.")
            async def requeue_with_delay(current_job, delay_seconds, job_queue):
                await asyncio.sleep(delay_seconds)
                await job_queue.put(current_job)
                logger.info(f"Job {current_job.job_id} requeued after delay.")
            # It's important not to modify job status here, it's still 'in_queue' effectively
            asyncio.create_task(requeue_with_delay(job, 30, queue))
            queue.task_done() # Signal that this attempt to process the job is done (for now)
            continue
        
        try:
            job.status = 'in_progress'
            logger.info(f"Job {job.job_id} status set to 'in_progress'. Starting autonomous_chat.")
            
            # get_chat_strategy is from strategies module
            # autonomous_chat now takes the job object directly
            await autonomous_chat(job=job, max_turns=30)
            
            # autonomous_chat is responsible for setting job.status to 'done' or leaving it as 'in_progress' (or 'error')
            if job.status == 'in_progress':
                logger.info(f"Job {job.job_id} finished autonomous_chat (e.g. max_turns reached), status remains 'in_progress'. Will be picked up if explicitly requeued by a mechanism.")
            elif job.status == 'done':
                logger.info(f"Job {job.job_id} completed and marked as 'done' by autonomous_chat.")
            elif job.status == 'in_queue': # If a tool inside autonomous_chat re-queued it (e.g. _start_and_wait)
                 logger.info(f"Job {job.job_id} was explicitly moved back to 'in_queue' status during its run.")
            else:
                logger.info(f"Job {job.job_id} finished autonomous_chat with status: '{job.status}'.")

        except Exception as e:
            job.status = 'error'
            job.summary = (job.summary or "") + f" Error in chat_worker: {e}" # Append error to summary
            logger.error(f"Job {job.job_id} failed with exception in chat_worker: {e}", exc_info=True)
        finally:
            # Ensure JOBS reflects the final state of the job, especially if autonomous_chat modified it.
            # from .job_manager import JOBS # Not ideal here due to potential for repeated imports
            # JOBS[job.job_id] = job # This should be handled by functions that modify job, or by autonomous_chat itself.
            # The job object is mutable, so changes within autonomous_chat to job.status etc. are already reflected.
            logger.info(f"Chat worker finished processing job {job.job_id}. Final status: '{job.status}'.")
            queue.task_done() 