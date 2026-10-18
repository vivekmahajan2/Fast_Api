import re
import logging
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional, Tuple
import httpx

from app.core.config import settings
from app.models.schemas import JobFetchRequest

logger = logging.getLogger(__name__)

VALID_WORKPLACE_TYPES = {"remote", "hybrid", "on_site", "unspecified"}
VALID_EXP_LEVELS = {"internship", "entry_level", "associate", "mid_senior", "director", "executive", "unspecified"}

def clean_html(raw_html: Optional[str]) -> str:
    """Removes HTML tags and normalizes whitespace."""
    if not raw_html:
        return ""
    text = re.sub(r"<[^>]+>", " ", raw_html)
    text = re.sub(r"&[a-zA-Z0-9#]+;", " ", text)
    return " ".join(text.split())

def keyword_matches_text(kw: str, text: str) -> bool:
    """Checks whether keyword appears as a whole word or phrase in text."""
    if not kw or not text:
        return False
    return bool(re.search(r"\b" + re.escape(kw.strip()) + r"\b", text, re.IGNORECASE))

def normalize_workplace_type(value: Optional[str]) -> str:
    if not value:
        return "unspecified"
    val = value.strip().lower()
    if val in VALID_WORKPLACE_TYPES:
        return val
    if "remote" in val:
        return "remote"
    if "hybrid" in val:
        return "hybrid"
    if "site" in val or "office" in val:
        return "on_site"
    return "unspecified"

def normalize_experience_level(value: Optional[str]) -> str:
    if not value:
        return "unspecified"
    val = value.strip().lower()
    if val in VALID_EXP_LEVELS:
        return val
    if "intern" in val:
        return "internship"
    if "entry" in val or "junior" in val or "grad" in val:
        return "entry_level"
    if "mid" in val or "senior" in val:
        return "mid_senior"
    if "lead" in val or "director" in val:
        return "director"
    return "unspecified"


