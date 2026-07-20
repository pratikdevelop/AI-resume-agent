# agents/matching_agent.py
# Agent 2: Skill & Experience Matcher
# Runs on port 8002
# Now fetches job requirements from MongoDB instead of hardcoded values

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import List, Optional
import httpx
import os
from dotenv import load_dotenv

load_dotenv()

ORCHESTRATOR_URL = os.getenv("ORCHESTRATOR_URL", "http://localhost:8000")

# Inline schemas
class ParsedResume(BaseModel):
    name: str
    email: str
    years_experience: int
    skills: List[str]
    education: str
    previous_roles: List[str]
    job_id: Optional[str] = None   # which job they applied to

class MatchResult(BaseModel):
    candidate_name: str
    candidate_email: str
    job_title: str
    job_id: Optional[str] = None
    score: float
    required_skills_matched: List[str]
    preferred_skills_matched: List[str]
    experience_years: int

# No default job — job_id is always required
# If job not found, pipeline returns an error

app = FastAPI(title="MatchingAgent (Dynamic Jobs)", version="2.0")


async def fetch_job(job_id: str) -> dict:
    """Fetch job requirements from orchestrator's /jobs/{id} endpoint."""
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            r = await client.get(f"{ORCHESTRATOR_URL}/jobs/{job_id}")
            if r.status_code == 200:
                return r.json()
    except Exception as e:
        print(f"[MatchingAgent] Could not fetch job {job_id}: {e}")
    return None


def score_candidate(resume: ParsedResume, job: dict) -> MatchResult:
    """Score candidate against a specific job's requirements."""
    required  = [s.lower() for s in job.get("required_skills", [])]
    preferred = [s.lower() for s in job.get("preferred_skills", [])]
    min_exp   = job.get("min_experience_years", 3)
    weights   = job.get("weights", {"required_skills": 60, "preferred_skills": 20, "experience": 20})

    candidate_skills = [s.lower() for s in resume.skills]

    req_matched  = [s for s in required  if s in candidate_skills]
    pref_matched = [s for s in preferred if s in candidate_skills]

    req_score  = (len(req_matched)  / max(len(required),  1)) * weights["required_skills"]
    pref_score = (len(pref_matched) / max(len(preferred), 1)) * weights["preferred_skills"]
    exp_score  = min(resume.years_experience / max(min_exp, 1), 1.0) * weights["experience"]

    total = round(req_score + pref_score + exp_score, 1)

    return MatchResult(
        candidate_name=resume.name,
        candidate_email=resume.email,
        job_title=job.get("title", "Unknown"),
        job_id=str(job.get("_id", "")),
        score=total,
        required_skills_matched=req_matched,
        preferred_skills_matched=pref_matched,
        experience_years=resume.years_experience,
        shortlist_threshold=job.get("shortlist_threshold", 70),
        waitlist_threshold=job.get("waitlist_threshold", 45),
    )


@app.get("/health")
def health():
    return {"agent": "MatchingAgent", "status": "ok", "port": 8002}


@app.post("/match", response_model=MatchResult)
async def match_candidate(resume: ParsedResume) -> MatchResult:
    """Score candidate against the job they applied for (or default job)."""
    try:
        job = None

        # Try to fetch the specific job
        if resume.job_id and resume.job_id != "default":
            job = await fetch_job(resume.job_id)
            if job:
                print(f"[MatchingAgent] Scoring against job: {job['title']} ({resume.job_id})")
            else:
                print(f"[MatchingAgent] Job {resume.job_id} not found, using default")

        # No fallback — raise error if job not found
        if not job:
            raise HTTPException(status_code=404, detail=f"Job '{resume.job_id}' not found. Please select a valid job.")

        result = score_candidate(resume, job)
        print(f"[MatchingAgent] {resume.name} scored {result.score}/100 for {result.job_title}")
        return result

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Matching failed: {str(e)}")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8002)