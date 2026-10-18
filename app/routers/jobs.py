from fastapi import APIRouter, HTTPException, Query, status
from typing import Optional, List, Dict, Any
from uuid import UUID
from datetime import datetime, timezone
import asyncio
import httpx

from app.models.schemas import (
    JobFetchRequest, JobFetchResponse,
    JobStatusUpdateRequest,
    JobApproveRequest, JobApproveResponse,
    JobMatchRequest, JobMatchResponse, MatchDetail
)
from app.services.supabase_service import SupabaseService
from app.services.job_fetcher import JobFetcherService
from app.core.config import settings
from app.agent.groq_matcher import GroqMatchEngine

router = APIRouter(prefix="/api/jobs", tags=["Jobs"])

@router.post("/fetch", response_model=JobFetchResponse)
async def fetch_jobs(payload: JobFetchRequest):
    """
    Fetch jobs from authorized provider (JSearch via RapidAPI) or free live tech job boards
    (Remotive, Arbeitnow), translates filters, deduplicates records against Supabase, and inserts new jobs.
    """
    raw_jobs, active_provider, info_message = await JobFetcherService.fetch_jobs(payload)

    # Ingest into Supabase with automatic deduplication
    result = SupabaseService.insert_jobs_deduplicated(raw_jobs)
    return JobFetchResponse(
        status="success",
        provider=active_provider,
        fetched_count=result["fetched_count"],
        new_inserted_count=result["new_inserted_count"],
        duplicate_count=result["duplicate_count"],
        job_ids=result["job_ids"],
        message=info_message
    )

@router.get("", response_model=Dict[str, Any])
async def list_jobs(
    status: Optional[str] = Query(None, description="Filter by status (new, matched, shortlisted, approved, etc.)"),
    workplace_type: Optional[str] = Query(None, description="Filter by workplace type (remote, hybrid, on_site)"),
    min_score: Optional[int] = Query(None, ge=0, le=100, description="Minimum overall match score"),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0)
):
    """Retrieve saved jobs with filters and pagination from Supabase."""
    return SupabaseService.list_jobs(
        status=status,
        workplace_type=workplace_type,
        min_score=min_score,
        limit=limit,
        offset=offset
    )

@router.get("/{job_id}", response_model=Dict[str, Any])
async def get_job_details(job_id: str):
    """Get one job's details along with its match evaluation from Supabase."""
    job = SupabaseService.get_job_by_id(job_id)
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Job with id {job_id} not found."
        )
    return job

@router.post("/match", response_model=JobMatchResponse)
async def match_jobs(payload: JobMatchRequest):
    """
    Calculate candidate-job match score and skill breakdown using candidate profile and job description.
    Persists evaluation in Supabase job_matches table.
    """
    # 1. Fetch candidate profile
    candidate = SupabaseService.get_default_candidate()
    if not candidate:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No candidate profile configured. Create a profile at POST /api/candidates/profile first."
        )
    candidate_id = candidate["id"]
    candidate_skills = [s.lower() for s in (candidate.get("primary_skills") or []) + (candidate.get("secondary_skills") or [])]

    # 2. Identify target jobs
    job_ids_to_process = [str(jid) for jid in payload.job_ids]
    if not job_ids_to_process:
        # Default: process recently added 'new' jobs
        recent_jobs = SupabaseService.list_jobs(status="new", limit=10)
        job_ids_to_process = [j["id"] for j in recent_jobs.get("items", [])]

    async def _evaluate_single(jid: str) -> Optional[MatchDetail]:
        job = SupabaseService.get_job_by_id(jid)
        if not job:
            return None

        # Evaluate candidate-job fit using Groq LLM asynchronously
        eval_output = await GroqMatchEngine.async_evaluate_fit(candidate=candidate, job=job)

        match_record = {
            "job_id": jid,
            "candidate_id": candidate_id,
            "overall_score": eval_output["overall_score"],
            "skill_match_score": eval_output["skill_match_score"],
            "experience_match_score": eval_output["experience_match_score"],
            "matched_skills": eval_output.get("matched_skills", []),
            "missing_skills": eval_output.get("missing_skills", []),
            "reasoning": eval_output["reasoning"],
            "tailored_pitch": eval_output.get("tailored_pitch"),
            "recommended_action": eval_output["recommended_action"]
        }

        # Persist in Supabase
        SupabaseService.save_job_match(match_record)

        return MatchDetail(
            job_id=UUID(jid),
            overall_score=eval_output["overall_score"],
            skill_match_score=eval_output["skill_match_score"],
            experience_match_score=eval_output["experience_match_score"],
            matched_skills=eval_output.get("matched_skills", []),
            missing_skills=eval_output.get("missing_skills", []),
            reasoning=eval_output["reasoning"],
            tailored_pitch=eval_output.get("tailored_pitch"),
            recommended_action=eval_output["recommended_action"]
        )

    tasks = [_evaluate_single(jid) for jid in job_ids_to_process]
    raw_results = await asyncio.gather(*tasks)
    match_results = [r for r in raw_results if r is not None]

    return JobMatchResponse(
        evaluated_count=len(match_results),
        results=match_results
    )

@router.patch("/{job_id}/status", response_model=Dict[str, Any])
async def update_status(job_id: str, payload: JobStatusUpdateRequest):
    """Update job status (saved, shortlisted, applied, rejected, etc.) in Supabase."""
    updated = SupabaseService.update_job_status(job_id, payload.status)
    if not updated:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Job with id {job_id} not found."
        )
    return {
        "id": job_id,
        "status": payload.status,
        "message": f"Job status updated to '{payload.status}' in Supabase"
    }

@router.post("/{job_id}/approve", response_model=JobApproveResponse)
async def approve_job(job_id: str, payload: JobApproveRequest):
    """
    Record human-in-the-loop approval before an external application action.
    Saves approval in application_approvals and sets jobs.status = 'approved'.
    """
    result = SupabaseService.record_approval(
        job_id=job_id,
        candidate_id=str(payload.candidate_id),
        approved=payload.approved,
        notes=payload.notes
    )
    return JobApproveResponse(
        job_id=UUID(result["job_id"]),
        status=result["status"],
        approval_id=UUID(result["approval_id"]) if result.get("approval_id") else UUID("00000000-0000-0000-0000-000000000000"),
        ready_for_application=result["ready_for_application"]
    )
