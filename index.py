"""
A2A (Agent-to-Agent) Job Application Processor
================================================
Flow: Resume Agent → Matching Agent → Decision Agent → Email Agent

Each agent is a class that:
  1. Receives a message/payload from another agent
  2. Does its job
  3. Passes results to the next agent
"""

import json
import time
import random

# ─────────────────────────────────────────────
# SHARED MESSAGE BUS (simulates A2A messaging)
# ─────────────────────────────────────────────
class MessageBus:
    """Simple in-memory message bus for agent-to-agent communication."""
    def __init__(self):
        self.messages = []

    def send(self, sender, receiver, payload):
        msg = {
            "id": len(self.messages) + 1,
            "from": sender,
            "to": receiver,
            "timestamp": time.strftime("%H:%M:%S"),
            "payload": payload
        }
        self.messages.append(msg)
        print(f"\n📨  [{msg['timestamp']}] {sender} → {receiver}")
        print(f"    Payload: {json.dumps(payload, indent=6)}")
        return msg


# ─────────────────────────────────────────────
# AGENT 1: RESUME AGENT
# Parses the raw resume and extracts structured data
# ─────────────────────────────────────────────
class ResumeAgent:
    NAME = "ResumeAgent"

    def __init__(self, bus: MessageBus):
        self.bus = bus

    def process(self, raw_resume: dict):
        print(f"\n{'='*55}")
        print(f"🤖  {self.NAME}: Parsing resume...")

        # Simulate NLP extraction
        parsed = {
            "name": raw_resume.get("name"),
            "email": raw_resume.get("email"),
            "years_experience": raw_resume.get("years_experience", 0),
            "skills": [s.lower() for s in raw_resume.get("skills", [])],
            "education": raw_resume.get("education", "Unknown"),
            "previous_roles": raw_resume.get("previous_roles", []),
        }

        print(f"    ✅ Extracted: {parsed['name']} | Skills: {parsed['skills']}")

        # Send to Matching Agent
        self.bus.send(
            sender=self.NAME,
            receiver=MatchingAgent.NAME,
            payload={"parsed_resume": parsed}
        )
        return parsed


# ─────────────────────────────────────────────
# AGENT 2: MATCHING AGENT
# Compares resume against job requirements and scores the candidate
# ─────────────────────────────────────────────
class MatchingAgent:
    NAME = "MatchingAgent"

    JOB_REQUIREMENTS = {
        "title": "Senior Python Developer",
        "required_skills": ["python", "fastapi", "postgresql", "docker"],
        "preferred_skills": ["kubernetes", "aws", "redis"],
        "min_experience_years": 3,
        "education_preference": ["B.Tech", "M.Tech", "B.Sc", "M.Sc", "BE", "ME"],
    }

    def __init__(self, bus: MessageBus):
        self.bus = bus

    def process(self, parsed_resume: dict):
        print(f"\n{'='*55}")
        print(f"🤖  {self.NAME}: Scoring candidate against job requirements...")

        req = self.JOB_REQUIREMENTS
        candidate_skills = parsed_resume["skills"]

        # Skill match scoring
        required_matched = [s for s in req["required_skills"] if s in candidate_skills]
        preferred_matched = [s for s in req["preferred_skills"] if s in candidate_skills]

        skill_score = (len(required_matched) / len(req["required_skills"])) * 60
        preferred_score = (len(preferred_matched) / len(req["preferred_skills"])) * 20

        # Experience score
        exp_score = min(parsed_resume["years_experience"] / req["min_experience_years"], 1) * 20

        total_score = round(skill_score + preferred_score + exp_score, 1)

        result = {
            "candidate_name": parsed_resume["name"],
            "candidate_email": parsed_resume["email"],
            "job_title": req["title"],
            "score": total_score,
            "required_skills_matched": required_matched,
            "preferred_skills_matched": preferred_matched,
            "experience_years": parsed_resume["years_experience"],
            "parsed_resume": parsed_resume,
        }

        print(f"    ✅ Score: {total_score}/100 | Required Skills: {required_matched}")

        self.bus.send(
            sender=self.NAME,
            receiver=DecisionAgent.NAME,
            payload={"match_result": result}
        )
        return result


# ─────────────────────────────────────────────
# AGENT 3: DECISION AGENT
# Makes the hire / reject / waitlist decision
# ─────────────────────────────────────────────
class DecisionAgent:
    NAME = "DecisionAgent"

    THRESHOLDS = {
        "shortlist": 70,
        "waitlist": 45,
    }

    def __init__(self, bus: MessageBus):
        self.bus = bus

    def process(self, match_result: dict):
        print(f"\n{'='*55}")
        print(f"🤖  {self.NAME}: Making hiring decision...")

        score = match_result["score"]

        if score >= self.THRESHOLDS["shortlist"]:
            decision = "SHORTLISTED"
            reason = f"Strong candidate with score {score}/100. Matched required skills: {match_result['required_skills_matched']}."
        elif score >= self.THRESHOLDS["waitlist"]:
            decision = "WAITLISTED"
            reason = f"Moderate candidate with score {score}/100. Missing some key skills."
        else:
            decision = "REJECTED"
            reason = f"Candidate scored {score}/100, below the minimum threshold of {self.THRESHOLDS['waitlist']}."

        result = {
            **match_result,
            "decision": decision,
            "reason": reason,
        }

        print(f"    ✅ Decision: {decision} (Score: {score})")

        self.bus.send(
            sender=self.NAME,
            receiver=EmailAgent.NAME,
            payload={"decision_result": result}
        )
        return result


