from pydantic import BaseModel
from typing import List


class Steps(BaseModel):
    plan_step: str
    step_name: str
    verified: bool
    checked: bool

class EchoResponse(BaseModel):
    plan: List[Steps]
    plan_completion_percentage: float
    response: str
    summary: str
