# agents/decision_agent.py
# 🤖 Agent 3: Hiring Decision Maker
# Runs on port 8003
# Receives MatchResult, returns DecisionResult

from fastapi import FastAPI, HTTPException
import sys, os
sys.path.append(os.path.dirname(os.path.dirname(__file__)))
from models.schemas import MatchResult, DecisionResult, Decision
from typing import Optional

app = FastAPI(title="DecisionAgent", version="1.0")

# Default thresholds (overridden by job-specific ones from MatchResult)
DEFAULT_THRESHOLDS = {"shortlist": 70, "waitlist": 45}


@app.get("/health")
def health():
    return {"agent": "DecisionAgent", "status": "ok", "port": 8003}


@app.post("/decide", response_model=DecisionResult)
def make_decision(match: MatchResult) -> DecisionResult:
    """
    Apply business rules to the match score and produce a hiring decision.
    Rules can be swapped for an ML model or LLM in production.
    """
    try:
        score = match.score

        # Use job-specific thresholds if available, else defaults
        shortlist_t = getattr(match, "shortlist_threshold", None) or DEFAULT_THRESHOLDS["shortlist"]
        waitlist_t  = getattr(match, "waitlist_threshold",  None) or DEFAULT_THRESHOLDS["waitlist"]

        if score >= shortlist_t:
            decision = Decision.SHORTLISTED
            reason = (
                f"Strong candidate with score {score}/100. "
                f"Matched required skills: {match.required_skills_matched}."
            )
        elif score >= waitlist_t:
            decision = Decision.WAITLISTED
            reason = (
                f"Moderate candidate with score {score}/100. "
                f"Missing some key required skills."
            )
        else:
            decision = Decision.REJECTED
            reason = (
                f"Candidate scored {score}/100, "
                f"below the minimum threshold of {waitlist_t}."
            )

        result = DecisionResult(
            candidate_name=match.candidate_name,
            candidate_email=match.candidate_email,
            job_title=match.job_title,
            score=score,
            decision=decision,
            reason=reason,
            required_skills_matched=match.required_skills_matched,
        )
        print(f"[DecisionAgent] ✅ {match.candidate_name} → {decision.value}")
        return result

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Decision failed: {str(e)}")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8003)