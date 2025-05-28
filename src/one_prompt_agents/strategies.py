"""
This module defines various chat termination strategies for agents
in the one-prompt-agents framework.

A chat strategy determines whether an autonomous agent run should end or
continue, and if it continues, what the next user message to the agent
should be. This allows for different conversational flows and completion
conditions for agent tasks (e.g., based on plan completion, error states, etc.).

Includes:
- `ChatEndStrategy`: Base class for all strategies.
- `ContinueLastUncheckedStrategy`: Continues if the agent's plan has unchecked steps.
- `PlanWatcherStrategy`: Monitors plan consistency and step completion.
- `chat_strategy_map`: A registry for available strategies.
- `get_chat_strategy`: Function to retrieve a strategy class by name.
- `register_strategy`: Function to add new strategies to the map.

Strategies are designed to be decoupled from direct job state access by receiving
a `get_job_func` to query job details, avoiding circular dependencies.
"""
import logging
from typing import Tuple, Optional

logger = logging.getLogger(__name__)

# Forward declaration for type hinting JOBS if needed by strategies, though not directly used in this snippet
# from .job_manager import JOBS # This would create a circular import if JOBS is defined in job_manager
# Instead, strategies will receive job_id and use a get_job function provided from elsewhere (e.g., job_manager)

class ChatEndStrategy:
    """Base class for defining agent chat termination strategies.

    Subclasses must implement the `next_turn` method to determine if the
    chat should end and what the next user message should be if it continues.

    Attributes:
        start_instruction (str): A default instruction for the agent at the beginning of a task.
    """
    start_instruction: str = "Start by making a plan"

    def next_turn(self, final_output, history, agent, job_id: str, get_job_func) -> Tuple[bool, Optional[str]]:
        """Determines if the chat should end and provides the next user message.

        Args:
            final_output: The final output from the agent's last turn.
            history: The conversation history.
            agent: The agent instance.
            job_id (str): The ID of the current job.
            get_job_func (callable): A function to retrieve a job by its ID.

        Returns:
            Tuple[bool, Optional[str]]: A tuple where the first element is True
            if the chat should end, False otherwise. The second element is the
            next user message if the chat continues, or None if it ends.
        """
        raise NotImplementedError

class ContinueLastUncheckedStrategy(ChatEndStrategy):
    """A strategy that continues the chat as long as there are unchecked steps in the plan.

    It instructs the agent to continue with the first unchecked step.
    The chat ends when all plan steps are marked as checked or if the job status
    is no longer 'in_progress'.
    """
    start_instruction: str = "Start by making a plan"

    def next_turn(self, final_output, history, agent, job_id: str, get_job_func) -> Tuple[bool, Optional[str]]:
        """Checks the plan and job status to decide the next action.

        Args:
            final_output: The agent's output, expected to have a `plan` attribute.
            history: The conversation history.
            agent: The agent instance.
            job_id (str): The ID of the current job.
            get_job_func (callable): A function to retrieve a job by its ID.

        Returns:
            Tuple[bool, Optional[str]]: (end_chat, next_user_message)
        """
        job = get_job_func(job_id)
        if not job or job.status != 'in_progress':
            logger.info(f"ContinueLastUncheckedStrategy for job {job_id}: job status is '{job.status if job else 'not found'}'. Signaling agent run to end.")
            return False, None

        plan = getattr(final_output, 'plan', []) # Ensure plan is accessed safely
        if len(plan) == 0:
            return False, "Plan shouldn't be empty. Revisit the conversation history and generate a new plan according to your goals."
        elif all(getattr(step, 'checked', False) for step in plan): # Safe access to step.checked
            return True, None
        else:
            return False, "Continue with the first step of the plan that is not checked yet. And after verifing the step goal mark it as checked."

class PlanWatcherStrategy(ChatEndStrategy):
    """A strategy that monitors the agent's plan for consistency and completion.

    This strategy keeps track of the plan steps across turns. It checks for:
    - Unexpectedly removed plan steps that were not completed.
    - Empty plans.
    - Completion (all steps checked).

    It provides feedback to the agent to correct its plan or continue with unchecked steps.
    The chat ends if the job status is no longer 'in_progress' or all steps are checked.
    """
    start_instruction: str = "Start by making a plan"

    def __init__(self):
        """Initializes the PlanWatcherStrategy with an empty plan dictionary."""
        super().__init__()
        self.plan_dict = {}  # step_name -> step data

    def next_turn(self, final_output, history, agent, job_id: str, get_job_func) -> Tuple[bool, Optional[str]]:
        """Monitors plan changes and determines the next course of action.
        
        Args:
            final_output: The agent's output, expected to have a `plan` attribute.
            history: The conversation history.
            agent: The agent instance.
            job_id (str): The ID of the current job.
            get_job_func (callable): A function to retrieve a job by its ID.

        Returns:
            Tuple[bool, Optional[str]]: (end_chat, next_user_message)
        """
        job = get_job_func(job_id)
        if not job or job.status != 'in_progress':
            logger.info(f"PlanWatcherStrategy for job {job_id}: job status is '{job.status if job else 'not found'}'. Signaling agent run to end.")
            return False, None

        plan = getattr(final_output, 'plan', [])
        new_plan_dict = {getattr(step, 'step_name', str(i)): step for i, step in enumerate(plan)}
        messages = []

        for step_name, old_step in self.plan_dict.items():
            if step_name not in new_plan_dict:
                if not getattr(old_step, 'checked', False):
                    messages.append(f"The step: {step_name} was unexpectedly removed from your plan, please review it and add it again properly.")

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


# To be populated by the application, e.g., in cli.py or a dedicated strategy_registrar.py
chat_strategy_map = {
    "default": ContinueLastUncheckedStrategy,
    "plan_watcher": PlanWatcherStrategy,
}

def register_strategy(name: str, strategy_class: type[ChatEndStrategy]):
    """Registers a new chat strategy."""
    if name in chat_strategy_map:
        logger.warning(f"Strategy '{name}' is already registered. Overwriting.")
    chat_strategy_map[name] = strategy_class
    logger.info(f"Chat strategy '{name}' registered.")

def get_chat_strategy(strategy_name: str) -> type[ChatEndStrategy]:
    """Retrieves a chat strategy class based on its name.

    Looks up the strategy in the `chat_strategy_map`. If the name is not found,
    it defaults to `ContinueLastUncheckedStrategy`.

    Args:
        strategy_name (str): The name of the desired chat strategy.

    Returns:
        type[ChatEndStrategy]: The class of the chat strategy.
    """
    strategy_cls = chat_strategy_map.get(strategy_name)
    if not strategy_cls:
        logger.warning(f"Chat strategy '{strategy_name}' not found. Falling back to 'default' strategy.")
        return chat_strategy_map["default"]
    return strategy_cls 