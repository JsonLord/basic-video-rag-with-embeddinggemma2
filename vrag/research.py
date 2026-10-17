"""Future outbound research job boundary; no autonomous jobs or local workers."""
from typing import Protocol
from pydantic import Field
from config.schema import Strict

class ResearchJob(Strict):
    task: str = Field(min_length=1, max_length=2000)
    observation_ids: list[str] = Field(max_length=20)

class ResearchStatus(Strict):
    job_id: str
    status: str

class ResearchWorker(Protocol):
    async def submit(self, job: ResearchJob) -> ResearchStatus: ...
    async def cancel(self, job_id: str) -> None: ...
