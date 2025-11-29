"""
Jobs Router (Use Cases 3 & 4)
Handles watchdog jobs and 115 life event monitoring.
"""

import logging
from typing import List, Optional

from fastapi import APIRouter, HTTPException, Depends, Query
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from ..core.database import get_db
from ..models.schemas import Job, JobStatus, StorageType, ConfidenceLevel
from ..models.db_models import JobDB

logger = logging.getLogger(__name__)
router = APIRouter()


class CreateJobRequest(BaseModel):
    """Request to create a monitoring job"""
    name: str
    job_type: str  # watchdog or life_event
    source_path: str
    storage_type: StorageType
    default_rule_ids: Optional[List[str]] = None
    auto_approve: bool = False
    confidence_threshold: ConfidenceLevel = ConfidenceLevel.HIGH
    poll_interval: int = 60  # For watchdog
    event_types: Optional[List[str]] = None  # For life_event


class UpdateJobRequest(BaseModel):
    """Request to update a job"""
    name: Optional[str] = None
    default_rule_ids: Optional[List[str]] = None
    auto_approve: Optional[bool] = None
    confidence_threshold: Optional[ConfidenceLevel] = None
    enabled: Optional[bool] = None
    poll_interval: Optional[int] = None
    event_types: Optional[List[str]] = None


class JobResponse(BaseModel):
    """Job response"""
    id: str
    name: str
    job_type: str
    source_path: str
    storage_type: StorageType
    auto_approve: bool
    confidence_threshold: ConfidenceLevel
    enabled: bool
    status: JobStatus
    poll_interval: int
    event_types: Optional[List[str]] = None
    
    class Config:
        from_attributes = True


class JobListResponse(BaseModel):
    """Response for job listing"""
    jobs: List[JobResponse]
    total: int


@router.get("/", response_model=JobListResponse)
async def list_jobs(
    job_type: Optional[str] = None,
    storage_type: Optional[StorageType] = None,
    enabled_only: bool = False,
    db: AsyncSession = Depends(get_db)
):
    """
    List all monitoring jobs.
    
    Optionally filter by job type, storage type, or enabled status.
    """
    query = select(JobDB)
    
    if job_type:
        query = query.where(JobDB.job_type == job_type)
    if storage_type:
        query = query.where(JobDB.storage_type == storage_type.value)
    if enabled_only:
        query = query.where(JobDB.enabled == True)
    
    result = await db.execute(query)
    jobs = result.scalars().all()
    
    return JobListResponse(
        jobs=[JobResponse.model_validate(j) for j in jobs],
        total=len(jobs)
    )


@router.post("/", response_model=JobResponse)
async def create_job(
    request: CreateJobRequest,
    db: AsyncSession = Depends(get_db)
):
    """
    Create a new monitoring job.
    
    Job types:
    - watchdog: Monitors local/FUSE paths for file changes
    - life_event: Monitors 115 cloud life events
    """
    # Validate job type and storage type combination
    if request.job_type == "watchdog" and request.storage_type != StorageType.LOCAL:
        raise HTTPException(
            status_code=400,
            detail="Watchdog jobs only support local storage type"
        )
    
    if request.job_type == "life_event" and request.storage_type != StorageType.P115:
        raise HTTPException(
            status_code=400,
            detail="Life event jobs only support p115 storage type"
        )
    
    # Create job
    job = JobDB(
        name=request.name,
        job_type=request.job_type,
        source_path=request.source_path,
        storage_type=request.storage_type.value,
        default_rule_ids=request.default_rule_ids,
        auto_approve=request.auto_approve,
        confidence_threshold=request.confidence_threshold.value,
        poll_interval=request.poll_interval,
        event_types=request.event_types,
        enabled=True,
        status=JobStatus.ACTIVE.value
    )
    
    db.add(job)
    await db.commit()
    await db.refresh(job)
    
    return JobResponse.model_validate(job)


@router.get("/{job_id}", response_model=JobResponse)
async def get_job(
    job_id: str,
    db: AsyncSession = Depends(get_db)
):
    """Get a specific job by ID"""
    result = await db.execute(select(JobDB).where(JobDB.id == job_id))
    job = result.scalar_one_or_none()
    
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    
    return JobResponse.model_validate(job)


@router.put("/{job_id}", response_model=JobResponse)
async def update_job(
    job_id: str,
    request: UpdateJobRequest,
    db: AsyncSession = Depends(get_db)
):
    """Update a job"""
    result = await db.execute(select(JobDB).where(JobDB.id == job_id))
    job = result.scalar_one_or_none()
    
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    
    # Update fields
    if request.name is not None:
        job.name = request.name
    if request.default_rule_ids is not None:
        job.default_rule_ids = request.default_rule_ids
    if request.auto_approve is not None:
        job.auto_approve = request.auto_approve
    if request.confidence_threshold is not None:
        job.confidence_threshold = request.confidence_threshold.value
    if request.enabled is not None:
        job.enabled = request.enabled
    if request.poll_interval is not None:
        job.poll_interval = request.poll_interval
    if request.event_types is not None:
        job.event_types = request.event_types
    
    await db.commit()
    await db.refresh(job)
    
    return JobResponse.model_validate(job)


@router.delete("/{job_id}")
async def delete_job(
    job_id: str,
    db: AsyncSession = Depends(get_db)
):
    """Delete a job"""
    result = await db.execute(select(JobDB).where(JobDB.id == job_id))
    job = result.scalar_one_or_none()
    
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    
    await db.delete(job)
    await db.commit()
    
    return {"message": "Job deleted successfully"}


@router.post("/{job_id}/start")
async def start_job(
    job_id: str,
    db: AsyncSession = Depends(get_db)
):
    """Start a job"""
    result = await db.execute(select(JobDB).where(JobDB.id == job_id))
    job = result.scalar_one_or_none()
    
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    
    job.enabled = True
    job.status = JobStatus.ACTIVE.value
    await db.commit()
    
    # TODO: Actually start the job in scheduler
    
    return {"message": "Job started", "status": job.status}


@router.post("/{job_id}/stop")
async def stop_job(
    job_id: str,
    db: AsyncSession = Depends(get_db)
):
    """Stop a job"""
    result = await db.execute(select(JobDB).where(JobDB.id == job_id))
    job = result.scalar_one_or_none()
    
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    
    job.status = JobStatus.PAUSED.value
    await db.commit()
    
    # TODO: Actually stop the job in scheduler
    
    return {"message": "Job stopped", "status": job.status}


@router.get("/{job_id}/history")
async def get_job_history(
    job_id: str,
    limit: int = Query(default=50, le=200),
    offset: int = 0,
    db: AsyncSession = Depends(get_db)
):
    """Get transfer history for a job"""
    from ..models.db_models import TransferHistoryDB
    
    result = await db.execute(select(JobDB).where(JobDB.id == job_id))
    job = result.scalar_one_or_none()
    
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    
    # Get transfer history
    query = select(TransferHistoryDB).where(
        TransferHistoryDB.job_id == job_id
    ).order_by(
        TransferHistoryDB.created_at.desc()
    ).offset(offset).limit(limit)
    
    result = await db.execute(query)
    history = result.scalars().all()
    
    return {
        "job_id": job_id,
        "history": history,
        "limit": limit,
        "offset": offset
    }

