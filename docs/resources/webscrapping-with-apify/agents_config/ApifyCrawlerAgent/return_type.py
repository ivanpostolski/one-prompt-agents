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

class ApifyCrawlerAgentResponse(PlanReturnType):
    content: str 