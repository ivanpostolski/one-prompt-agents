from pydantic import BaseModel
from typing import List

class JobTestResult(BaseModel):
    """
    The final output of the JobTestAgent, summarizing the results
    of the parallel echo jobs it waited for.
    """
    final_summary: str
    echoed_results: List[str] 