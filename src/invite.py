"""Create a Google Meet space (guests join without knocking) and email the link to the candidate."""
import base64, html, re
from email.message import EmailMessage
import httpx
from . import config as C
from .google_auth import access_token

EMAIL_RE = re.compile(r"^[^@\s<>,;]+@[^@\s<>,;]+\.[^@\s<>,;]+$")

def _hdr():
    return {"Authorization": f"Bearer {access_token()}"}

def create_meeting() -> str:
    r = httpx.post("https://meet.googleapis.com/v2/spaces", headers=_hdr(), timeout=20,
                   json={"config": {"accessType": C.MEET_ACCESS}})
    if r.is_error: raise RuntimeError(f"Meet API {r.status_code}: {r.text}")
    j = r.json()
    print("Meet space created. Google applied access settings:", j.get("config"))
    return j["meetingUri"]

def build_message(to, name, url, job, when_text):
    n, role, co = html.escape(name or "there"), html.escape(job["title"]), html.escape(job["company"])
    bot = html.escape(C.BOT_NAME)
    text = (f"Hi {name or 'there'},\n\nYou are invited to an interview for {job['title']} at {job['company']}.\n\n"
            f"When: {when_text}\nJoin: {url}\n\n"
            f"Your interviewer is {C.BOT_NAME}, an AI assistant. The conversation is transcribed so the hiring team can review it. "
            f"You can answer in English, Hindi or Hinglish. It takes about {C.MAX_MINUTES} minutes.\n"
            "Tips: use a quiet place and headphones, and join a minute early. If Meet asks you to sign in, use this email address.\n\nGood luck!\n")
    page = (f"<p>Hi {n},</p><p>You are invited to an interview for <b>{role}</b> at <b>{co}</b>.</p>"
            f"<p><b>When:</b> {html.escape(when_text)}</p>"
            f'<p><a href="{html.escape(url)}" style="background:#1a73e8;color:#fff;padding:10px 18px;border-radius:6px;'
            f'text-decoration:none">Join the interview</a></p><p>{html.escape(url)}</p>'
            f"<p>Your interviewer is <b>{bot}</b>, an AI assistant. The conversation is transcribed so the hiring team can review it. "
            f"You can answer in <b>English, Hindi or Hinglish</b>. It takes about {C.MAX_MINUTES} minutes.</p>"
            "<p>Tips: use a quiet place and headphones, and join a minute early. If Meet asks you to sign in, use this email address.</p><p>Good luck!</p>")
    m = EmailMessage()
    m["To"] = to; m["Subject"] = f"Interview invitation: {job['title']} at {job['company']}"
    m.set_content(text); m.add_alternative(page, subtype="html")
    return m

def send_invite(to, name, url, job, when_text):
    if not EMAIL_RE.match(to or ""): raise ValueError(f"Invalid email address: {to!r}")
    raw = base64.urlsafe_b64encode(build_message(to, name, url, job, when_text).as_bytes()).decode()
    r = httpx.post("https://gmail.googleapis.com/gmail/v1/users/me/messages/send",
                   headers=_hdr(), json={"raw": raw}, timeout=20)
    if r.is_error: raise RuntimeError(f"Gmail API {r.status_code}: {r.text}")