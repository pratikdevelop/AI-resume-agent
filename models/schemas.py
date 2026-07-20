# models/schemas.py
# Shared Pydantic models used across all agents

from pydantic import BaseModel, EmailStr
from typing import List, Optional
from enum import Enum


# ─── INPUT ────────────────────────────────────────────
class RawResume(BaseModel):
    name: str
    email: str
    years_experience: int
    skills: List[str]
    education: str
    previous_roles: List[str] = []


# ─── AGENT 1 OUTPUT ───────────────────────────────────
class ParsedResume(BaseModel):
    name: str
    email: str
    years_experience: int
    skills: List[str]          # lowercased
    education: str
    previous_roles: List[str]


# ─── AGENT 2 OUTPUT ───────────────────────────────────
class MatchResult(BaseModel):
    candidate_name: str
    candidate_email: str
    job_title: str
    job_id: Optional[str] = None
    score: float
    required_skills_matched: List[str]
    preferred_skills_matched: List[str]
    experience_years: int
    shortlist_threshold: Optional[int] = 70
    waitlist_threshold: Optional[int]  = 45


# ─── AGENT 3 OUTPUT ───────────────────────────────────
class Decision(str, Enum):
    SHORTLISTED = "SHORTLISTED"
    WAITLISTED  = "WAITLISTED"
    REJECTED    = "REJECTED"


class DecisionResult(BaseModel):
    candidate_name: str
    candidate_email: str
    job_title: str
    score: float
    decision: Decision
    reason: str
    required_skills_matched: List[str]


# ─── AGENT 4 OUTPUT ───────────────────────────────────
class EmailResult(BaseModel):
    status: str
    recipient: str
    decision: Decision
    subject: str
    body: str


# ─── AGENT 5 INPUT ────────────────────────────────────
class ScheduleRequest(BaseModel):
    candidate_name: str
    candidate_email: str
    job_title: str
    score: float
    decision: Decision


# ─── AGENT 5 OUTPUT ───────────────────────────────────
class InterviewSlot(BaseModel):
    date: str           # e.g. "2026-03-05"
    time: str           # e.g. "10:00 AM"
    duration_minutes: int
    interviewer: str
    interviewer_email: Optional[str] = ""
    meeting_link: str
    calendar_id: str    # simulated calendar event ID


class ScheduleResult(BaseModel):
    scheduled: bool
    candidate_name: str
    candidate_email: str
    slot: Optional[InterviewSlot] = None
    skipped_reason: Optional[str] = None


# ─── FINAL ORCHESTRATOR RESPONSE ──────────────────────
class PipelineResult(BaseModel):
    candidate: str
    email: str
    score: float
    decision: Decision
    reason: str
    email_sent: bool
    email_subject: str
    interview_scheduled: bool
    interview_slot: Optional[InterviewSlot] = None