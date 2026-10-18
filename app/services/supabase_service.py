from typing import List, Dict, Any, Optional
from uuid import uuid4
from datetime import datetime, timezone
from app.core.database import supabase

# Local in-memory fallback stores when Supabase is not connected
_MEMORY_CANDIDATE: Dict[str, Any] = {
    "id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
    "full_name": "AI Engineering Candidate",
    "email": "candidate@example.com",
    "target_titles": ["AI Engineer", "Machine Learning Engineer", "Python Backend Developer"],
    "primary_skills": ["Python", "FastAPI", "LangChain", "LangGraph", "Supabase", "PostgreSQL", "Docker"],
    "secondary_skills": ["PyTorch", "Vector Databases", "n8n", "Redis", "Git"],
    "experience_years": 1.5,
    "preferred_locations": ["India", "Remote"],
    "workplace_preferences": ["remote", "hybrid"],
    "bio": "AI Engineer specializing in agentic workflows, LLM orchestration, and scalable FastAPI backend services.",
    "created_at": datetime.now(timezone.utc).isoformat(),
    "updated_at": datetime.now(timezone.utc).isoformat()
}
_MEMORY_JOBS: Dict[str, Dict[str, Any]] = {}
_MEMORY_MATCHES: Dict[str, Dict[str, Any]] = {}
_MEMORY_APPROVALS: Dict[str, Dict[str, Any]] = {}

