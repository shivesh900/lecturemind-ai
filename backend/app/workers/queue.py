"""In-process background job queue with retries.

* Jobs are persisted in `processing_jobs`, so a restart re-queues anything that
  was queued or running.
* WORKER_CONCURRENCY workers pull from an asyncio queue; the API never blocks on
  transcription or AI calls.
* Retryable failures (AI timeouts, rate limits, transient errors) are retried
  up to JOB_MAX_ATTEMPTS with backoff; permanent ones (corrupt file, no speech)
  fail immediately with a clear message.

Swapping to Celery/RQ: call `run_job(job_id)` from a Celery task instead of
`JobQueue.enqueue`'s asyncio queue - the pipeline itself has no dependency on
this module. See README → "Scaling the worker".
"""
from __future__ import annotations

import asyncio
import logging

from bson import ObjectId

from ..core.config import get_settings
from ..core.database import get_db
from ..models.documents import new_steps, utcnow
from .pipeline import Pipeline, StepError

log = logging.getLogger(__name__)


async def create_job(db, lecture: dict, reset_steps: list[str] | None = None) -> ObjectId:
    now = utcnow()
    job = {"lecture_id": lecture["_id"], "user_id": lecture["user_id"], "status": "queued", "attempts": 0,
           "max_attempts": get_settings().job_max_attempts, "progress": lecture.get("progress", 0),
           "current_step": None, "error": None, "steps": {}, "created_at": now, "updated_at": now}
    res = await db.processing_jobs.insert_one(job)
    upd = {"status": "queued", "error": None, "job_id": res.inserted_id, "updated_at": now}
    if reset_steps is not None:
        steps = lecture.get("steps") or new_steps()
        for s in reset_steps:
            steps[s] = {"status": "pending", "error": None, "started_at": None, "finished_at": None}
        upd["steps"] = steps
    await db.lectures.update_one({"_id": lecture["_id"]}, {"$set": upd})
    return res.inserted_id


async def run_job(job_id: ObjectId, db=None) -> str:
    """Run one job to completion (including retries). Returns final status."""
    db = db if db is not None else get_db()
    job = await db.processing_jobs.find_one({"_id": job_id})
    if not job:
        return "missing"
    attempts = job.get("attempts", 0)
    max_attempts = job.get("max_attempts", 3)
    while True:
        attempts += 1
        await db.processing_jobs.update_one({"_id": job_id}, {"$set": {"status": "running", "attempts": attempts,
                                                                       "started_at": utcnow(), "error": None}})
        try:
            await Pipeline(db, job["lecture_id"], job_id).run()
            await db.processing_jobs.update_one({"_id": job_id}, {"$set": {"status": "completed", "progress": 100,
                                                                           "finished_at": utcnow()}})
            return "completed"
        except StepError as exc:
            final = (not exc.retryable) or attempts >= max_attempts
            await db.processing_jobs.update_one({"_id": job_id}, {"$set": {
                "status": "failed" if final else "retrying", "error": f"{exc.step}: {exc.message}",
                "updated_at": utcnow()}})
            if final:
                log.warning("Job %s failed permanently at %s: %s", job_id, exc.step, exc.message)
                return "failed"
            delay = min(60.0, get_settings().job_retry_base_seconds * attempts)
            log.info("Job %s retrying in %ss (attempt %d/%d)", job_id, delay, attempts, max_attempts)
            await db.lectures.update_one({"_id": job["lecture_id"]}, {"$set": {
                "status": "processing", "error": f"Retrying after error: {exc.message[:200]}"}})
            await asyncio.sleep(delay)
        except Exception as exc:  # pragma: no cover - defensive
            log.exception("Job %s crashed", job_id)
            await db.processing_jobs.update_one({"_id": job_id}, {"$set": {"status": "failed", "error": str(exc)[:300]}})
            await db.lectures.update_one({"_id": job["lecture_id"]}, {"$set": {"status": "failed",
                                                                                "error": "Processing crashed unexpectedly."}})
            return "failed"


class JobQueue:
    def __init__(self) -> None:
        self.queue: asyncio.Queue[ObjectId] = asyncio.Queue()
        self.workers: list[asyncio.Task] = []
        self.inline = False  # tests: run jobs synchronously on enqueue

    async def start(self) -> None:
        n = max(1, get_settings().worker_concurrency)
        self.workers = [asyncio.create_task(self._worker(i)) for i in range(n)]
        db = get_db()
        # recover jobs interrupted by a restart
        async for job in db.processing_jobs.find({"status": {"$in": ["queued", "running", "retrying"]}}).sort("created_at", 1):
            await db.processing_jobs.update_one({"_id": job["_id"]}, {"$set": {"status": "queued"}})
            await self.queue.put(job["_id"])
        log.info("Job queue started with %d worker(s)", n)

    async def stop(self) -> None:
        for w in self.workers:
            w.cancel()
        self.workers = []

    async def enqueue(self, job_id: ObjectId) -> None:
        if self.inline:
            await run_job(job_id)
        else:
            await self.queue.put(job_id)

    async def _worker(self, n: int) -> None:
        while True:
            job_id = await self.queue.get()
            try:
                await run_job(job_id)
            except asyncio.CancelledError:
                raise
            except Exception:  # pragma: no cover
                log.exception("worker %d: job %s crashed", n, job_id)
            finally:
                self.queue.task_done()


job_queue = JobQueue()
