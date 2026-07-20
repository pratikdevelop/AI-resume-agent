#!/bin/bash
# start_all.sh — starts all 5 services in background processes

echo "🚀 Starting A2A Job Application Processor..."
echo ""

# Kill any existing instances
pkill -f "uvicorn agents" 2>/dev/null
pkill -f "uvicorn orchestrator" 2>/dev/null
sleep 1

# Start all agents
echo "Starting ResumeAgent   on :8001..."
uvicorn agents.resume_agent:app   --port 8001 --log-level warning &

echo "Starting MatchingAgent  on :8002..."
uvicorn agents.matching_agent:app --port 8002 --log-level warning &

echo "Starting DecisionAgent  on :8003..."
uvicorn agents.decision_agent:app --port 8003 --log-level warning &

echo "Starting EmailAgent     on :8004..."
uvicorn agents.email_agent:app    --port 8004 --log-level warning &

echo "Starting Orchestrator   on :8000..."
uvicorn orchestrator:app    --port 8000 --log-level info &

sleep 2
echo ""
echo "✅ All agents running!"
echo ""
echo "📬 Submit an application:"
echo 'curl -X POST http://localhost:8000/apply \'
echo '  -H "Content-Type: application/json" \'
echo '  -d @test_candidates/priya.json'
echo ""
echo "❤️  Health check:"
echo "curl http://localhost:8000/health"
echo ""
echo "Press Ctrl+C to stop all agents."
wait