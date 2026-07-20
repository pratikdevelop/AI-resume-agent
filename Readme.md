# A2A Job Application Processor

A fully working Agent-to-Agent (A2A) hiring pipeline built with FastAPI, MongoDB, and local AI (llama3.2).

## Architecture

```
POST /apply     (JSON)
POST /apply-pdf (PDF upload → llama3.2 AI parsing)
        │
        ▼
Orchestrator :8000
        │
        ├── ResumeAgent    :8001  (parse resume / extract PDF with llama3.2)
        ├── MatchingAgent  :8002  (score candidate vs job requirements)
        ├── DecisionAgent  :8003  (shortlist / waitlist / reject)
        ├── SchedulerAgent :8005  (book interview via Google Calendar / Jitsi)
        └── EmailAgent     :8004  (send real email via Gmail)
        │
        ▼
MongoDB Atlas (persist all results)
Dashboard: http://localhost:8000/dashboard
```

## Quick Start (Local)

```bash
pip install -r requirements.txt
# Fill in your .env file (see .env.example)
start_all.bat
```

## Quick Start (Docker)

```bash
# Make sure Docker Desktop is running
docker-compose up --build
```

All services start automatically. Visit http://localhost:8000/dashboard

## Environment Variables (.env)

```
GMAIL_SENDER=yourname@gmail.com
GMAIL_APP_PASSWORD=your-16-char-app-password
GOOGLE_CALENDAR_ID=yourname@gmail.com
GOOGLE_CREDENTIALS_FILE=credentials.json
TIMEZONE=Asia/Kolkata
MONGO_URI=mongodb+srv://user:pass@cluster.mongodb.net/
MONGO_DB=a2a_hiring
API_KEY=your-secret-api-key
DOCKER_MODEL_URL=http://localhost:12434
DOCKER_MODEL=ai/llama3.2
```

## API Endpoints

| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| GET | /dashboard | None | Visual hiring dashboard |
| GET | /health | None | All agent health check |
| POST | /apply | API Key | Submit via JSON |
| POST | /apply-pdf | API Key | Submit via PDF upload |
| GET | /applications | API Key | List all applications |
| GET | /stats | API Key | Aggregated stats |

## Test (PowerShell 7 / curl)

```bash
# JSON
curl.exe -X POST http://localhost:8000/apply \
  -H "X-Api-Key: your-key" \
  -H "Content-Type: application/json" \
  -d '{"name":"Priya Sharma","email":"priya@example.com","years_experience":5,"skills":["Python","FastAPI","Docker"],"education":"B.Tech","previous_roles":["Backend Engineer"]}'

# PDF
curl.exe -X POST http://localhost:8000/apply-pdf \
  -H "X-Api-Key: your-key" \
  -F "file=@resume.pdf"
```