# agents/email_agent.py
# Agent 4: Real Email Sender via Gmail SMTP
# Runs on port 8004
# Now accepts optional interview_slot and includes it in shortlist emails

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import Optional, List
from enum import Enum
import smtplib
import os
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from dotenv import load_dotenv

load_dotenv(override=True)
print(f"[EmailAgent] GMAIL_SENDER={repr(os.getenv('GMAIL_SENDER'))}")
print(f"[EmailAgent] APP_PASSWORD length={len(os.getenv('GMAIL_APP_PASSWORD') or '')}")

GMAIL_SENDER       = os.getenv("GMAIL_SENDER")
GMAIL_APP_PASSWORD = os.getenv("GMAIL_APP_PASSWORD")
HR_EMAIL           = os.getenv("HR_EMAIL", os.getenv("GMAIL_SENDER"))  # defaults to sender


# Inline schemas
class Decision(str, Enum):
    SHORTLISTED = "SHORTLISTED"
    WAITLISTED  = "WAITLISTED"
    REJECTED    = "REJECTED"

class InterviewSlot(BaseModel):
    date: str
    time: str
    duration_minutes: int
    interviewer: str
    meeting_link: str
    calendar_id: str

class DecisionResult(BaseModel):
    candidate_name: str
    candidate_email: str
    job_title: str
    score: float
    decision: Decision
    reason: str
    required_skills_matched: List[str]
    interview_slot: Optional[InterviewSlot] = None   # injected by orchestrator

class EmailResult(BaseModel):
    status: str
    recipient: str
    decision: Decision
    subject: str
    body: str


app = FastAPI(title="EmailAgent (Real Gmail)", version="2.0")


def format_skills(skills: list) -> str:
    return "\n".join(f"  - {s.capitalize()}" for s in skills) if skills else "  - (general experience)"


def build_email_body(decision: DecisionResult) -> tuple[str, str]:
    """Returns (subject, body) based on decision and optional interview slot."""

    slot = decision.interview_slot

    if decision.decision == Decision.SHORTLISTED:
        subject = f"You've Been Shortlisted - {decision.job_title} at TechCorp"

        if slot:
            interview_section = f"""
Your interview has been scheduled! Here are the details:

  Date        : {slot.date}
  Time        : {slot.time} (IST)
  Duration    : {slot.duration_minutes} minutes
  Interviewer : {slot.interviewer}
  Meeting Link: {slot.meeting_link}

Please join the meeting link 5 minutes early. If you need to reschedule,
reply to this email at least 24 hours in advance.
"""
        else:
            interview_section = """
Our recruitment team will contact you within 2 business days to
schedule a technical interview.
"""

        body = f"""Dear {decision.candidate_name},

We are thrilled to inform you that after reviewing your application
for the {decision.job_title} role, you have been SHORTLISTED!

Your profile stood out, particularly your experience with:
{format_skills(decision.required_skills_matched)}
{interview_section}
Best regards,
HR Team - TechCorp
"""

    elif decision.decision == Decision.WAITLISTED:
        subject = f"Update on Your Application - {decision.job_title}"
        body = f"""Dear {decision.candidate_name},

Thank you for applying for the {decision.job_title} position at TechCorp.

After careful review, your application has been placed on our WAITLIST.
We were impressed by your background but currently have candidates whose
skills more closely match our immediate needs.

We will reach out if a suitable opportunity arises.

Best regards,
HR Team - TechCorp
"""

    else:  # REJECTED
        subject = f"Your Application for {decision.job_title} at TechCorp"
        body = f"""Dear {decision.candidate_name},

Thank you for your interest in the {decision.job_title} position at TechCorp.

After reviewing your application, we have decided to move forward with
other candidates whose qualifications more closely match the current role.

We encourage you to apply for future openings and wish you all the best.

Best regards,
HR Team - TechCorp
"""

    return subject, body


