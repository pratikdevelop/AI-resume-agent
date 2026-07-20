# agents/resume_agent.py
# Agent 1: Resume Parser
# Runs on port 8001
# Uses Docker Model Runner (docker run ai/llama3.2) - OpenAI-compatible API

from fastapi import FastAPI, HTTPException, UploadFile, File
from pydantic import BaseModel
from typing import List
import os
import json
import re
import httpx
import pymupdf
from dotenv import load_dotenv

load_dotenv()

# Docker Model Runner uses OpenAI-compatible API on port 12434
DOCKER_MODEL_URL = os.getenv("DOCKER_MODEL_URL", "http://localhost:11434")
DOCKER_MODEL     = os.getenv("DOCKER_MODEL",     "ai/llama3.2")

# Inline schemas
class RawResume(BaseModel):
    name: str
    email: str
    years_experience: int
    skills: List[str]
    education: str
    previous_roles: List[str] = []

class ParsedResume(BaseModel):
    name: str
    email: str
    years_experience: int
    skills: List[str]
    education: str
    previous_roles: List[str]

app = FastAPI(title="ResumeAgent (Docker Model Runner llama3.2)", version="3.0")


# ── PDF Text Extraction ────────────────────────────────────────────────────────

def extract_text_from_pdf(pdf_bytes: bytes) -> str:
    doc  = pymupdf.open(stream=pdf_bytes, filetype="pdf")
    text = ""
    for page in doc:
        text += page.get_text()
    doc.close()
    return text.strip()


# ── Docker Model Runner Parser ─────────────────────────────────────────────────

SYSTEM_PROMPT = """You are an expert resume parser. 
Extract information and return ONLY a valid JSON object with no extra text, no markdown.

Required format:
{
  "name": "Full name",
  "email": "email@example.com",
  "years_experience": 5,
  "skills": ["Python", "FastAPI", "Docker"],
  "education": "B.Tech",
  "previous_roles": ["Backend Engineer at XYZ"]
}

Rules:
- years_experience must be an integer
- skills must be individual technologies/tools/languages
- education should be degree type only
- Return ONLY the JSON, nothing else"""


async def parse_with_docker_model(resume_text: str) -> dict:
    """
    Uses Docker Model Runner's OpenAI-compatible /v1/chat/completions endpoint.
    """
    payload = {
        "model":       DOCKER_MODEL,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user",   "content": f"Parse this resume:\n\n{resume_text[:4000]}"},
        ],
        "temperature": 0,
        "max_tokens":  512,
    }

    print(f"[ResumeAgent] Sending to Docker Model Runner ({DOCKER_MODEL})...")

    async with httpx.AsyncClient(timeout=120.0) as client:
        response = await client.post(
            f"{DOCKER_MODEL_URL}/v1/chat/completions",
            json=payload,
            headers={"Content-Type": "application/json"},
        )
        response.raise_for_status()
        data = response.json()

    raw = data["choices"][0]["message"]["content"].strip()
    print(f"[ResumeAgent] Model response: {raw[:300]}...")

    # Strip markdown fences if present
    raw = re.sub(r"^```(?:json)?\s*", "", raw)
    raw = re.sub(r"\s*```$",          "", raw)

    # Extract JSON object in case there's surrounding text
    match = re.search(r"\{.*\}", raw, re.DOTALL)
    if match:
        raw = match.group(0)

    return json.loads(raw)


# ── Routes ─────────────────────────────────────────────────────────────────────

@app.get("/health")
async def health():
    model_status = "unreachable"
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            r = await client.get(f"{DOCKER_MODEL_URL}/v1/models")
            if r.status_code == 200:
                models = [m["id"] for m in r.json().get("data", [])]
                model_status = "ok" if any(DOCKER_MODEL in m for m in models) else f"'{DOCKER_MODEL}' not found — available: {models}"
    except Exception as e:
        model_status = f"unreachable: {str(e)}"

    return {
        "agent":        "ResumeAgent",
        "status":       "ok",
        "port":         8001,
        "model_url":    DOCKER_MODEL_URL,
        "model":        DOCKER_MODEL,
        "model_status": model_status,
        "modes":        ["POST /parse (JSON)", "POST /parse-pdf (PDF upload)"],
    }


@app.post("/parse", response_model=ParsedResume)
def parse_resume(resume: RawResume) -> ParsedResume:
    """Original JSON mode — unchanged."""
    try:
        parsed = ParsedResume(
            name=resume.name.strip(),
            email=resume.email.strip().lower(),
            years_experience=resume.years_experience,
            skills=[s.strip().lower() for s in resume.skills],
            education=resume.education.strip(),
            previous_roles=resume.previous_roles,
        )
        print(f"[ResumeAgent] JSON parsed: {parsed.name}")
        return parsed
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Parsing failed: {str(e)}")


@app.post("/parse-pdf", response_model=ParsedResume)
async def parse_pdf(file: UploadFile = File(...)) -> ParsedResume:
    """
    Upload PDF -> PyMuPDF extracts text -> llama3.2 (Docker Model Runner) parses it
    -> returns structured ParsedResume for the pipeline.
    """
    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files accepted.")

    pdf_bytes = await file.read()
    if len(pdf_bytes) > 10 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="PDF too large. Max 10MB.")

    print(f"[ResumeAgent] PDF: {file.filename} ({len(pdf_bytes)} bytes)")

    # Step 1: Extract text
    try:
        resume_text = extract_text_from_pdf(pdf_bytes)
        print(f"[ResumeAgent] Extracted {len(resume_text)} chars from PDF")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"PDF extraction failed: {str(e)}")

    if not resume_text:
        raise HTTPException(status_code=400, detail="No text found in PDF. Is it a scanned image?")

    # Step 2: Parse with llama3.2
    try:
        extracted = await parse_with_docker_model(resume_text)
    except httpx.ConnectError:
        raise HTTPException(
            status_code=503,
            detail=f"Docker Model Runner unreachable at {DOCKER_MODEL_URL}. Make sure Docker Desktop is running and the model is started."
        )
    except json.JSONDecodeError as e:
        raise HTTPException(status_code=500, detail=f"Model returned invalid JSON: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"LLM parsing failed: {str(e)}")

    # Step 3: Build ParsedResume
    parsed = ParsedResume(
        name=str(extracted.get("name", "Unknown")).strip(),
        email=str(extracted.get("email", "")).strip().lower(),
        years_experience=int(extracted.get("years_experience", 0)),
        skills=[s.strip().lower() for s in extracted.get("skills", [])],
        education=str(extracted.get("education", "")).strip(),
        previous_roles=extracted.get("previous_roles", []),
    )

    print(f"[ResumeAgent] Done: {parsed.name} | {len(parsed.skills)} skills | {parsed.years_experience} yrs exp")
    return parsed


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)