# ─────────────────────────────────────────────
# AGENT 4: EMAIL AGENT
# Composes and "sends" a personalized email to the candidate
# ─────────────────────────────────────────────
class EmailAgent:
    NAME = "EmailAgent"

    TEMPLATES = {
        "SHORTLISTED": """
Subject: 🎉 Exciting News About Your Application – {job_title}

Dear {name},

We reviewed your application for the role of {job_title} and we are thrilled
to inform you that you have been SHORTLISTED for the next round!

Your profile impressed us, particularly your experience with:
{skills}

Our recruitment team will reach out within 2 business days to schedule
a technical interview.

Best regards,
HR Team – TechCorp
        """,
        "WAITLISTED": """
Subject: Update on Your Application – {job_title}

Dear {name},

Thank you for applying for the {job_title} role.

After careful review, we have placed your application on our WAITLIST.
We were impressed by your profile but currently have candidates whose
skills more closely match our immediate needs.

We will contact you if a suitable opening arises.

Best regards,
HR Team – TechCorp
        """,
        "REJECTED": """
Subject: Your Application for {job_title}

Dear {name},

Thank you for your interest in the {job_title} position at TechCorp.

After reviewing your application, we have decided to move forward with
other candidates whose qualifications more closely match the current role.

We encourage you to apply for future openings and wish you the best.

Best regards,
HR Team – TechCorp
        """,
    }

    def __init__(self, bus: MessageBus):
        self.bus = bus

    def process(self, decision_result: dict):
        print(f"\n{'='*55}")
        print(f"🤖  {self.NAME}: Composing email...")

        template = self.TEMPLATES[decision_result["decision"]]
        skills_list = "\n".join(f"  • {s}" for s in decision_result["required_skills_matched"]) or "  • (general experience)"

        email_body = template.format(
            name=decision_result["candidate_name"],
            job_title=decision_result["job_title"],
            skills=skills_list,
        )

        print(f"\n{'─'*55}")
        print(f"📧  EMAIL TO: {decision_result['candidate_email']}")
        print(email_body)
        print(f"{'─'*55}")
        print(f"    ✅ Email sent to {decision_result['candidate_email']}")

        self.bus.send(
            sender=self.NAME,
            receiver="Orchestrator",
            payload={
                "status": "COMPLETE",
                "candidate": decision_result["candidate_name"],
                "decision": decision_result["decision"],
                "email_sent_to": decision_result["candidate_email"],
            }
        )
        return email_body


# ─────────────────────────────────────────────
# ORCHESTRATOR
# Wires all agents together and kicks off the flow
# ─────────────────────────────────────────────
class Orchestrator:
    def __init__(self):
        self.bus = MessageBus()
        self.resume_agent = ResumeAgent(self.bus)
        self.matching_agent = MatchingAgent(self.bus)
        self.decision_agent = DecisionAgent(self.bus)
        self.email_agent = EmailAgent(self.bus)

    def run(self, raw_resume: dict):
        print(f"\n{'#'*55}")
        print(f"🚀  ORCHESTRATOR: Starting A2A pipeline for {raw_resume['name']}")
        print(f"{'#'*55}")

        # Agent 1 → parses resume
        parsed = self.resume_agent.process(raw_resume)

        # Agent 2 → scores the candidate
        match_result = self.matching_agent.process(parsed)

        # Agent 3 → makes hiring decision
        decision_result = self.decision_agent.process(match_result)

        # Agent 4 → sends email
        self.email_agent.process(decision_result)

        print(f"\n{'#'*55}")
        print(f"✅  PIPELINE COMPLETE | Total messages on bus: {len(self.bus.messages)}")
        print(f"{'#'*55}\n")


# ─────────────────────────────────────────────
# MAIN — Run with 3 different candidate profiles
# ─────────────────────────────────────────────
if __name__ == "__main__":

    candidates = [
        {
            "name": "Priya Sharma",
            "email": "priya.sharma@email.com",
            "years_experience": 5,
            "skills": ["Python", "FastAPI", "PostgreSQL", "Docker", "AWS", "Redis"],
            "education": "B.Tech",
            "previous_roles": ["Backend Engineer", "Senior Developer"],
        },
        {
            "name": "Rahul Verma",
            "email": "rahul.verma@email.com",
            "years_experience": 2,
            "skills": ["Python", "Django", "MySQL"],
            "education": "B.Sc",
            "previous_roles": ["Junior Developer"],
        },
        {
            "name": "Anjali Mehta",
            "email": "anjali.mehta@email.com",
            "years_experience": 4,
            "skills": ["Python", "FastAPI", "Docker", "Kubernetes"],
            "education": "M.Tech",
            "previous_roles": ["Software Engineer", "DevOps Engineer"],
        },
    ]

    orchestrator = Orchestrator()

    for candidate in candidates:
        orchestrator.run(candidate)
        print("\n" + "="*55 + "\n")