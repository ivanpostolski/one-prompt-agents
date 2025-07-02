from pydantic import BaseModel  # type: ignore

class EmptyAgentResponse(BaseModel):
    content: str 