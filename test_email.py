"""
Run this directly to test Gmail SMTP:
  python test_email.py
"""
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

SENDER   = "pratik.raut9115@gmail.com"
PASSWORD = "lzfviqpwbelglini"   # no spaces
TO       = "pratik.raut9115@gmail.com"

print(f"Sender  : {repr(SENDER)}")
print(f"Password: {repr(PASSWORD)}")
print(f"Length  : {len(PASSWORD)}")
print()

msg = MIMEMultipart()
msg["Subject"] = "A2A Test Email"
msg["From"]    = SENDER
msg["To"]      = TO
msg.attach(MIMEText("This is a test from A2A pipeline.", "plain", "utf-8"))

print("Trying port 587 + STARTTLS...")
try:
    with smtplib.SMTP("smtp.gmail.com", 587, timeout=15) as s:
        s.ehlo()
        s.starttls()
        s.ehlo()
        s.login(SENDER, PASSWORD)
        s.sendmail(SENDER, [TO], msg.as_string())
    print("SUCCESS! Email sent via port 587")
except Exception as e:
    print(f"FAILED port 587: {e}")

print()
print("Trying port 465 + SSL...")
try:
    with smtplib.SMTP_SSL("smtp.gmail.com", 465, timeout=15) as s:
        s.ehlo()
        s.login(SENDER, PASSWORD)
        s.sendmail(SENDER, [TO], msg.as_string())
    print("SUCCESS! Email sent via port 465")
except Exception as e:
    print(f"FAILED port 465: {e}")