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
from typing import Tuple, Optional, Any, Type, List, Dict
from pydantic import TypeAdapter, BaseModel, Field, create_model
import json

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
            agent: The agent instance (typically `agents.Agent`).
            job_id (str): The ID of the current job.
            get_job_func (callable): A function to retrieve a job by its ID.

        Returns:
            Tuple[bool, Optional[str]]: A tuple where the first element is True
            if the chat should end, False otherwise. The second element is the
            next user message if the chat continues, or None if it ends.
        """
        raise NotImplementedError

    def get_format_correction_prompt(
        self, 
        agent_name: str, 
        agent_instructions: str, 
        expected_return_type: Type[BaseModel],
        raw_llm_output: str, 
        error_details: str
    ) -> str:
        """Generates a prompt to correct the LLM's output format.

        Args:
            agent_name (str): Name of the agent.
            agent_instructions (str): Original instructions for the agent.
            expected_return_type (Type[BaseModel]): The Pydantic model expected for the output.
            raw_llm_output (str): The raw output from the LLM that caused the error.
            error_details (str): Details of the parsing error.

        Returns:
            str: A corrective prompt to send back to the LLM.
        """
        try:
            schema = TypeAdapter(expected_return_type).json_schema()
        except Exception as e:
            logger.error(f"Could not generate JSON schema for {expected_return_type}: {e}")
            schema = "Error generating schema. Please refer to the Pydantic model definition."

        part1 = f"Your previous response for agent '{agent_name}' was not in the correct format and could not be parsed.\n"
        part2 = f"Error details: {error_details}\n"
        part3 = f"The raw output you provided was:\n```json\n{raw_llm_output}\n```\n\n"
        part4 = f"Please carefully review your instructions and the required output format. "
        part5 = f"Your main instructions are:\n---\n{agent_instructions}\n---\n"
        part6 = f"You MUST respond with a valid JSON object matching the following Pydantic model schema:\n"
        
        schema_str = json.dumps(schema, indent=2)
        part7 = f"Schema for {expected_return_type.__name__}:\n```json\n{schema_str}\n```\n"
        part8 = f"Ensure your entire response is a single, valid JSON object. Pay special attention to string escaping"

        return part1 + part2 + part3 + part4 + part5 + part6 + part7 + part8

    # ---------------------------------------------------------------------
    # Return-type helper
    # ---------------------------------------------------------------------
    @classmethod
    def ensure_return_type(cls, return_type: Type[BaseModel]) -> Type[BaseModel]:
        """Return the given Pydantic model or, if required fields are missing for
        the current strategy, return a *new* Pydantic model class that extends
        the original one with the necessary definitions.

        Sub-classes can override this to enforce their own schema requirements.
        The default implementation just forwards ``return_type`` unchanged.
        """
        return return_type

    # ---------------------- internal helper utilities --------------------
    @staticmethod
    def _augment_step_model(original_model: Type[BaseModel], required_fields: Dict[str, tuple[Any, Any]]) -> Type[BaseModel]:
        """Create a new model based on *original_model* that contains all
        ``required_fields``.  If *original_model* already contains a field with
        the same name the original definition is preserved.

        Args:
            original_model: The user-supplied step model.
            required_fields: Mapping of *field_name* -> (*type*, *default*).

        Returns:
            A new subclass of ``original_model`` containing all of the
            ``required_fields``.
        """
        missing: Dict[str, tuple[Any, Any]] = {}
        for fname, (ftype, fdefault) in required_fields.items():
            if fname not in original_model.model_fields:  # pydantic v2
                missing[fname] = (ftype, fdefault)

        if not missing:
            return original_model

        # Build an augmented version that inherits from the original but adds
        # the required fields.
        Augmented = create_model(
            f"{original_model.__name__}Augmented",  # type: ignore[arg-type]
            __base__=original_model,
            **missing,
        )
        return Augmented

    @staticmethod
    def _build_plan_field(step_model: Type[BaseModel]):
        """Utility to build a plan field tuple for ``create_model`` calls."""
        return (List[step_model], Field(default_factory=list, description="Plan of steps to execute"))

class ContinueLastUncheckedStrategy(ChatEndStrategy):
    """A strategy that continues the chat as long as there are unchecked steps in the plan.

    It instructs the agent to continue with the first unchecked step.
    The chat ends when all plan steps are marked as checked or if the job status
    is no longer 'in_progress'.
    """
    start_instruction: str = "Start by making a plan"

    @classmethod
    def ensure_return_type(cls, return_type: Type[BaseModel]) -> Type[BaseModel]:
        """Ensure the supplied ``return_type`` has a ``plan`` field whose item
        model contains a boolean ``checked`` property.  If any of these are
        missing, a new Pydantic model class is generated that satisfies the
        requirement and returned instead.
        """
        # Step-level requirement: ``checked: bool``
        required_step_fields = {
            "checked": (bool, Field(default=False, description="Whether this step is completed."))
        }

        # --- Check if a plan field exists ----------------------------------
        if "plan" in return_type.model_fields:
            plan_field_info = return_type.model_fields["plan"]
            annotation = plan_field_info.annotation
            step_model = None

            # Extract the step model from typing e.g. list[StepModel]
            try:
                from typing import get_origin, get_args
                origin = get_origin(annotation)
                if origin in (list, List):
                    args = get_args(annotation)
                    if args:
                        step_model = args[0]
            except Exception:
                step_model = None

            if step_model is None or not isinstance(step_model, type):
                # Unable to introspect – build a brand-new plan step model with the required field.
                NewStepModel = create_model("PlanStep", **required_step_fields)  # type: ignore[arg-type]
            elif issubclass(step_model, BaseModel):
                # Check if the required field already exists.
                if "checked" in step_model.model_fields:
                    return return_type  # Already satisfies requirement.
                NewStepModel = cls._augment_step_model(step_model, required_step_fields)
            else:
                # Non-pydantic or non-model annotation, replace completely.
                NewStepModel = create_model("PlanStep", **required_step_fields)  # type: ignore[arg-type]

            # Build new return_type overriding plan with NewStepModel
            NewReturn = create_model(
                f"{return_type.__name__}WithPlanChecked",  # type: ignore[arg-type]
                __base__=return_type,
                plan=cls._build_plan_field(NewStepModel),
            )
            return NewReturn

        # If no plan field exists, create one.
        PlanStep = create_model("PlanStep", **required_step_fields)  # type: ignore[arg-type]
        NewReturn = create_model(
            f"{return_type.__name__}WithPlan",  # type: ignore[arg-type]
            __base__=return_type,
            plan=cls._build_plan_field(PlanStep),
        )
        return NewReturn

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

    @classmethod
    def ensure_return_type(cls, return_type: Type[BaseModel]) -> Type[BaseModel]:
        """Ensure the return type includes a ``plan`` list of steps that each
        expose **both** a ``step_name: str`` and a ``checked: bool`` field.
        """
        required_step_fields = {
            "step_name": (str, Field(..., description="Name of the plan step.")),
            "checked": (bool, Field(default=False, description="Whether the step is completed."))
        }

        if "plan" in return_type.model_fields:
            plan_field_info = return_type.model_fields["plan"]
            annotation = plan_field_info.annotation
            step_model = None

            try:
                from typing import get_origin, get_args
                origin = get_origin(annotation)
                if origin in (list, List):
                    args = get_args(annotation)
                    if args:
                        step_model = args[0]
            except Exception:
                step_model = None

            if step_model is None or not isinstance(step_model, type):
                NewStepModel = create_model("WatcherPlanStep", **required_step_fields)  # type: ignore[arg-type]
            elif issubclass(step_model, BaseModel):
                # If already satisfied, no changes needed.
                if all(f in step_model.model_fields for f in required_step_fields):
                    return return_type
                NewStepModel = cls._augment_step_model(step_model, required_step_fields)
            else:
                NewStepModel = create_model("WatcherPlanStep", **required_step_fields)  # type: ignore[arg-type]

            NewReturn = create_model(
                f"{return_type.__name__}Watched",  # type: ignore[arg-type]
                __base__=return_type,
                plan=cls._build_plan_field(NewStepModel),
            )
            return NewReturn

        # No plan field at all, create one with required step model
        StepModel = create_model("WatcherPlanStep", **required_step_fields)  # type: ignore[arg-type]
        NewReturn = create_model(
            f"{return_type.__name__}WithPlan",  # type: ignore[arg-type]
            __base__=return_type,
            plan=cls._build_plan_field(StepModel),
        )
        return NewReturn

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