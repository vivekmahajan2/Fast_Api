import json
import logging
from typing import Dict, Any, List, Optional
from app.core.config import settings

logger = logging.getLogger(__name__)

class GroqMatchEngine:
    """
    Evaluates candidate-job fit using Groq's high-speed LPU inference API
    (e.g., llama-3.3-70b-versatile or llama-3.1-8b-instant).
    """

    @classmethod
    def evaluate_fit(cls, candidate: Dict[str, Any], job: Dict[str, Any]) -> Dict[str, Any]:
        """
        Runs LLM evaluation via Groq with structured JSON output.
        Falls back to rule-based evaluation if Groq API key is not configured.
        """
        if settings.GROQ_API_KEY:
            try:
                return cls._evaluate_with_groq(candidate, job)
            except Exception as e:
                logger.error(f"Groq API call failed: {e}. Falling back to heuristic evaluation.")

        return cls._heuristic_fallback(candidate, job)

    @classmethod
    async def async_evaluate_fit(cls, candidate: Dict[str, Any], job: Dict[str, Any]) -> Dict[str, Any]:
        """
        Runs asynchronous LLM evaluation via Groq with structured JSON output.
        Falls back to rule-based evaluation if Groq API key is not configured or error occurs.
        """
        if settings.GROQ_API_KEY:
            try:
                from groq import AsyncGroq
                client = AsyncGroq(api_key=settings.GROQ_API_KEY)

                system_prompt = (
                    "You are an expert AI Career Agent and Technical Recruiter. "
                    "Your task is to critically analyze candidate fit for a job posting. "
                    "You must return ONLY a valid JSON object with the following exact keys:\n"
                    "{\n"
                    '  "overall_score": integer (0 to 100),\n'
                    '  "skill_match_score": integer (0 to 100),\n'
                    '  "experience_match_score": integer (0 to 100),\n'
                    '  "matched_skills": [list of strings],\n'
                    '  "missing_skills": [list of strings],\n'
                    '  "reasoning": "2-3 sentences explaining strengths and gaps",\n'
                    '  "tailored_pitch": "Actionable talking points for the candidate cover letter or outreach",\n'
                    '  "recommended_action": "strongly_recommend" | "recommend" | "neutral" | "not_recommended"\n'
                    "}"
                )

                user_content = f"""
### CANDIDATE PROFILE:
- Name: {candidate.get('full_name')}
- Target Titles: {', '.join(candidate.get('target_titles') or [])}
- Primary Skills: {', '.join(candidate.get('primary_skills') or [])}
- Secondary Skills: {', '.join(candidate.get('secondary_skills') or [])}
- Years of Experience: {candidate.get('experience_years', 0)}
- Bio: {candidate.get('bio', 'N/A')}

### JOB DETAILS:
- Title: {job.get('title')}
- Company: {job.get('company_name')}
- Workplace Type: {job.get('workplace_type')}
- Experience Level: {job.get('experience_level')}
- Description:
{job.get('description', '')[:3000]}
"""

                chat_completion = await client.chat.completions.create(
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_content}
                    ],
                    model=settings.GROQ_MODEL,
                    response_format={"type": "json_object"},
                    temperature=0.2,
                    max_tokens=1024,
                )

                response_text = chat_completion.choices[0].message.content
                parsed = json.loads(response_text)

                action = parsed.get("recommended_action", "neutral")
                if action not in ["strongly_recommend", "recommend", "neutral", "not_recommended"]:
                    score = parsed.get("overall_score", 50)
                    action = "strongly_recommend" if score >= 80 else ("recommend" if score >= 65 else "neutral")
                    parsed["recommended_action"] = action

                return parsed
            except Exception as e:
                logger.error(f"Async Groq API call failed: {e}. Falling back to heuristic evaluation.")

        return cls._heuristic_fallback(candidate, job)


    @classmethod
    def _evaluate_with_groq(cls, candidate: Dict[str, Any], job: Dict[str, Any]) -> Dict[str, Any]:
        from groq import Groq

        client = Groq(api_key=settings.GROQ_API_KEY)

        system_prompt = (
            "You are an expert AI Career Agent and Technical Recruiter. "
            "Your task is to critically analyze candidate fit for a job posting. "
            "You must return ONLY a valid JSON object with the following exact keys:\n"
            "{\n"
            '  "overall_score": integer (0 to 100),\n'
            '  "skill_match_score": integer (0 to 100),\n'
            '  "experience_match_score": integer (0 to 100),\n'
            '  "matched_skills": [list of strings],\n'
            '  "missing_skills": [list of strings],\n'
            '  "reasoning": "2-3 sentences explaining strengths and gaps",\n'
            '  "tailored_pitch": "Actionable talking points for the candidate cover letter or outreach",\n'
            '  "recommended_action": "strongly_recommend" | "recommend" | "neutral" | "not_recommended"\n'
            "}"
        )

        user_content = f"""
### CANDIDATE PROFILE:
- Name: {candidate.get('full_name')}
- Target Titles: {', '.join(candidate.get('target_titles') or [])}
- Primary Skills: {', '.join(candidate.get('primary_skills') or [])}
- Secondary Skills: {', '.join(candidate.get('secondary_skills') or [])}
- Years of Experience: {candidate.get('experience_years', 0)}
- Bio: {candidate.get('bio', 'N/A')}

### JOB DETAILS:
- Title: {job.get('title')}
- Company: {job.get('company_name')}
- Workplace Type: {job.get('workplace_type')}
- Experience Level: {job.get('experience_level')}
- Description:
{job.get('description', '')[:3000]}
"""

        chat_completion = client.chat.completions.create(
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_content}
            ],
            model=settings.GROQ_MODEL,
            response_format={"type": "json_object"},
            temperature=0.2,
            max_tokens=1024,
        )

        response_text = chat_completion.choices[0].message.content
        parsed = json.loads(response_text)

        # Enforce valid action bounds
        action = parsed.get("recommended_action", "neutral")
        if action not in ["strongly_recommend", "recommend", "neutral", "not_recommended"]:
            score = parsed.get("overall_score", 50)
            action = "strongly_recommend" if score >= 80 else ("recommend" if score >= 65 else "neutral")
            parsed["recommended_action"] = action

        return parsed

    @classmethod
    def _heuristic_fallback(cls, candidate: Dict[str, Any], job: Dict[str, Any]) -> Dict[str, Any]:
        """Heuristic fallback when GROQ_API_KEY is not set."""
        candidate_skills = [
            s.lower() for s in (candidate.get("primary_skills") or []) + (candidate.get("secondary_skills") or [])
        ]
        description = (job.get("description") or "").lower()
        title = (job.get("title") or "").lower()

        matched = [s for s in candidate_skills if s in description or s in title]
        common_ai_skills = ["docker", "fastapi", "langchain", "kubernetes", "pytorch", "supabase", "vector db"]
        missing = [s for s in common_ai_skills if s not in matched and s in description]

        skill_score = min(100, int((len(matched) / max(1, len(candidate_skills))) * 100) + 35)
        exp_score = 80
        overall = int((skill_score * 0.6) + (exp_score * 0.4))
        action = "strongly_recommend" if overall >= 80 else ("recommend" if overall >= 65 else "neutral")

        return {
            "overall_score": overall,
            "skill_match_score": skill_score,
            "experience_match_score": exp_score,
            "matched_skills": matched if matched else candidate.get("primary_skills", [])[:2],
            "missing_skills": missing,
            "reasoning": f"Matches key candidate skills ({', '.join(matched[:3]) if matched else 'core requirements'}). Evaluated using heuristic fallback (set GROQ_API_KEY for deep LLM evaluation).",
            "tailored_pitch": f"Highlight experience with {matched[0] if matched else 'Python'} and autonomous agent development.",
            "recommended_action": action
        }
