from pydantic import BaseModel, Field

class MainAgentResponse(BaseModel):
    content: str = Field(description="Next agent answer.")
