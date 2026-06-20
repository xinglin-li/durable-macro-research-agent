# tests/test_job_worker.py
import pytest
import asyncio
from agent_runtime.jobs.store import SQLiteJobStore
from agent_runtime.jobs.worker import AsyncMacroJobWorker

@pytest.mark.asyncio
async def test_job_store_idempotency_and_retry_backoff_lifecycle():
    """矩阵一：验证强幂等主键拦截、分布式重试耗尽走向失败的完整生命周期"""
    store = SQLiteJobStore()
    worker = AsyncMacroJobWorker(store)
    await worker.start()
    
    try:
        # 1. 强幂等防线测试：使用相同的 key 连续提交两次分析任务
        job_v1 = store.submit_job(job_type="arima", idempotency_key="key_cpi_2026", payload={"series": "CPI"})
        job_v2 = store.submit_job(job_type="arima", idempotency_key="key_cpi_2026", payload={"series": "CPI"})
        
        # 验证第二次提交被拦截，直接返回了第一次创建的任务 ID，严防重复计算
        assert job_v1.job_id == job_v2.job_id
        
        # 2. 故障注入与重试测试：下发一个注定会由于数学收敛失败的任务，设置 max_attempts=2
        fail_job = store.submit_job(job_type="backtest", idempotency_key="key_fail", payload={"force_fail": True})
        fail_job.max_attempts = 2
        
        # 等待后台 Worker 领取、失败重试并最终打入失败终态
        await asyncio.sleep(0.1)
        
        final_job = store.get_job(fail_job.job_id)
        assert final_job.status == "failed"
        # 验证其在彻底倒下前，确实顽强地执行了 2 次抓取重跑
        assert final_job.attempt_count == 2
        assert "convergence error" in final_job.error
        
    finally:
        await worker.stop()