from pydantic import BaseModel  # type: ignore

class InteractiveAgentResponse(BaseModel):
    content: str 