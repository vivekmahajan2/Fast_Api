from pydantic import BaseModel, Field, EmailStr
from typing import List, Optional, Dict, Any, Literal
from datetime import datetime
from uuid import UUID

# -----------------------------------------------------------------------------
# Candidate Schemas
# -----------------------------------------------------------------------------
class CandidateProfileCreate(BaseModel):
    full_name: str
    email: EmailStr
    target_titles: List[str] = Field(default_factory=list)
    primary_skills: List[str] = Field(default_factory=list)
    secondary_skills: List[str] = Field(default_factory=list)
    experience_years: float = 0.0
    preferred_locations: List[str] = Field(default_factory=list)
    workplace_preferences: List[str] = Field(default_factory=lambda: ["remote"])
    resume_raw_text: Optional[str] = None
    bio: Optional[str] = None

class CandidateProfileResponse(CandidateProfileCreate):
    id: UUID
    created_at: datetime
    updated_at: datetime

# -----------------------------------------------------------------------------
# Job Fetch & Filter Schemas
# -----------------------------------------------------------------------------
class JobFetchRequest(BaseModel):
    keywords: List[str] = Field(default_factory=lambda: ["AI Engineer", "Machine Learning Engineer"])
    country: str = "India"
    workplace_type: Literal["remote", "hybrid", "on_site", "all"] = "remote"
    experience_level: List[str] = Field(default_factory=lambda: ["internship", "entry_level"])
    posted_within_days: int = Field(default=7, ge=1, le=30)
    limit: int = Field(default=50, ge=1, le=100)
    provider: Optional[str] = Field(default="auto", description="Provider to fetch from: 'auto', 'jsearch', 'remotive', or 'arbeitnow'")

class JobFetchResponse(BaseModel):
    status: str = "success"
    provider: str
    fetched_count: int
    new_inserted_count: int
    duplicate_count: int
    job_ids: List[str]
    message: Optional[str] = None

# -----------------------------------------------------------------------------
# Job Database Schemas
# -----------------------------------------------------------------------------
class JobItem(BaseModel):
    id: UUID
    external_job_id: str
    provider: str
    title: str
    company_name: str
    location: Optional[str] = None
    country: Optional[str] = None
    workplace_type: str
    experience_level: str
    description: str
    job_url: str
    salary_min: Optional[float] = None
    salary_max: Optional[float] = None
    salary_currency: Optional[str] = "USD"
    posted_at: Optional[datetime] = None
    status: str
    created_at: datetime
    updated_at: datetime

class JobListResponse(BaseModel):
    total: int
    items: List[JobItem]

# -----------------------------------------------------------------------------
# Match & Evaluation Schemas
# -----------------------------------------------------------------------------
class JobMatchRequest(BaseModel):
    job_ids: List[UUID] = Field(default_factory=list)
    candidate_id: Optional[UUID] = None
    force_reevaluate: bool = False

class MatchDetail(BaseModel):
    job_id: UUID
    overall_score: int
    skill_match_score: int
    experience_match_score: int
    matched_skills: List[str]
    missing_skills: List[str]
    reasoning: str
    tailored_pitch: Optional[str] = None
    recommended_action: str

class JobMatchResponse(BaseModel):
    evaluated_count: int
    results: List[MatchDetail]

# -----------------------------------------------------------------------------
# Status Update & Human Approval Schemas
# -----------------------------------------------------------------------------
class JobStatusUpdateRequest(BaseModel):
    status: Literal["new", "matched", "shortlisted", "approved", "applied", "rejected", "archived"]
    notes: Optional[str] = None

class JobApproveRequest(BaseModel):
    candidate_id: UUID
    approved: bool = True
    notes: Optional[str] = None
    trigger_auto_apply: bool = False

class JobApproveResponse(BaseModel):
    job_id: UUID
    status: str
    approval_id: UUID
    ready_for_application: bool
