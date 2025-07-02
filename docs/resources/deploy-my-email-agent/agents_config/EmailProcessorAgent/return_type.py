from pydantic import BaseModel  # type: ignore

class EmailProcessorAgentResponse(BaseModel):
    content: str 