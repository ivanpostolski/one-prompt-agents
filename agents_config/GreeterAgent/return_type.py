from pydantic import BaseModel, Field

class GreetingResponse(BaseModel):
    greeting_message: str = Field(description="The personalized greeting message.")
