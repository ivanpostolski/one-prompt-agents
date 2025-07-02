from pydantic import BaseModel  # type: ignore

class FilesystemAgentResponse(BaseModel):
    content: str 