class SupabaseService:
    @staticmethod
    def get_default_candidate() -> Optional[Dict[str, Any]]:
        """Retrieves the primary candidate profile."""
        if supabase:
            try:
                response = supabase.table("candidate_profiles").select("*").limit(1).execute()
                if response.data:
                    return response.data[0]
            except Exception as e:
                print(f"Supabase query error: {e}")
        
        return _MEMORY_CANDIDATE

    @staticmethod
    def upsert_candidate_profile(data: Dict[str, Any]) -> Dict[str, Any]:
        """Creates or updates a candidate profile."""
        if supabase:
            try:
                response = supabase.table("candidate_profiles").upsert(data, on_conflict="email").execute()
                if response.data:
                    return response.data[0]
            except Exception as e:
                print(f"Supabase upsert error: {e}")

        # In-memory fallback
        data["id"] = data.get("id") or str(uuid4())
        data["updated_at"] = datetime.now(timezone.utc).isoformat()
        _MEMORY_CANDIDATE.update(data)
        return _MEMORY_CANDIDATE

    @staticmethod
    def insert_jobs_deduplicated(jobs_data: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Deduplicates jobs based on (provider, external_job_id) using Supabase or fallback store.
        Returns newly inserted count, duplicates, and list of inserted job IDs.
        """
        if not jobs_data:
            return {"fetched_count": 0, "new_inserted_count": 0, "duplicate_count": 0, "job_ids": []}

        provider = jobs_data[0].get("provider", "jsearch")

        if supabase:
            try:
                existing_pairs = set()
                providers = list({j.get("provider", "jsearch") for j in jobs_data})
                for prov in providers:
                    prov_ext_ids = [j["external_job_id"] for j in jobs_data if j.get("provider", "jsearch") == prov and "external_job_id" in j]
                    if prov_ext_ids:
                        existing_res = (
                            supabase.table("jobs")
                            .select("provider, external_job_id")
                            .eq("provider", prov)
                            .in_("external_job_id", prov_ext_ids)
                            .execute()
                        )
                        for row in (existing_res.data or []):
                            existing_pairs.add((row.get("provider"), row.get("external_job_id")))

                new_jobs = [j for j in jobs_data if (j.get("provider", "jsearch"), j.get("external_job_id")) not in existing_pairs]
                duplicate_count = len(jobs_data) - len(new_jobs)

                inserted_ids = []
                if new_jobs:
                    insert_res = supabase.table("jobs").insert(new_jobs).execute()
                    if insert_res.data:
                        inserted_ids = [row["id"] for row in insert_res.data]

                return {
                    "fetched_count": len(jobs_data),
                    "new_inserted_count": len(inserted_ids),
                    "duplicate_count": duplicate_count,
                    "job_ids": inserted_ids
                }
            except Exception as e:
                print(f"Supabase insert error: {e}. Falling back to in-memory store.")

        # In-memory fallback
        new_jobs = []
        duplicate_count = 0
        inserted_ids = []

        existing_pairs = {(j.get("provider", "jsearch"), j.get("external_job_id")) for j in _MEMORY_JOBS.values()}

        for j in jobs_data:
            prov = j.get("provider", "jsearch")
            ext_id = j.get("external_job_id")
            if (prov, ext_id) in existing_pairs:
                duplicate_count += 1
            else:
                job_id = str(uuid4())
                j["id"] = job_id
                j["created_at"] = datetime.now(timezone.utc).isoformat()
                j["updated_at"] = datetime.now(timezone.utc).isoformat()
                _MEMORY_JOBS[job_id] = j
                existing_pairs.add((prov, ext_id))
                inserted_ids.append(job_id)

        return {
            "fetched_count": len(jobs_data),
            "new_inserted_count": len(inserted_ids),
            "duplicate_count": duplicate_count,
            "job_ids": inserted_ids
        }

    @staticmethod
    def list_jobs(
        status: Optional[str] = None,
        workplace_type: Optional[str] = None,
        min_score: Optional[int] = None,
        limit: int = 20,
        offset: int = 0
    ) -> Dict[str, Any]:
        """Queries stored jobs with optional filtering and pagination."""
        if supabase:
            try:
                query = supabase.table("jobs").select("*, job_matches(overall_score, skill_match_score, recommended_action)", count="exact")
                if status:
                    query = query.eq("status", status)
                if workplace_type and workplace_type != "all":
                    query = query.eq("workplace_type", workplace_type)

                query = query.order("created_at", desc=True).range(offset, offset + limit - 1)
                response = query.execute()
                items = response.data or []

                if min_score is not None:
                    filtered = []
                    for item in items:
                        matches = item.get("job_matches") or []
                        if matches and matches[0].get("overall_score", 0) >= min_score:
                            filtered.append(item)
                    items = filtered

                return {
                    "total": response.count if response.count is not None else len(items),
                    "items": items
                }
            except Exception as e:
                print(f"Supabase list error: {e}. Falling back to in-memory store.")

        # In-memory fallback
        items = list(_MEMORY_JOBS.values())
        if status:
            items = [j for j in items if j.get("status") == status]
        if workplace_type and workplace_type != "all":
            items = [j for j in items if j.get("workplace_type") == workplace_type]
        if min_score is not None:
            items = [j for j in items if _MEMORY_MATCHES.get(j["id"], {}).get("overall_score", 0) >= min_score]

        for j in items:
            match = _MEMORY_MATCHES.get(j["id"])
            j["job_matches"] = [match] if match else []

        total = len(items)
        paginated = items[offset: offset + limit]
        return {"total": total, "items": paginated}

    @staticmethod
    def get_job_by_id(job_id: str) -> Optional[Dict[str, Any]]:
        """Retrieves a single job with its match report."""
        if supabase:
            try:
                response = (
                    supabase.table("jobs")
                    .select("*, job_matches(*)")
                    .eq("id", job_id)
                    .limit(1)
                    .execute()
                )
                if response.data:
                    return response.data[0]
            except Exception as e:
                print(f"Supabase get error: {e}")

        # In-memory fallback
        job = _MEMORY_JOBS.get(job_id)
        if job:
            job_copy = dict(job)
            match = _MEMORY_MATCHES.get(job_id)
            job_copy["job_matches"] = [match] if match else []
            return job_copy
        return None

    @staticmethod
    def update_job_status(job_id: str, new_status: str) -> Optional[Dict[str, Any]]:
        """Updates the status of a job."""
        if supabase:
            try:
                response = (
                    supabase.table("jobs")
                    .update({"status": new_status, "updated_at": datetime.now(timezone.utc).isoformat()})
                    .eq("id", job_id)
                    .execute()
                )
                if response.data:
                    return response.data[0]
            except Exception as e:
                print(f"Supabase update error: {e}")

        # In-memory fallback
        job = _MEMORY_JOBS.get(job_id)
        if job:
            job["status"] = new_status
            job["updated_at"] = datetime.now(timezone.utc).isoformat()
            return job
        return None

    @staticmethod
    def record_approval(job_id: str, candidate_id: str, approved: bool, notes: Optional[str] = None) -> Dict[str, Any]:
        """Records human-in-the-loop approval and transitions job status."""
        new_status = "approved" if approved else "rejected"
        approval_id = str(uuid4())
        
        approval_payload = {
            "id": approval_id,
            "job_id": job_id,
            "candidate_id": candidate_id,
            "approved": approved,
            "approval_notes": notes,
            "submission_status": "pending" if approved else "cancelled",
            "approved_at": datetime.now(timezone.utc).isoformat()
        }

        if supabase:
            try:
                supabase.table("application_approvals").insert(approval_payload).execute()
                SupabaseService.update_job_status(job_id, new_status)
                return {
                    "job_id": job_id,
                    "status": new_status,
                    "approval_id": approval_id,
                    "ready_for_application": approved
                }
            except Exception as e:
                print(f"Supabase approval error: {e}")

        # In-memory fallback
        _MEMORY_APPROVALS[approval_id] = approval_payload
        SupabaseService.update_job_status(job_id, new_status)
        return {
            "job_id": job_id,
            "status": new_status,
            "approval_id": approval_id,
            "ready_for_application": approved
        }

    @staticmethod
    def save_job_match(match_data: Dict[str, Any]) -> Dict[str, Any]:
        """Saves or updates a match score evaluation."""
        job_id = match_data.get("job_id")
        if supabase:
            try:
                response = (
                    supabase.table("job_matches")
                    .upsert(match_data, on_conflict="job_id,candidate_id")
                    .execute()
                )
                if job_id:
                    supabase.table("jobs").update({"status": "matched"}).eq("id", job_id).eq("status", "new").execute()
                if response.data:
                    return response.data[0]
            except Exception as e:
                print(f"Supabase save match error: {e}")

        # In-memory fallback
        if job_id:
            _MEMORY_MATCHES[job_id] = match_data
            if job_id in _MEMORY_JOBS and _MEMORY_JOBS[job_id].get("status") == "new":
                _MEMORY_JOBS[job_id]["status"] = "matched"
        return match_data
