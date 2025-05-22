from pydantic import BaseModel, Field

class EchoResponse(BaseModel):
    content: str = Field(description="The exact text that was provided in the prompt.")
