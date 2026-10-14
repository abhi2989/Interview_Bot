# AI Interview Bot (Google Meet + Groq + Sarvam)

```
Candidate joins Meet --> Bot (Chromium via Playwright, named account + avatar)
   ^                         |
   | bot voice               v
 bot_mic sink <-- Sarvam TTS <-- Groq agent <-- Sarvam STT <-- VAD <-- meeting_out sink (candidate audio)
                                   |
                       JD + resume + rules + history
                                   v
                 per-answer evaluation (score + verbatim evidence)
                                   v
                       report.json / report.md + transcript
```

## Run
1. `cp .env.example .env` and fill GROQ_API_KEY / SARVAM_API_KEY.
2. Create a dedicated Google account ("Aria - AI Interviewer", add profile photo). Locally:
   `pip install playwright && playwright install chrome && python -m src.login_once` -> `data/auth.json`
3. Edit `data/job.json` and `data/resume.txt`.
4. `docker build -t interview-bot .`
   `docker run --rm --env-file .env -v $PWD/data:/app/data -v $PWD/output:/app/output interview-bot --meet-url https://meet.google.com/xxx-xxxx-xxx`
5. Open the report in `output/`.

## Important notes
- Meet has no official "bot join + raw audio" API for general use. This uses browser automation: Meet UI selectors in `src/meet.py` can change and need maintenance. The host must admit the bot unless it is invited/in the same org.
  For production, consider the Google Meet Media API (developer preview) or a managed meeting-bot provider.
- Verify Sarvam model/speaker names and REST clip limits in their docs; STT is chunked at 25s here. Their streaming STT would cut latency further.
- Compliance: the bot discloses it is AI and that the call is transcribed. Get explicit candidate consent for recording, store data securely
  (India DPDP, GDPR, etc.), and keep a human making the hiring decision (scores are advisory; some jurisdictions regulate automated hiring tools).
- Not covered yet: barge-in (candidate interrupting the bot), multi-candidate scheduling, a database, a recruiter dashboard.
