# src/agent_runtime/jobs/models.py
from typing import Any, Dict, Literal, Optional
from pydantic import BaseModel, Field
import time

class JobRecord(BaseModel):
    """底层任务存储层真相来源（Job Store 实体）"""
    job_id: str
    job_type: str
    idempotency_key: str  # 强幂等防线主键
    status: Literal["queued", "running", "succeeded", "failed", "cancel_requested", "cancelled"]
    payload: Dict[str, Any]
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    attempt_count: int = 0
    max_attempts: int = 3
    created_at: float = Field(default_factory=time.time)
    updated_at: float = Field(default_factory=time.time)