class JobFetcherService:
    @classmethod
    async def fetch_jobs(cls, payload: JobFetchRequest) -> Tuple[List[Dict[str, Any]], str, Optional[str]]:
        """
        Coordinates fetching jobs from authorized providers (JSearch) or free live sources
        (Remotive, Arbeitnow) with automatic fallback and error reporting.
        Returns: (raw_jobs, provider_used, status_message)
        """
        target_provider = (payload.provider or "auto").lower()
        jobs: List[Dict[str, Any]] = []
        error_notes: List[str] = []

        # 1. Try JSearch if requested or auto
        if target_provider in ("auto", "jsearch") and settings.RAPIDAPI_KEY:
            jsearch_jobs, jsearch_err = await cls._fetch_from_jsearch(payload)
            if jsearch_jobs:
                return jsearch_jobs, "jsearch", None
            if jsearch_err:
                error_notes.append(f"JSearch: {jsearch_err}")

        # 2. Try Remotive (free live remote jobs feed)
        if target_provider in ("auto", "remotive"):
            remotive_jobs, rem_err = await cls._fetch_from_remotive(payload)
            if remotive_jobs:
                note = None
                if error_notes:
                    note = f"Notice: {'; '.join(error_notes)}. Extracted {len(remotive_jobs)} live jobs from Remotive."
                return remotive_jobs, "remotive", note
            if rem_err:
                error_notes.append(f"Remotive: {rem_err}")

        # 3. Try Arbeitnow (free live tech jobs feed)
        if target_provider in ("auto", "arbeitnow"):
            arbeitnow_jobs, arb_err = await cls._fetch_from_arbeitnow(payload)
            if arbeitnow_jobs:
                note = None
                if error_notes:
                    note = f"Notice: {'; '.join(error_notes)}. Extracted {len(arbeitnow_jobs)} live jobs from Arbeitnow."
                return arbeitnow_jobs, "arbeitnow", note
            if arb_err:
                error_notes.append(f"Arbeitnow: {arb_err}")

        # 4. Fallback simulation if all live providers fail or return 0
        exp_level = payload.experience_level[0] if payload.experience_level else "entry_level"
        for idx, kw in enumerate(payload.keywords):
            jobs.append({
                "external_job_id": f"mock_{int(datetime.now(timezone.utc).timestamp())}_{idx}",
                "provider": "mock_provider",
                "title": f"Junior {kw}",
                "company_name": f"NextGen {kw} Tech Labs",
                "location": f"{payload.country} (Remote)",
                "country": payload.country,
                "workplace_type": normalize_workplace_type(payload.workplace_type),
                "experience_level": normalize_experience_level(exp_level),
                "description": f"We are seeking a high-potential {kw} to join our agile AI engineering team. Experience with Python, FastAPI, and LangChain is highly preferred.",
                "job_url": f"https://careers.example.com/{kw.lower().replace(' ', '-')}",
                "salary_min": 700000,
                "salary_max": 1100000,
                "salary_currency": "INR" if payload.country.lower() == "india" else "USD",
                "posted_at": datetime.now(timezone.utc).isoformat(),
                "status": "new",
                "raw_payload": {"source": "mock_fallback"}
            })

        fallback_msg = "Live providers unavailable"
        if error_notes:
            fallback_msg = f"{'; '.join(error_notes)}. Generated mock fallback."
        return jobs, "mock_provider", fallback_msg

    @classmethod
    async def _fetch_from_jsearch(cls, payload: JobFetchRequest) -> Tuple[List[Dict[str, Any]], Optional[str]]:
        query_str = " ".join(payload.keywords)
        if payload.country:
            query_str += f" in {payload.country}"
        if payload.workplace_type == "remote":
            query_str += " remote"

        url = "https://jsearch.p.rapidapi.com/search"
        headers = {
            "x-rapidapi-key": settings.RAPIDAPI_KEY,
            "x-rapidapi-host": "jsearch.p.rapidapi.com"
        }
        params = {
            "query": query_str,
            "page": "1",
            "num_pages": "1",
            "date_posted": "week" if payload.posted_within_days <= 7 else "month"
        }

        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(url, headers=headers, params=params, timeout=15.0)
                if response.status_code == 200:
                    api_data = response.json()
                    raw_items = api_data.get("data", [])
                    exp_level = payload.experience_level[0] if payload.experience_level else "entry_level"

                    parsed_jobs = []
                    for item in raw_items[:payload.limit]:
                        parsed_jobs.append({
                            "external_job_id": str(item.get("job_id")),
                            "provider": "jsearch",
                            "title": item.get("job_title", "Untitled"),
                            "company_name": item.get("employer_name", "Unknown Company"),
                            "location": f"{item.get('job_city', '')}, {item.get('job_country', '')}".strip(", ") or "Remote",
                            "country": item.get("job_country") or payload.country,
                            "workplace_type": "remote" if item.get("job_is_remote") else "on_site",
                            "experience_level": normalize_experience_level(exp_level),
                            "description": clean_html(item.get("job_description", "")),
                            "job_url": item.get("job_apply_link", ""),
                            "salary_min": item.get("job_min_salary"),
                            "salary_max": item.get("job_max_salary"),
                            "salary_currency": item.get("job_salary_currency", "USD"),
                            "posted_at": item.get("job_posted_at_datetime_utc"),
                            "status": "new",
                            "raw_payload": item
                        })
                    return parsed_jobs, None
                elif response.status_code == 403:
                    msg = "RapidAPI key is not subscribed to JSearch. Please subscribe at https://rapidapi.com/letscrape-6bRBa3qguO5/api/jsearch (free plan available)."
                    logger.warning(msg)
                    return [], msg
                else:
                    msg = f"HTTP {response.status_code}: {response.text[:200]}"
                    logger.warning(f"JSearch error: {msg}")
                    return [], msg
        except Exception as e:
            logger.error(f"JSearch exception: {e}")
            return [], str(e)

    @classmethod
    async def _fetch_from_remotive(cls, payload: JobFetchRequest) -> Tuple[List[Dict[str, Any]], Optional[str]]:
        """Fetches from Remotive's free public remote jobs API."""
        try:
            search_term = " ".join(payload.keywords)
            url = "https://remotive.com/api/remote-jobs"
            params = {"search": search_term, "limit": str(payload.limit)}

            async with httpx.AsyncClient() as client:
                res = await client.get(url, params=params, timeout=12.0)
                if res.status_code != 200:
                    return [], f"HTTP {res.status_code}"

                data = res.json()
                items = data.get("jobs", [])
                if not items:
                    # Try software-dev category if keyword search returned 0
                    res = await client.get(url, params={"category": "software-dev", "limit": str(payload.limit)}, timeout=12.0)
                    if res.status_code == 200:
                        items = res.json().get("jobs", [])

                # Filter Remotive jobs strictly against candidate keywords
                keywords = [k.lower().strip() for k in payload.keywords if k.strip()]
                matched_items = []
                for item in items:
                    title_text = item.get("title", "").lower()
                    desc_text = item.get("description", "").lower()
                    tags_text = " ".join(item.get("tags", [])).lower()
                    corpus = f"{title_text} {desc_text} {tags_text}"
                    if any(keyword_matches_text(kw, corpus) for kw in keywords):
                        matched_items.append(item)

                if not matched_items:
                    return [], "No Remotive postings matched keywords."

                parsed_jobs = []
                for item in matched_items[:payload.limit]:
                    title = item.get("title", "Untitled")
                    desc = clean_html(item.get("description", ""))
                    loc = item.get("candidate_required_location") or "Worldwide (Remote)"

                    # Infer experience level from title
                    exp_level = "entry_level"
                    title_lower = title.lower()
                    if "senior" in title_lower or "lead" in title_lower or "principal" in title_lower:
                        exp_level = "mid_senior"
                    elif "intern" in title_lower:
                        exp_level = "internship"

                    parsed_jobs.append({
                        "external_job_id": f"remotive_{item.get('id')}",
                        "provider": "remotive",
                        "title": title,
                        "company_name": item.get("company_name", "Unknown Company"),
                        "location": loc,
                        "country": payload.country if payload.country else "Remote",
                        "workplace_type": "remote",
                        "experience_level": exp_level,
                        "description": desc,
                        "job_url": item.get("url", ""),
                        "salary_min": None,
                        "salary_max": None,
                        "salary_currency": "USD",
                        "posted_at": item.get("publication_date"),
                        "status": "new",
                        "raw_payload": item
                    })
                return parsed_jobs, None
        except Exception as e:
            logger.error(f"Remotive fetch error: {e}")
            return [], str(e)

    @classmethod
    async def _fetch_from_arbeitnow(cls, payload: JobFetchRequest) -> Tuple[List[Dict[str, Any]], Optional[str]]:
        """Fetches from Arbeitnow's free public job board API."""
        try:
            url = "https://www.arbeitnow.com/api/job-board-api"
            async with httpx.AsyncClient() as client:
                res = await client.get(url, timeout=12.0)
                if res.status_code != 200:
                    return [], f"HTTP {res.status_code}"

                items = res.json().get("data", [])
                keywords = [k.lower().strip() for k in payload.keywords if k.strip()]

                # Filter by keyword in title, description, or tags
                matched = []
                for item in items:
                    title_lower = item.get("title", "").lower()
                    tags_lower = " ".join(item.get("tags", [])).lower()
                    desc_lower = item.get("description", "").lower()
                    corpus = f"{title_lower} {tags_lower} {desc_lower}"
                    if any(keyword_matches_text(kw, title_lower) or keyword_matches_text(kw, tags_lower) or keyword_matches_text(kw, corpus) for kw in keywords):
                        if payload.workplace_type == "remote" and not item.get("remote"):
                            continue
                        matched.append(item)

                if not matched:
                    return [], "No Arbeitnow postings matched candidate keywords."

                parsed_jobs = []
                for item in matched[:payload.limit]:
                    title = item.get("title", "Untitled")
                    desc = clean_html(item.get("description", ""))
                    is_remote = bool(item.get("remote"))

                    exp_level = "entry_level"
                    title_lower = title.lower()
                    if "senior" in title_lower or "lead" in title_lower:
                        exp_level = "mid_senior"
                    elif "intern" in title_lower:
                        exp_level = "internship"

                    parsed_jobs.append({
                        "external_job_id": f"arbeitnow_{item.get('slug')}",
                        "provider": "arbeitnow",
                        "title": title,
                        "company_name": item.get("company_name", "Unknown Company"),
                        "location": item.get("location") or ("Remote" if is_remote else "On-site"),
                        "country": payload.country,
                        "workplace_type": "remote" if is_remote else "on_site",
                        "experience_level": exp_level,
                        "description": desc,
                        "job_url": item.get("url", ""),
                        "salary_min": None,
                        "salary_max": None,
                        "salary_currency": "EUR",
                        "posted_at": datetime.fromtimestamp(item.get("created_at", 0), tz=timezone.utc).isoformat() if item.get("created_at") else None,
                        "status": "new",
                        "raw_payload": item
                    })
                return parsed_jobs, None
        except Exception as e:
            logger.error(f"Arbeitnow fetch error: {e}")
            return [], str(e)
