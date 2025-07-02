from typing import List
from pydantic import BaseModel  # type: ignore

class Steps(BaseModel):
    plan_step: str
    step_name: str
    verified: bool
    checked: bool

class PlanReturnType(BaseModel):
    plan: List[Steps]
    plan_completion_percentage: float

class AutoFilesystemAgentResponse(PlanReturnType):
    """Return type for AutoFilesystemAgent.

    Extends the generic plan structure with a confirmation message.
    """
    content: str 