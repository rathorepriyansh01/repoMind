from fastapi import APIRouter, BackgroundTasks, HTTPException, Request
from pydantic import BaseModel, Field

from app.config import get_settings
from app.rate_limit import client_ip, limiter
from app.services.pipeline import run_analysis_job
from app.services.store import create_job, get_job

router = APIRouter()


class AnalyzeRequest(BaseModel):
    url: str = Field(min_length=8, max_length=500)
    force: bool = False


@router.post("/api/v1/analyze")
async def analyze(req: AnalyzeRequest, request: Request, background_tasks: BackgroundTasks):
    settings = get_settings()
    limiter.check(f"analyze:{client_ip(request)}", settings.analyze_rate_limit, settings.analyze_rate_window_seconds)
    job_id = await create_job()
    background_tasks.add_task(run_analysis_job, job_id, req.url.strip(), req.force)
    return {"job_id": job_id, "status": "queued"}


@router.get("/api/v1/jobs/{job_id}")
async def job_status(job_id: str):
    job = await get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found.")
    return {
        "job_id": job["id"],
        "status": job["status"],
        "progress": job["progress"],
        "error": job["error"],
        "repository_id": job["repository_id"],
    }
