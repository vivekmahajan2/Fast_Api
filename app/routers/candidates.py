from fastapi import APIRouter, HTTPException, status
from typing import Dict, Any
from app.models.schemas import CandidateProfileCreate, CandidateProfileResponse
from app.services.supabase_service import SupabaseService

router = APIRouter(prefix="/api/candidates", tags=["Candidates"])

@router.get("/profile", response_model=Dict[str, Any])
async def get_candidate_profile():
    """Retrieve the primary candidate profile from Supabase."""
    candidate = SupabaseService.get_default_candidate()
    if not candidate:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No candidate profile found. Please create one first."
        )
    return candidate

@router.post("/profile", response_model=Dict[str, Any])
async def create_or_update_profile(profile: CandidateProfileCreate):
    """Create or update candidate profile in Supabase."""
    data = profile.model_dump()
    result = SupabaseService.upsert_candidate_profile(data)
    return {
        "status": "success",
        "message": "Candidate profile saved successfully in Supabase",
        "data": result
    }
