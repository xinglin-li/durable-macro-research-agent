# src/agent_runtime/jobs/worker.py
import asyncio
from typing import Callable, Dict, Any, Optional
from agent_runtime.jobs.store import SQLiteJobStore

class AsyncMacroJobWorker:
    """长期异步多任务 Worker 处理器：负责拉取、多路重试与自检优雅取消"""
    
    def __init__(self, store: SQLiteJobStore):
        self.store = store
        self._running = False
        self._loop_task: Optional[asyncio.Task] = None

    async def start(self):
        """激活后台常驻消费者循环"""
        self._running = True
        self._loop_task = asyncio.create_task(self._process_loop())

    async def stop(self):
        """优雅关闭工作流"""
        self._running = False
        if self._loop_task:
            self._loop_task.cancel()

    async def _process_loop(self):
        """常驻轮询中心"""
        while self._running:
            cancelled_job = self.store.fetch_next_cancel_requested_job()
            if cancelled_job:
                self.store.update_job_status(
                    cancelled_job.job_id,
                    "cancelled",
                    error="Cancelled gracefully by human request.",
                )

            job = self.store.fetch_next_queued_job()
            if job:
                # 1. 领取任务，锁定状态为 running
                self.store.update_job_status(job.job_id, "running")
                job.attempt_count += 1
                
                # 2. 派发执行具体的宏观长任务计算逻辑
                asyncio.create_task(self._execute_job_core(job.job_id))
            await asyncio.sleep(0.01) # 防止 busy waiting 榨干 CPU

    async def _execute_job_core(self, job_id: str):
        """核心计算体：模拟需要密集消耗资源的时序模型计算过程"""
        job = self.store.get_job(job_id)
        if not job:
            return

        try:
            # --- 模拟密集计算阶段一 ---
            await asyncio.sleep(0.02)
            
            # 【优雅取消第一处心跳自检卡点】
            # 必须在物理密集步骤之间进行自检，一旦捕捉到取消诉求，主动释放资源退出
            current_job = self.store.get_job(job_id)
            if current_job and current_job.status == "cancel_requested":
                self.store.update_job_status(job_id, "cancelled", error="Cancelled gracefully by human request.")
                return

            # --- 模拟密集计算阶段二（例如发生暂时性网络异动或计算收敛失败） ---
            if job.payload.get("force_fail"):
                raise RuntimeError("Transient math convergence error.")

            # 成功跑完，交付成果大文件 Ref 指针
            artifact_ref = {"artifact_id": f"art_{job_id}", "uri": f"storage://macro/processed_{job_id}.csv"}
            self.store.update_job_status(job_id, "succeeded", result={"summary": "ARIMA rolling done.", "artifact_ref": artifact_ref})
            
        except Exception as e:
            # 3. 错误路径分水岭：检查是否可以执行指数退避重试
            if job.attempt_count < job.max_attempts:
                # 尚未耗尽天数，打回队列重新 queued，驱动下一次轮询，间接实现 Retry 机制
                self.store.update_job_status(job_id, "queued")
            else:
                # 耗尽重试次数，无药可救，打入终态失败
                self.store.update_job_status(job_id, "failed", error=str(e))
