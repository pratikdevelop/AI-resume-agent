# agents/scheduler_agent.py
# Agent 5: Interview Scheduler
# Uses job-specific interviewers and deterministic date (X working days ahead)

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime, timedelta
import httpx
import os
import random
import hashlib
from dotenv import load_dotenv

load_dotenv(override=True)

ORCHESTRATOR_URL = os.getenv("ORCHESTRATOR_URL", "http://localhost:8000")
TIMEZONE         = os.getenv("TIMEZONE", "Asia/Kolkata")

TIME_SLOTS_HOUR = [9, 10, 11, 14, 15, 16]  # available hours (24h)

app = FastAPI(title="SchedulerAgent", version="3.0")


# ── Schemas ───────────────────────────────────────────────────
class Decision(str):
    SHORTLISTED = "SHORTLISTED"
    WAITLISTED  = "WAITLISTED"
    REJECTED    = "REJECTED"


class ScheduleRequest(BaseModel):
    candidate_name: str
    candidate_email: str
    job_title: str
    job_id: Optional[str] = None
    score: float
    decision: str


class InterviewSlot(BaseModel):
    date: str
    time: str
    duration_minutes: int
    interviewer: str
    interviewer_email: Optional[str] = ""
    meeting_link: str
    calendar_id: str


class ScheduleResult(BaseModel):
    scheduled: bool
    candidate_name: str
    candidate_email: str
    slot: Optional[InterviewSlot] = None
    skipped_reason: Optional[str] = None


# ── Helpers ───────────────────────────────────────────────────

def next_working_day(days_ahead: int) -> datetime:
    """Return a date that is exactly `days_ahead` working days from today."""
    dt = datetime.utcnow()
    count = 0
    while count < days_ahead:
        dt += timedelta(days=1)
        if dt.weekday() < 5:   # Mon=0 … Fri=4
            count += 1
    return dt


def pick_time_slot(candidate_email: str) -> int:
    """Pick a consistent (not random) time slot based on candidate email hash."""
    h = int(hashlib.md5(candidate_email.encode()).hexdigest(), 16)
    return TIME_SLOTS_HOUR[h % len(TIME_SLOTS_HOUR)]


def make_meeting_link(candidate_name: str, job_title: str, date_str: str) -> str:
    """Generate a deterministic Jitsi meet link."""
    slug = f"{candidate_name}-{job_title}-{date_str}".lower()
    slug = "".join(c if c.isalnum() else "-" for c in slug)
    slug = "-".join(filter(None, slug.split("-")))[:60]
    return f"https://meet.jit.si/techcorp-{slug}"


async def fetch_job(job_id: str) -> Optional[dict]:
    """Fetch job details including interviewers from orchestrator."""
    if not job_id:
        return None
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            r = await client.get(f"{ORCHESTRATOR_URL}/jobs/{job_id}")
            if r.status_code == 200:
                return r.json()
    except Exception as e:
        print(f"[SchedulerAgent] Could not fetch job {job_id}: {e}")
    return None


# ── Routes ────────────────────────────────────────────────────

@app.get("/health")
def health():
    return {"agent": "SchedulerAgent", "status": "ok", "port": 8005}


@app.post("/schedule", response_model=ScheduleResult)
async def schedule_interview(request: ScheduleRequest) -> ScheduleResult:
    print(f"\n[SchedulerAgent] {request.candidate_name} — {request.decision}")

    # Only schedule for SHORTLISTED
    if request.decision != "SHORTLISTED":
        reason = f"Candidate is {request.decision} — scheduling skipped."
        print(f"[SchedulerAgent] Skipped: {reason}")
        return ScheduleResult(
            scheduled=False,
            candidate_name=request.candidate_name,
            candidate_email=request.candidate_email,
            skipped_reason=reason,
        )

    # ── Fetch job to get interviewers & settings ──────────────
    job = await fetch_job(request.job_id)

    # Get interviewers from job, fallback to env-based defaults
    job_interviewers = []
    days_ahead = 3
    duration = 60

    if job:
        job_interviewers = job.get("interviewers", [])
        days_ahead = job.get("interview_days_ahead", 3)
        duration   = job.get("interview_duration", 60)
        print(f"[SchedulerAgent] Job '{job['title']}' has {len(job_interviewers)} interviewer(s), scheduling {days_ahead} working days ahead")

    # ── Pick interviewer ──────────────────────────────────────
    if job_interviewers:
        # Pick deterministically based on candidate email
        h = int(hashlib.md5(request.candidate_email.encode()).hexdigest(), 16)
        interviewer_obj = job_interviewers[h % len(job_interviewers)]
        interviewer_name  = f"{interviewer_obj.get('name','')} ({interviewer_obj.get('title','')})" if interviewer_obj.get('title') else interviewer_obj.get('name','')
        interviewer_email = interviewer_obj.get("email", os.getenv("GMAIL_SENDER", ""))
    else:
        # No interviewers defined for this job — use HR email
        interviewer_name  = "HR Team"
        interviewer_email = os.getenv("HR_EMAIL", os.getenv("GMAIL_SENDER", ""))
        print(f"[SchedulerAgent] No interviewers set for job — assigning HR Team")

    # ── Calculate interview date & time ───────────────────────
    interview_date = next_working_day(days_ahead)
    hour           = pick_time_slot(request.candidate_email)
    interview_dt   = interview_date.replace(hour=hour, minute=0, second=0)

    date_str = interview_dt.strftime("%Y-%m-%d")
    time_str = interview_dt.strftime("%I:%M %p")

    # ── Build meeting link ────────────────────────────────────
    meet_link = make_meeting_link(request.candidate_name, request.job_title, date_str)

    slot = InterviewSlot(
        date=date_str,
        time=time_str,
        duration_minutes=duration,
        interviewer=interviewer_name,
        interviewer_email=interviewer_email,
        meeting_link=meet_link,
        calendar_id=f"evt-{date_str}-{hour:02d}00",
    )

    print(f"[SchedulerAgent] Scheduled: {date_str} {time_str} | Interviewer: {interviewer_name} ({interviewer_email})")
    return ScheduleResult(
        scheduled=True,
        candidate_name=request.candidate_name,
        candidate_email=request.candidate_email,
        slot=slot,
    )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8005)