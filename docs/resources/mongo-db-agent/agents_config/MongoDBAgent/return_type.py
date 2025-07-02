from pydantic import BaseModel  # type: ignore

class MongoDBAgentResponse(BaseModel):
    content: str 