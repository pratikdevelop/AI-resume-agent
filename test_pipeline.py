# test_pipeline.py
# Runs all 3 test candidates through the full A2A pipeline
# and prints a clean summary table.
#
# Usage: python test_pipeline.py

import urllib.request
import urllib.error
import json

BASE_URL = "http://localhost:8000"

CANDIDATES = [
    {
        "name": "Priya Sharma",
        "email": "priya@example.com",
        "years_experience": 5,
        "skills": ["Python", "FastAPI", "PostgreSQL", "Docker", "AWS"],
        "education": "B.Tech",
        "previous_roles": ["Backend Engineer", "Senior Developer"],
    },
    {
        "name": "Rahul Verma",
        "email": "rahul@example.com",
        "years_experience": 2,
        "skills": ["Python", "Django", "MySQL"],
        "education": "B.Sc",
        "previous_roles": ["Junior Developer"],
    },
    {
        "name": "Anjali Mehta",
        "email": "anjali@example.com",
        "years_experience": 4,
        "skills": ["Python", "FastAPI", "Docker", "Kubernetes"],
        "education": "M.Tech",
        "previous_roles": ["Software Engineer", "DevOps Engineer"],
    },
]

DECISION_ICON = {
    "SHORTLISTED": "✅",
    "WAITLISTED":  "⏳",
    "REJECTED":    "❌",
}


def post(url, data):
    body = json.dumps(data).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=15) as resp:
        return json.loads(resp.read().decode("utf-8"))


def check_health():
    try:
        with urllib.request.urlopen(f"{BASE_URL}/health", timeout=5) as r:
            health = json.loads(r.read())
        print("Health Check:")
        for agent, status in health["agents"].items():
            icon = "✅" if status == "ok" else "❌"
            print(f"  {icon}  {agent:<12} {status}")
        print()
        return all(s == "ok" for s in health["agents"].values())
    except Exception as e:
        print(f"❌ Cannot reach orchestrator: {e}")
        print("   Make sure all agents are running (start_all.bat)\n")
        return False


def run_tests():
    print("=" * 60)
    print("  A2A Job Application Pipeline — Test Runner")
    print("=" * 60)
    print()

    if not check_health():
        return

    results = []

    for candidate in CANDIDATES:
        print(f"Testing: {candidate['name']}...")
        try:
            result = post(f"{BASE_URL}/apply", candidate)
            results.append(result)
            icon = DECISION_ICON.get(result["decision"], "?")
            print(f"  {icon}  {result['decision']} | Score: {result['score']}/100")
            if result.get("interview_scheduled") and result.get("interview_slot"):
                slot = result["interview_slot"]
                print(f"  📅  Interview: {slot['date']} at {slot['time']}")
                print(f"      With    : {slot['interviewer']}")
                print(f"      Link    : {slot['meeting_link']}")
            elif not result.get("interview_scheduled"):
                print(f"  ⏭️   No interview scheduled")
        except urllib.error.URLError as e:
            print(f"  ❌ Request failed: {e}")
        print()

    # Summary table
    print("=" * 60)
    print(f"  {'CANDIDATE':<18} {'SCORE':>6}  {'DECISION':<12} {'INTERVIEW'}")
    print("-" * 60)
    for r in results:
        icon = DECISION_ICON.get(r["decision"], "?")
        interview = "Booked" if r.get("interview_scheduled") else "Skipped"
        print(f"  {r['candidate']:<18} {r['score']:>5.1f}  {icon} {r['decision']:<11} {interview}")
    print("=" * 60)


if __name__ == "__main__":
    run_tests()