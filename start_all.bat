@echo off
echo ========================================
echo  A2A Job Application Processor v2.0
echo  5-Agent Pipeline
echo ========================================
echo.

echo [1/5] Starting ResumeAgent   on port 8001...
start "ResumeAgent   :8001" cmd /k "uvicorn agents.resume_agent:app --port 8001"

echo [2/5] Starting MatchingAgent  on port 8002...
start "MatchingAgent :8002" cmd /k "uvicorn agents.matching_agent:app --port 8002"

echo [3/5] Starting DecisionAgent  on port 8003...
start "DecisionAgent :8003" cmd /k "uvicorn agents.decision_agent:app --port 8003"

echo [4/5] Starting EmailAgent     on port 8004...
start "EmailAgent    :8004" cmd /k "uvicorn agents.email_agent:app --port 8004"

echo [5/5] Starting SchedulerAgent on port 8005...
start "SchedulerAgent:8005" cmd /k "uvicorn agents.scheduler_agent:app --port 8005"

timeout /t 3 /nobreak >nul

echo.
echo Starting Orchestrator on port 8000...
start "Orchestrator  :8000" cmd /k "uvicorn orchestrator:app --port 8000 --reload"

timeout /t 2 /nobreak >nul

echo.
echo ========================================
echo  All 6 services are running!
echo ========================================
echo.
echo  Swagger UI  : http://localhost:8000/docs
echo  Health check: http://localhost:8000/health
echo.
echo  Test with PowerShell:
echo.
echo  Invoke-RestMethod -Uri "http://localhost:8000/apply" -Method POST -ContentType "application/json" -Body '{
echo    "name": "Priya Sharma",
echo    "email": "priya@example.com",
echo    "years_experience": 5,
echo    "skills": ["Python","FastAPI","PostgreSQL","Docker","AWS"],
echo    "education": "B.Tech",
echo    "previous_roles": ["Backend Engineer"]
echo  }'
echo.
pause