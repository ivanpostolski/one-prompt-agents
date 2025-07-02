from pydantic import BaseModel  # type: ignore

class ApifyScraperAgentResponse(BaseModel):
    content: str 