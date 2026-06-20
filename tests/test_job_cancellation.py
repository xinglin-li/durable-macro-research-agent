# tests/test_job_cancellation.py
import pytest
import asyncio
from agent_runtime.jobs.store import SQLiteJobStore
from agent_runtime.jobs.worker import AsyncMacroJobWorker

@pytest.mark.asyncio
async def test_job_graceful_cancellation_via_heartbeat_checkpoint():
    """矩阵二：验证高危优雅取消。下发 cancel_requested 信号后，Worker 通过心跳自检卡点安全熔断"""
    store = SQLiteJobStore()
    worker = AsyncMacroJobWorker(store)
    await worker.start()
    
    try:
        # 1. 下发一个正常的任务
        job = store.submit_job(job_type="heavy_loop", idempotency_key="key_cancel", payload={"loop": True})
        
        # 2. 模拟任务正在运行中，客户端突然下发撤销判定
        store.update_job_status(job.job_id, "cancel_requested")
        
        # 给 Worker 的自检卡点留出一点时间做出自检反应
        await asyncio.sleep(0.08)
        
        # 3. 终极断言：任务没有被简单粗暴地彻底 delete 掉，而是由 Worker 善后清理后推进到了 cancelled 终态！
        final_job = store.get_job(job.job_id)
        assert final_job.status == "cancelled"
        assert "Cancelled gracefully" in final_job.error
        
    finally:
        await worker.stop()