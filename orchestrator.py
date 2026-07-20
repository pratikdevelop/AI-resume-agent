# orchestrator.py
# Main Entry Point (port 8000)
# MongoDB + API Key Auth + Admin Dashboard + Duplicate Detection + PDF Upload

from fastapi import FastAPI, HTTPException, Depends, Header, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.staticfiles import StaticFiles
import pathlib
import httpx
import os
from dotenv import load_dotenv
from pydantic import BaseModel
from models.schemas import RawResume, PipelineResult, Decision
from auth import (
    CompanyRegister, UserLogin, TokenResponse, CompanyInDB,
    hash_password, verify_password, create_token, get_current_company
)
from database import (
    create_company, get_company_by_email,
    get_all_applications_for_company, get_stats_for_company,
    get_jobs_for_company, get_application_by_email_and_company
)
from database import save_application, get_all_applications, get_application_by_email, get_stats, ping, create_job, get_all_jobs, get_job_by_id, update_job, delete_job, get_job_stats

load_dotenv()

API_KEY = os.getenv("API_KEY", "secret-key-change-me")

app = FastAPI(
    title="A2A Job Application Orchestrator",
    description="5-agent pipeline with MongoDB, Auth, Dashboard, and PDF Upload",
    version="3.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

def get_agents():
    """Read agent URLs at call time so Docker env vars are always picked up."""
    return {
        "resume":    os.getenv("RESUME_URL",    "http://localhost:8001") + "/parse",
        "matching":  os.getenv("MATCHING_URL",  "http://localhost:8002") + "/match",
        "decision":  os.getenv("DECISION_URL",  "http://localhost:8003") + "/decide",
        "email":     os.getenv("EMAIL_URL",     "http://localhost:8004") + "/send-email",
        "scheduler": os.getenv("SCHEDULER_URL", "http://localhost:8005") + "/schedule",
    }

TIMEOUT = httpx.Timeout(30.0)


@app.on_event("startup")
async def startup():
    try:
        await ping()
        print("[Orchestrator] MongoDB Atlas connected!")
    except Exception as e:
        print(f"[Orchestrator] MongoDB WARNING: {e}")


def verify_api_key(x_api_key: str = Header(...)):
    if x_api_key != API_KEY:
        raise HTTPException(status_code=401, detail="Invalid API Key. Pass X-Api-Key header.")
    return x_api_key


async def call_agent(client, url, payload, agent_name):
    print(f"[Orchestrator] Calling {agent_name}...")
    try:
        response = await client.post(url, json=payload, timeout=TIMEOUT)
        response.raise_for_status()
        return response.json()
    except httpx.ConnectError:
        raise HTTPException(status_code=503, detail=f"{agent_name} unavailable at {url}")
    except httpx.HTTPStatusError as e:
        raise HTTPException(status_code=502, detail=f"{agent_name} error {e.response.status_code}: {e.response.text}")


async def run_pipeline(client, parsed: dict, source: str = "json", filename: str = "", job_id: str = "", company=None) -> tuple:
    """Shared pipeline logic used by both /apply and /apply-pdf."""
    parsed["job_id"] = job_id  # ensure job_id flows into matching
    match_result    = await call_agent(client, get_agents()["matching"], parsed,       "MatchingAgent")
    decision_result = await call_agent(client, get_agents()["decision"], match_result, "DecisionAgent")

    schedule_payload = {
        "candidate_name":  decision_result["candidate_name"],
        "candidate_email": decision_result["candidate_email"],
        "job_title":       decision_result["job_title"],
        "score":           decision_result["score"],
        "decision":        decision_result["decision"],
    }
    schedule_result = await call_agent(client, get_agents()["scheduler"], schedule_payload, "SchedulerAgent")

    email_payload = dict(decision_result)
    email_payload["interview_slot"] = schedule_result.get("slot") if schedule_result.get("scheduled") else None
    email_result = await call_agent(client, get_agents()["email"], email_payload, "EmailAgent")

    result = PipelineResult(
        candidate=decision_result["candidate_name"],
        email=decision_result["candidate_email"],
        score=decision_result["score"],
        decision=Decision(decision_result["decision"]),
        reason=decision_result["reason"],
        email_sent=email_result["status"] == "sent",
        email_subject=email_result["subject"],
        interview_scheduled=schedule_result["scheduled"],
        interview_slot=schedule_result.get("slot"),
    )

    db_doc = {
        "candidate":           result.candidate,
        "email":               result.email,
        "score":               result.score,
        "decision":            result.decision,
        "reason":              result.reason,
        "email_sent":          result.email_sent,
        "interview_scheduled": result.interview_scheduled,
        "interview_slot":      schedule_result.get("slot"),
        "skills_matched":      decision_result.get("required_skills_matched", []),
        "source":              source,
        "job_id":              job_id,
        "job_title":           match_result.get("job_title", ""),
        "company_id":          company.company_id   if company else "",
        "company_name":        company.company_name if company else "",
    }
    if filename:
        db_doc["original_filename"] = filename

    await save_application(db_doc)
    return result, decision_result


# ── Routes ─────────────────────────────────────────────────────────────────────


# Serve frontend UI — all routes served from root
_frontend = pathlib.Path(__file__).parent / 'frontend'

@app.get('/', response_class=FileResponse)
def root_page():
    """Root — redirect to auth if not logged in (handled by frontend JS)."""
    return FileResponse(str(_frontend / 'auth.html'))

@app.get('/auth', response_class=FileResponse)
def auth_page():
    return FileResponse(str(_frontend / 'auth.html'))

@app.get('/app', response_class=FileResponse)
def app_page():
    return FileResponse(str(_frontend / 'index.html'))

# Static assets (fonts, css, js files if any)
if _frontend.exists():
    app.mount('/static', StaticFiles(directory=str(_frontend)), name='static')


@app.get("/health")
async def health_check():
    statuses = {}
    async with httpx.AsyncClient() as client:
        for name, url in get_agents().items():
            base_url = url.rsplit("/", 1)[0]
            try:
                r = await client.get(f"{base_url}/health", timeout=3.0)
                statuses[name] = "ok" if r.status_code == 200 else "error"
            except Exception:
                statuses[name] = "unreachable"
    return {"orchestrator": "ok", "agents": statuses}


@app.get("/applications")
async def list_applications(company: CompanyInDB = Depends(get_current_company)):
    apps = await get_all_applications_for_company(company.company_id)
    return {"count": len(apps), "applications": apps}


@app.get("/stats")
async def stats(company: CompanyInDB = Depends(get_current_company)):
    return await get_stats_for_company(company.company_id)


@app.get("/dashboard", response_class=HTMLResponse)
async def dashboard():
    apps = await get_all_applications(200)
    s    = await get_stats()

    rows = ""
    for a in apps:
        decision = a.get("decision", "")
        color    = {"SHORTLISTED": "#22c55e", "WAITLISTED": "#f59e0b", "REJECTED": "#ef4444"}.get(decision, "#6b7280")
        slot     = a.get("interview_slot") or {}
        interview = f"{slot.get('date','')} {slot.get('time','')}<br><small>{slot.get('interviewer','')}</small>" if slot else "<span style='color:#9ca3af'>-</span>"
        meet      = f"<a href='{slot.get('meeting_link','')}' target='_blank' style='color:#6366f1'>Join</a>" if slot.get("meeting_link") else "-"
        created   = str(a.get("created_at", ""))[:16].replace("T", " ")
        source    = a.get("source", "json")
        source_badge = "<span style='background:#6366f1;color:white;padding:2px 7px;border-radius:999px;font-size:11px'>PDF</span>" if source == "pdf_upload" else ""

        rows += f"""<tr>
            <td>{a.get('candidate','')} {source_badge}</td>
            <td><a href='mailto:{a.get('email','')}' style='color:#6366f1'>{a.get('email','')}</a></td>
            <td><strong>{a.get('score',0)}</strong></td>
            <td><span style='background:{color};color:white;padding:3px 10px;border-radius:999px;font-size:12px;font-weight:600'>{decision}</span></td>
            <td>{interview}</td>
            <td>{meet}</td>
            <td style='color:#9ca3af;font-size:12px'>{created}</td>
        </tr>"""

    html = f"""<!DOCTYPE html>
<html lang='en'>
<head>
    <meta charset='UTF-8'>
    <title>A2A Hiring Dashboard</title>
    <meta http-equiv='refresh' content='30'>
    <style>
        *{{margin:0;padding:0;box-sizing:border-box}}
        body{{font-family:'Segoe UI',sans-serif;background:#0f172a;color:#e2e8f0;min-height:100vh}}
        header{{background:#1e293b;border-bottom:1px solid #334155;padding:20px 32px;display:flex;align-items:center;justify-content:space-between}}
        header h1{{font-size:22px;font-weight:700;color:#f1f5f9}}
        .stats{{display:grid;grid-template-columns:repeat(5,1fr);gap:16px;padding:24px 32px}}
        .stat{{background:#1e293b;border:1px solid #334155;border-radius:12px;padding:20px;text-align:center}}
        .stat .num{{font-size:36px;font-weight:800;color:#6366f1}}
        .stat .label{{font-size:13px;color:#64748b;margin-top:4px}}
        .green .num{{color:#22c55e}}.yellow .num{{color:#f59e0b}}.red .num{{color:#ef4444}}.blue .num{{color:#38bdf8}}
        .wrap{{padding:0 32px 32px}}
        .wrap h2{{font-size:16px;font-weight:600;color:#94a3b8;margin-bottom:12px}}
        table{{width:100%;border-collapse:collapse;background:#1e293b;border-radius:12px;overflow:hidden;border:1px solid #334155}}
        th{{background:#0f172a;padding:12px 16px;text-align:left;font-size:12px;font-weight:600;color:#64748b;text-transform:uppercase;border-bottom:1px solid #334155}}
        td{{padding:14px 16px;font-size:14px;border-bottom:1px solid #0f172a;vertical-align:middle}}
        tr:last-child td{{border-bottom:none}}
        tr:hover td{{background:#263548}}
        .btn{{background:#6366f1;color:white;border:none;padding:8px 18px;border-radius:8px;cursor:pointer;font-size:13px;font-weight:600}}
        .empty{{text-align:center;padding:60px;color:#475569}}
    </style>
</head>
<body>
<header>
    <h1>A2A Hiring Dashboard</h1>
    <div style='display:flex;align-items:center;gap:16px'>
        <span style='color:#64748b;font-size:13px'>Auto-refreshes every 30s</span>
        <button class='btn' onclick='location.reload()'>Refresh</button>
    </div>
</header>
<div class='stats'>
    <div class='stat'><div class='num'>{s['total']}</div><div class='label'>Total Applications</div></div>
    <div class='stat green'><div class='num'>{s['shortlisted']}</div><div class='label'>Shortlisted</div></div>
    <div class='stat yellow'><div class='num'>{s['waitlisted']}</div><div class='label'>Waitlisted</div></div>
    <div class='stat red'><div class='num'>{s['rejected']}</div><div class='label'>Rejected</div></div>
    <div class='stat blue'><div class='num'>{s['interviews_scheduled']}</div><div class='label'>Interviews Booked</div></div>
</div>
<div class='wrap'>
    <h2>All Candidates ({s['total']})</h2>
    <table>
        <thead><tr>
            <th>Candidate</th><th>Email</th><th>Score</th>
            <th>Decision</th><th>Interview</th><th>Meet</th><th>Applied</th>
        </tr></thead>
        <tbody>
            {rows if rows else "<tr><td colspan='7' class='empty'>No applications yet</td></tr>"}
        </tbody>
    </table>
</div>
</body>
</html>"""
    return html




# ── Auth Routes ──────────────────────────────────────────────────────────────

@app.post("/auth/register", response_model=TokenResponse)
async def register(data: CompanyRegister):
    """Register a new company workspace."""
    existing = await get_company_by_email(data.email)
    if existing:
        raise HTTPException(status_code=409, detail="Email already registered. Please login.")

    company_doc = {
        "company_name": data.company_name.strip(),
        "email":        data.email.lower().strip(),
        "password":     hash_password(data.password),
        "industry":     data.industry,
        "website":      data.website,
    }
    company_id = await create_company(company_doc)

    token = create_token({
        "company_id":   company_id,
        "company_name": data.company_name,
        "email":        data.email.lower(),
        "industry":     data.industry,
        "website":      data.website,
    })

    print(f"[Auth] New company registered: {data.company_name} ({data.email})")
    return TokenResponse(
        access_token=token,
        company_id=company_id,
        company_name=data.company_name,
        email=data.email.lower(),
    )


@app.post("/auth/login", response_model=TokenResponse)
async def login(data: UserLogin):
    """Login to existing company workspace."""
    company = await get_company_by_email(data.email)
    if not company or not verify_password(data.password, company["password"]):
        raise HTTPException(status_code=401, detail="Invalid email or password.")

    company_id = str(company["_id"])
    token = create_token({
        "company_id":   company_id,
        "company_name": company["company_name"],
        "email":        company["email"],
        "industry":     company.get("industry", ""),
        "website":      company.get("website", ""),
    })

    print(f"[Auth] Login: {company['company_name']} ({company['email']})")
    return TokenResponse(
        access_token=token,
        company_id=company_id,
        company_name=company["company_name"],
        email=company["email"],
    )


@app.get("/auth/me")
async def me(company: CompanyInDB = Depends(get_current_company)):
    """Get current company info."""
    return {
        "company_id":   company.company_id,
        "company_name": company.company_name,
        "email":        company.email,
        "industry":     company.industry,
        "website":      company.website,
    }


# ── Job Management Routes ─────────────────────────────────────────────────────

class JobInterviewer(BaseModel):
    name: str
    email: str
    title: str = ""

class JobPayload(BaseModel):
    title: str
    department: str = ""
    description: str = ""
    required_skills: list
    preferred_skills: list = []
    min_experience_years: int = 3
    shortlist_threshold: int = 70
    waitlist_threshold: int = 45
    weights: dict = {"required_skills": 60, "preferred_skills": 20, "experience": 20}
    interviewers: list = []          # list of {name, email, title}
    interview_days_ahead: int = 3    # schedule X working days from today
    interview_duration: int = 60     # minutes

@app.post("/jobs")
async def create_new_job(job: JobPayload, company: CompanyInDB = Depends(get_current_company)):
    """HR creates a new job posting for their company."""
    data = job.model_dump()
    data["company_id"]   = company.company_id
    data["company_name"] = company.company_name
    job_id = await create_job(data)
    return {"job_id": job_id, "message": f"Job '{job.title}' created successfully"}


@app.get("/jobs")
async def list_jobs(company: CompanyInDB = Depends(get_current_company)):
    """List active job postings for this company only."""
    jobs = await get_jobs_for_company(company.company_id)
    return {"count": len(jobs), "jobs": jobs}


@app.get("/jobs/{job_id}")
async def get_job(job_id: str):
    """Get a specific job by ID — used internally by agents."""
    job = await get_job_by_id(job_id)
    if not job:
        raise HTTPException(status_code=404, detail=f"Job {job_id} not found")
    return job


@app.put("/jobs/{job_id}")
async def edit_job(job_id: str, job: JobPayload, company: CompanyInDB = Depends(get_current_company)):
    """HR updates a job posting."""
    # Verify job belongs to this company
    existing = await get_job_by_id(job_id)
    if not existing or existing.get("company_id") != company.company_id:
        raise HTTPException(status_code=404, detail="Job not found")
    data = job.model_dump()
    data["company_id"] = company.company_id
    await update_job(job_id, data)
    return {"message": "Job updated successfully"}


@app.delete("/jobs/{job_id}")
async def remove_job(job_id: str, company: CompanyInDB = Depends(get_current_company)):
    """HR deactivates a job posting."""
    existing = await get_job_by_id(job_id)
    if not existing or existing.get("company_id") != company.company_id:
        raise HTTPException(status_code=404, detail="Job not found")
    await delete_job(job_id)
    return {"message": "Job deactivated successfully"}


@app.get("/jobs/{job_id}/stats")
async def job_stats(job_id: str, company: CompanyInDB = Depends(get_current_company)):
    """Stats for a specific job posting."""
    existing = await get_job_by_id(job_id)
    if not existing or existing.get("company_id") != company.company_id:
        raise HTTPException(status_code=404, detail="Job not found")
    return await get_job_stats(job_id)

# ── JSON Pipeline ─────────────────────────────────────────────────────────────
@app.post("/apply", response_model=PipelineResult)
async def apply(resume: RawResume, job_id: str = "", company: CompanyInDB = Depends(get_current_company)):
    print(f"\n[Orchestrator] [{company.company_name}] JSON: {resume.name} ({resume.email}) -> job:{job_id}")

    existing = await get_application_by_email_and_company(resume.email, company.company_id)
    if existing:
        raise HTTPException(status_code=409, detail=f"Already applied on {str(existing.get('created_at',''))[:10]}. Decision: {existing.get('decision')}.")

    async with httpx.AsyncClient() as client:
        parsed = await call_agent(client, get_agents()["resume"], resume.model_dump(), "ResumeAgent")
        parsed["job_id"] = job_id
        result, _ = await run_pipeline(client, parsed, source="json", job_id=job_id, company=company)

    print(f"[Orchestrator] Done: {result.candidate} -> {result.decision}")
    return result


# ── PDF Pipeline ──────────────────────────────────────────────────────────────
@app.post("/apply-pdf", response_model=PipelineResult)
async def apply_pdf(file: UploadFile = File(...), job_id: str = "", company: CompanyInDB = Depends(get_current_company)):
    """
    Upload a PDF resume -> llama3.2 extracts candidate info -> full pipeline runs.
    """
    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files accepted.")

    print(f"\n[Orchestrator] PDF application: {file.filename}")

    pdf_bytes = await file.read()

    async with httpx.AsyncClient() as client:

        # Step 1: Send PDF to ResumeAgent for llama3.2 parsing
        try:
            response = await client.post(
                os.getenv("RESUME_URL", "http://localhost:8001") + "/parse-pdf",
                files={"file": (file.filename, pdf_bytes, "application/pdf")},
                timeout=120.0,
            )
            response.raise_for_status()
            parsed = response.json()
        except httpx.ConnectError:
            raise HTTPException(status_code=503, detail="ResumeAgent unavailable at port 8001")
        except httpx.HTTPStatusError as e:
            raise HTTPException(status_code=502, detail=f"ResumeAgent error: {e.response.text}")

        print(f"[Orchestrator] llama3.2 extracted: {parsed.get('name')} | {parsed.get('email')}")

        # Duplicate check after extraction
        existing = await get_application_by_email(parsed.get("email", ""))
        if existing:
            raise HTTPException(status_code=409, detail=f"Already applied on {str(existing.get('created_at',''))[:10]}. Decision: {existing.get('decision')}.")

        # Steps 2-5: matching -> decision -> scheduler -> email
        result, _ = await run_pipeline(client, parsed, source="pdf_upload", filename=file.filename, job_id=job_id, company=company)

    print(f"[Orchestrator] PDF done: {result.candidate} -> {result.decision}")
    return result


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000, reload=True)