"""
This module is responsible for managing jobs within the one-prompt-agents framework.

A 'job' represents a specific task or conversation to be handled by an agent.
This includes:
- The `Job` dataclass: Defines the structure of a job (ID, agent, input text, status, etc.).
- `JOBS`: A global dictionary that acts as a registry for all active jobs, keyed by job ID.
- `get_done_jobs()`: Returns IDs of all completed jobs.
- `get_job()`: Retrieves a specific job by its ID.
- `submit_job()`: Creates a new job, adds it to the `JOBS` registry, and puts it onto an
  asyncio queue for processing by a chat worker.

The `JOBS` dictionary here is the central source of truth for job states, though strategies
and other components access job information via the `get_job` function to maintain decoupling.
"""
import asyncio
import uuid
from dataclasses import dataclass, field
from typing import Any, List, Dict, Set, Optional
import logging

logger = logging.getLogger(__name__)

@dataclass
class Job:
    """Represents a task to be processed by an agent.

    Jobs have an ID, an associated agent, input text, a strategy for execution,
    optional dependencies on other jobs, a status, chat history, and an optional summary.

    Attributes:
        job_id (str): Unique identifier for the job.
        agent (Any): The agent instance responsible for this job.
        text (str): The initial input text or prompt for the job.
        strategy_name (str): Name of the `ChatEndStrategy` to use for this job.
        depends_on (List[str]): List of job IDs that must be completed before this job can start.
        status (str): Current status of the job (e.g., 'in_draft', 'in_queue', 'in_progress', 'done', 'error').
        chat_history (List[Dict[str, str]]): The conversation history for this job.
        summary (str | None): An optional summary of the job's outcome or progress.
    """
    job_id: str
    agent: Any
    text: str
    strategy_name: str
    depends_on: List[str] = field(default_factory=list)
    status: str = 'in_draft'  # 'in_draft', 'in_queue', 'in_progress', 'done', 'error'
    chat_history: List[Dict[str, str]] = field(default_factory=list)
    summary: str | None = ""

# Global dict to track all jobs
JOBS: Dict[str, Job] = {}

def get_done_jobs() -> Set[str]:
    """Returns a set of job IDs for all jobs that have a 'done' status."""
    return {job_id for job_id, job in JOBS.items() if job.status == 'done'}

def get_job(job_id: str) -> Optional[Job]:
    """Retrieve a job by its ID from the global JOBS dictionary."""
    return JOBS.get(job_id)

async def submit_job(queue: "asyncio.Queue[Job]", agent: Any, text: str, strategy_name: str, depends_on: Optional[List[str]] = None) -> str:
    """Creates a new job, adds it to the global JOBS dictionary, and puts it on the processing queue.

    Args:
        queue (asyncio.Queue[Job]): The queue to add the job to.
        agent: The agent instance for the job.
        text (str): The input text/prompt for the job.
        strategy_name (str): The name of the chat strategy to use.
        depends_on (Optional[List[str]], optional): A list of job IDs this job depends on. Defaults to None.

    Returns:
        str: The ID of the newly created and submitted job.
    """
    job_id = str(uuid.uuid4())[-6:]  # Shortened job_id to last 6 characters
    job = Job(job_id=job_id, agent=agent, text=text, strategy_name=strategy_name, depends_on=depends_on or [], status='in_queue')
    JOBS[job_id] = job
    await queue.put(job)
    logger.info(f"Job {job_id} submitted to queue for agent {getattr(agent, 'name', 'UnnamedAgent')}.")
    return job_id 