def send_gmail(to: str, subject: str, body: str):
    if not GMAIL_SENDER or not GMAIL_APP_PASSWORD:
        raise ValueError("GMAIL_SENDER and GMAIL_APP_PASSWORD must be set in .env")

    # Strip any accidental whitespace/quotes from env vars
    sender   = GMAIL_SENDER.strip().strip('"').strip("'")
    password = GMAIL_APP_PASSWORD.strip().replace(' ', '')  # strip spaces from app password
    recipient = to.strip()

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"]    = sender          # plain email only — no display name (avoids RFC 5321 errors)
    msg["To"]      = recipient
    msg["Reply-To"] = sender
    msg.attach(MIMEText(body, "plain", "utf-8"))

    print(f"[EmailAgent] Connecting to Gmail SMTP as {sender} (pwd len={len(password)})...")
    try:
        with smtplib.SMTP("smtp.gmail.com", 587, timeout=15) as server:
            server.ehlo()
            server.starttls()
            server.ehlo()
            r = server.login(sender, password)
            print(f"[EmailAgent] Login response: {r}")
            r2 = server.sendmail(sender, [recipient], msg.as_string())
            print(f"[EmailAgent] Sendmail response: {r2}")
        print(f"[EmailAgent] Email delivered to {recipient}")
    except Exception as smtp_err:
        import traceback
        print(f"[EmailAgent] SMTP ERROR: {smtp_err}")
        print(traceback.format_exc())
        raise


def build_interviewer_email(decision: DecisionResult) -> tuple[str, str]:
    """Email sent to the interviewer/HR when a candidate is shortlisted."""
    slot = decision.interview_slot
    subject = f"[Interview Scheduled] {decision.candidate_name} — {decision.job_title}"
    body = f"""Hi {slot.interviewer if slot else 'Team'},

A candidate has been SHORTLISTED and an interview has been automatically scheduled.

Candidate Details:
  Name      : {decision.candidate_name}
  Email     : {decision.candidate_email}
  Role      : {decision.job_title}
  Score     : {decision.score}/100
  Skills    : {', '.join(decision.required_skills_matched)}

Interview Details:
  Date      : {slot.date if slot else 'TBD'}
  Time      : {slot.time + ' (IST)' if slot else 'TBD'}
  Duration  : {slot.duration_minutes if slot else 60} minutes
  Link      : {slot.meeting_link if slot else 'TBD'}

Please be available on the meeting link at the scheduled time.
The candidate has been notified with the same details.

— A2A Hiring Pipeline (Automated)
"""
    return subject, body


@app.get("/health")
def health():
    configured = bool(GMAIL_SENDER and GMAIL_APP_PASSWORD)
    return {
        "agent": "EmailAgent",
        "status": "ok",
        "port": 8004,
        "gmail_configured": configured,
        "sender": GMAIL_SENDER or "NOT SET",
    }


@app.post("/send-email", response_model=EmailResult)
def send_email(decision: DecisionResult) -> EmailResult:
    try:
        subject, body = build_email_body(decision)

        print(f"\n[EmailAgent] Sending to {decision.candidate_email}")
        print(f"  Subject  : {subject}")
        print(f"  Decision : {decision.decision.value}")
        if decision.interview_slot:
            print(f"  Slot     : {decision.interview_slot.date} {decision.interview_slot.time}")

        send_gmail(to=decision.candidate_email, subject=subject, body=body)

        # Send interviewer notification for shortlisted candidates
        if decision.decision == Decision.SHORTLISTED and decision.interview_slot:
            slot = decision.interview_slot
            # Send to the specific interviewer if they have an email, else HR
            interviewer_email = getattr(slot, "interviewer_email", "") or HR_EMAIL
            recipients = list({e for e in [interviewer_email, HR_EMAIL] if e})
            try:
                int_subject, int_body = build_interviewer_email(decision)
                for recipient_email in recipients:
                    send_gmail(to=recipient_email, subject=int_subject, body=int_body)
                    print(f"[EmailAgent] Interview notification sent to {recipient_email}")
            except Exception as hr_err:
                print(f"[EmailAgent] WARNING: Interviewer email failed: {hr_err}")
                # Don't fail the whole pipeline if interviewer email fails

        return EmailResult(
            status="sent",
            recipient=decision.candidate_email,
            decision=decision.decision,
            subject=subject,
            body=body,
        )

    except ValueError as e:
        raise HTTPException(status_code=503, detail=str(e))
    except smtplib.SMTPAuthenticationError:
        raise HTTPException(status_code=401, detail="Gmail authentication failed. Check .env")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Email sending failed: {str(e)}")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8004)