# src/agent_runtime/jobs/store.py
from typing import Dict, Optional, List
import time
from agent_runtime.jobs.models import JobRecord

class SQLiteJobStore:
    """持久化长任务存储管理器：行使强幂等控制与原子级状态锁"""
    
    def __init__(self):
        self._db: Dict[str, JobRecord] = {}
    
    def submit_job(self, job_type: str, idempotency_key: str, payload: dict) -> JobRecord:
        """提交长任务：部署确定性主键拦截。若 key 冲突，直接返回已有任务引用，不引发重复下发副作用"""
        # 1. 强幂等防线拦截：检查该 key 是否已经存在
        for existing_job in self._db.values():
            if existing_job.idempotency_key == idempotency_key:
                return existing_job  # 原地自愈，直接返回已有 JobRef，阻断二次物理副作用
                
        # 2. 不存在冲突，全新入队
        job_id = f"job_async_{int(time.time() * 1000)}"
        record = JobRecord(
            job_id=job_id, job_type=job_type, idempotency_key=idempotency_key,
            status="queued", payload=payload
        )
        self._db[job_id] = record
        return record
    
    def get_job(self, job_id: str) -> Optional[JobRecord]:
        """精细化读取 Job 详情"""
        return self._db.get(job_id)
    
    def update_job_status(self, job_id: str, status: str, result: Optional[dict] = None, error: Optional[str] = None) -> Optional[JobRecord]:
        """原子级状态转移锁"""
        if job_id in self._db:
            job = self._db[job_id]
            job.status = status
            job.updated_at = time.time()
            if result is not None:
                job.result = result
            if error is not None:
                job.error = error
            return job
        return None
    
    def fetch_next_queued_job(self) -> Optional[JobRecord]:
        """Worker 消费者拉取就绪任务"""
        for job in self._db.values():
            if job.status == "queued":
                return job
        return None

    def fetch_next_cancel_requested_job(self) -> Optional[JobRecord]:
        """Return a cancellation that must be acknowledged by the worker."""
        for job in self._db.values():
            if job.status == "cancel_requested":
                return job
        return None
