# import argparse, asyncio, json, os, time
# from . import sarvam
# from .audio import Ear, Speaker
# from .agent import InterviewAgent
# from .meet import MeetBot
# from .report import build

# async def one(text):
#     yield text

# async def run(a):
#     job = json.load(open(a.job)); resume = open(a.resume).read()
#     os.makedirs(a.out, exist_ok=True)
#     transcript, t0 = [], time.time()
#     stamp = lambda: time.strftime("%M:%S", time.gmtime(time.time() - t0))

#     bot = MeetBot(); await bot.join(a.meet_url)
#     if not await bot.wait_for_candidate(): print("Candidate never joined"); await bot.leave(); return
#     t0 = time.time()
#     ear, speaker, agent = Ear(), Speaker(), InterviewAgent(job, resume)
#     state = {"present": True}

#     async def watch_presence():           # off the hot path: never slows a turn
#         misses = 0
#         while True:
#             n = await bot.participant_count()
#             misses = misses + 1 if (n is not None and n < 2) else 0
#             state["present"] = misses < 2
#             await asyncio.sleep(5)
#     pres = asyncio.create_task(watch_presence())

#     async def say(stream):
#         spoken, pre = await speaker.say(stream, ear)
#         if spoken: transcript.append({"time": stamp(), "speaker": "Interviewer", "text": spoken})
#         if pre is not None: agent.mark_interrupted(spoken)
#         return pre

#     pre, silent = await say(agent.stream_question(None)), 0
#     while not agent.done and state["present"]:
#         if pre is None: pre = await asyncio.to_thread(ear.wait_onset, 45)
#         pcm = await asyncio.to_thread(ear.collect, pre) if pre else None
#         pre = None
#         text = await asyncio.to_thread(sarvam.stt, pcm) if pcm else ""
#         if len(text) < 3:
#             silent += 1
#             if silent >= 3: print("No response; ending"); break
#             pre = await say(one("Sorry, I didn't catch that. Could you please say it again?")); continue
#         silent = 0
#         transcript.append({"time": stamp(), "speaker": "Candidate", "text": text})
#         pre = await say(agent.stream_question(text))
#     pres.cancel()
#     await asyncio.gather(*agent.eval_tasks, return_exceptions=True)
#     await bot.leave()
#     await build(job, resume, agent.turns, transcript, a.out)
#     print(f"Report written to {a.out}/report.md")

# if __name__ == "__main__":
#     ap = argparse.ArgumentParser()
#     ap.add_argument("--meet-url", required=True); ap.add_argument("--job", default="data/job.json")
#     ap.add_argument("--resume", default="data/resume.txt"); ap.add_argument("--out", default="output")
#     asyncio.run(run(ap.parse_args()))







# import argparse, asyncio, json, os, re, sys, time
# from datetime import datetime, timedelta, timezone
# from . import sarvam, config as C, lang as L, invite
# from .audio import Ear, Speaker
# from .agent import InterviewAgent
# from .meet import MeetBot
# from .report import build

# async def one(text):
#     yield text

# def parse_start(s):
#     dt = datetime.fromisoformat(s.strip().replace("Z", "+00:00").replace(" ", "T", 1))
#     if dt.tzinfo is None:
#         sign = -1 if C.TZ_OFFSET.startswith("-") else 1
#         h, m = C.TZ_OFFSET.lstrip("+-").split(":")
#         dt = dt.replace(tzinfo=timezone(sign * timedelta(hours=int(h), minutes=int(m))))
#     return dt

# def slug(s): return re.sub(r"[^a-z0-9]+", "-", (s or "").lower()).strip("-") or "candidate"

# async def run(a):
#     job = json.load(open(a.job)); resume = open(a.resume).read()
#     start = parse_start(a.start_at) if a.start_at else None
#     url = a.meet_url
#     if not url:
#         if not a.candidate_email: sys.exit("Give --candidate-email (bot creates + emails the link) or --meet-url")
#         url = await asyncio.to_thread(invite.create_meeting)
#         print("Meeting created:", url)
#     if a.candidate_email:
#         when = f"{start:%A, %d %b %Y at %I:%M %p} {C.TZ_LABEL}" if start else "Now, please join as soon as you can"
#         try:
#             await asyncio.to_thread(invite.send_invite, a.candidate_email, a.candidate_name, url, job, when)
#             print("Invitation emailed to", a.candidate_email)
#         except Exception as e:
#             print("INVITE EMAIL FAILED:", e, "\nSend this link to the candidate yourself:", url)
#     out = a.out or f"output/{slug(a.candidate_name)}-{time.strftime('%Y%m%d-%H%M')}"
#     os.makedirs(out, exist_ok=True)
#     json.dump({"candidate": a.candidate_name, "email": a.candidate_email, "meet_url": url,
#                "scheduled": start.isoformat() if start else None}, open(f"{out}/session.json", "w"), indent=2)
#     if start:
#         wait = (start - datetime.now(timezone.utc)).total_seconds() - 60
#         if wait > 0: print(f"Waiting {wait/60:.0f} min until the interview time..."); await asyncio.sleep(wait)

#     transcript, t0 = [], time.time()
#     stamp = lambda: time.strftime("%M:%S", time.gmtime(time.time() - t0))
#     ear, speaker = Ear(), Speaker()
#     bot = MeetBot(); await bot.join(url)
#     if not await bot.wait_for_candidate(C.WAIT_MINUTES * 60):
#         print("Candidate never joined"); await bot.leave(); return
#     t0 = time.time(); ear.flush()
#     agent = InterviewAgent(job, resume)
#     state = {"present": True}

#     async def watch_presence():           # off the hot path: never slows a turn
#         misses = 0
#         while True:
#             n = await bot.participant_count()
#             misses = misses + 1 if (n is not None and n < 2) else 0
#             state["present"] = misses < 2
#             await asyncio.sleep(5)
#     pres = asyncio.create_task(watch_presence())

#     async def say(stream):
#         try: spoken, pre = await speaker.say(stream, ear)
#         except Exception as e:
#             print("turn failed:", repr(e)); return None
#         if spoken: transcript.append({"time": stamp(), "speaker": "Interviewer", "text": spoken})
#         if pre is not None: agent.mark_interrupted(spoken)
#         return pre

#     pre, silent = await say(agent.stream_question(None)), 0
#     while not agent.done and state["present"]:
#         if pre is None: pre = await asyncio.to_thread(ear.wait_onset, 45)
#         pcm = await asyncio.to_thread(ear.collect, pre) if pre else None
#         pre = None
#         text, api_lang = await asyncio.to_thread(sarvam.stt, pcm) if pcm else ("", None)
#         if len(text) < 3:
#             silent += 1
#             if silent >= 3: print("No response; ending"); break
#             pre = await say(one(L.RETRY[agent.lang])); continue
#         silent = 0
#         agent.lang = L.update(agent.lang, text, api_lang)
#         transcript.append({"time": stamp(), "speaker": "Candidate", "lang": agent.lang, "text": text})
#         pre = await say(agent.stream_question(text))
#     pres.cancel()
#     await asyncio.gather(*agent.eval_tasks, return_exceptions=True)
#     await bot.leave()
#     await build(job, resume, agent.turns, transcript, out)
#     print(f"Report written to {out}/report.md")

# if __name__ == "__main__":
#     ap = argparse.ArgumentParser()
#     ap.add_argument("--meet-url", help="Optional. If omitted, the bot creates a Meet link itself.")
#     ap.add_argument("--candidate-email", help="The link is emailed here (needs data/token.json)")
#     ap.add_argument("--candidate-name", default="")
#     ap.add_argument("--start-at", help='e.g. "2026-10-14 15:00" (uses TZ_OFFSET) or "2026-10-14T15:00+05:30"')
#     ap.add_argument("--job", default="data/job.json"); ap.add_argument("--resume", default="data/resume.txt")
#     ap.add_argument("--out", default=None)
#     asyncio.run(run(ap.parse_args()))










# import argparse, asyncio, json, os, re, sys, time
# from datetime import datetime, timedelta, timezone
# from . import sarvam, config as C, lang as L, invite
# from .audio import Ear, Speaker
# from .agent import InterviewAgent
# from .meet import MeetBot
# from .report import build

# async def one(text):
#     yield text

# def parse_start(s):
#     dt = datetime.fromisoformat(s.strip().replace("Z", "+00:00").replace(" ", "T", 1))
#     if dt.tzinfo is None:
#         sign = -1 if C.TZ_OFFSET.startswith("-") else 1
#         h, m = C.TZ_OFFSET.lstrip("+-").split(":")
#         dt = dt.replace(tzinfo=timezone(sign * timedelta(hours=int(h), minutes=int(m))))
#     return dt

# def slug(s): return re.sub(r"[^a-z0-9]+", "-", (s or "").lower()).strip("-") or "candidate"

# async def run(a):
#     job = json.load(open(a.job)); resume = open(a.resume).read()
#     start = parse_start(a.start_at) if a.start_at else None
#     url = a.meet_url
#     if not url:
#         if not a.candidate_email: sys.exit("Give --candidate-email (bot creates + emails the link) or --meet-url")
#         url = await asyncio.to_thread(invite.create_meeting)
#         print("Meeting created:", url)
#     if a.candidate_email:
#         when = f"{start:%A, %d %b %Y at %I:%M %p} {C.TZ_LABEL}" if start else "Now, please join as soon as you can"
#         try:
#             await asyncio.to_thread(invite.send_invite, a.candidate_email, a.candidate_name, url, job, when)
#             print("Invitation emailed to", a.candidate_email)
#         except Exception as e:
#             print("INVITE EMAIL FAILED:", e, "\nSend this link to the candidate yourself:", url)
#     out = a.out or f"output/{slug(a.candidate_name)}-{time.strftime('%Y%m%d-%H%M')}"
#     os.makedirs(out, exist_ok=True)
#     json.dump({"candidate": a.candidate_name, "email": a.candidate_email, "meet_url": url,
#                "scheduled": start.isoformat() if start else None}, open(f"{out}/session.json", "w"), indent=2)
#     if start:
#         wait = (start - datetime.now(timezone.utc)).total_seconds() - 60
#         if wait > 0: print(f"Waiting {wait/60:.0f} min until the interview time..."); await asyncio.sleep(wait)

#     transcript, t0 = [], time.time()
#     stamp = lambda: time.strftime("%M:%S", time.gmtime(time.time() - t0))
#     ear, speaker = Ear(), Speaker()
#     bot = MeetBot(); await bot.join(url)
#     if not await bot.wait_for_candidate(C.WAIT_MINUTES * 60):
#         print("Candidate never joined"); await bot.leave(); return
#     t0 = time.time(); ear.flush()
#     agent = InterviewAgent(job, resume)
#     state = {"present": True}

#     async def watch_presence():           # off the hot path: never slows a turn
#         misses = 0
#         while True:
#             n = await bot.participant_count()
#             misses = misses + 1 if (n is not None and n < 2) else 0
#             state["present"] = misses < 2
#             await asyncio.sleep(5)
#     pres = asyncio.create_task(watch_presence())

#     async def say(stream):
#         try: spoken, pre = await speaker.say(stream, ear)
#         except Exception as e:
#             print("turn failed:", repr(e)); return None
#         if spoken: transcript.append({"time": stamp(), "speaker": "Interviewer", "text": spoken})
#         if pre is not None: agent.mark_interrupted(spoken)
#         return pre

#     pre, silent = await say(agent.stream_question(None)), 0
#     while not agent.done and state["present"]:
#         if pre is None: pre = await asyncio.to_thread(ear.wait_onset, 45)
#         pcm = await asyncio.to_thread(ear.collect, pre) if pre else None
#         pre = None
#         text, api_lang = await asyncio.to_thread(sarvam.stt, pcm) if pcm else ("", None)
#         if len(text) < 3:
#             silent += 1
#             if silent >= 3: print("No response; ending"); break
#             pre = await say(one(L.RETRY[agent.lang])); continue
#         silent = 0
#         agent.lang = L.update(agent.lang, text, api_lang)
#         transcript.append({"time": stamp(), "speaker": "Candidate", "lang": agent.lang, "text": text})
#         pre = await say(agent.stream_question(text))
#     pres.cancel()
#     await asyncio.gather(*agent.eval_tasks, return_exceptions=True)
#     await bot.leave()
#     json.dump(agent.plan, open(f"{out}/plan.json", "w"), indent=2, ensure_ascii=False)   # the easy->hard ladder used
#     await build(job, resume, agent.turns, transcript, out)
#     print(f"Report written to {out}/report.md")

# if __name__ == "__main__":
#     ap = argparse.ArgumentParser()
#     ap.add_argument("--meet-url", help="Optional. If omitted, the bot creates a Meet link itself.")
#     ap.add_argument("--candidate-email", help="The link is emailed here (needs data/token.json)")
#     ap.add_argument("--candidate-name", default="")
#     ap.add_argument("--start-at", help='e.g. "2026-10-14 15:00" (uses TZ_OFFSET) or "2026-10-14T15:00+05:30"')
#     ap.add_argument("--job", default="data/job.json"); ap.add_argument("--resume", default="data/resume.txt")
#     ap.add_argument("--out", default=None)
#     asyncio.run(run(ap.parse_args()))










import argparse, asyncio, json, os, re, sys, time
from datetime import datetime, timedelta, timezone
from . import sarvam, config as C, lang as L, invite
from .audio import Ear, Speaker
from .agent import InterviewAgent
from .meet import MeetBot
from .pipeline import reply_stream
from .report import build

async def one(text):
    yield text

def parse_start(s):
    dt = datetime.fromisoformat(s.strip().replace("Z", "+00:00").replace(" ", "T", 1))
    if dt.tzinfo is None:
        sign = -1 if C.TZ_OFFSET.startswith("-") else 1
        h, m = C.TZ_OFFSET.lstrip("+-").split(":")
        dt = dt.replace(tzinfo=timezone(sign * timedelta(hours=int(h), minutes=int(m))))
    return dt

def slug(s): return re.sub(r"[^a-z0-9]+", "-", (s or "").lower()).strip("-") or "candidate"

async def run(a):
    job = json.load(open(a.job)); resume = open(a.resume).read()
    start = parse_start(a.start_at) if a.start_at else None
    url = a.meet_url
    if not url:
        if not a.candidate_email: sys.exit("Give --candidate-email (bot creates + emails the link) or --meet-url")
        url = await asyncio.to_thread(invite.create_meeting)
        print("Meeting created:", url)
    if a.candidate_email:
        when = f"{start:%A, %d %b %Y at %I:%M %p} {C.TZ_LABEL}" if start else "Now, please join as soon as you can"
        try:
            await asyncio.to_thread(invite.send_invite, a.candidate_email, a.candidate_name, url, job, when)
            print("Invitation emailed to", a.candidate_email)
        except Exception as e:
            print("INVITE EMAIL FAILED:", e, "\nSend this link to the candidate yourself:", url)
    out = a.out or f"output/{slug(a.candidate_name)}-{time.strftime('%Y%m%d-%H%M')}"
    os.makedirs(out, exist_ok=True)
    json.dump({"candidate": a.candidate_name, "email": a.candidate_email, "meet_url": url,
               "scheduled": start.isoformat() if start else None}, open(f"{out}/session.json", "w"), indent=2)
    if start:
        wait = (start - datetime.now(timezone.utc)).total_seconds() - 60
        if wait > 0: print(f"Waiting {wait/60:.0f} min until the interview time..."); await asyncio.sleep(wait)

    transcript, t0 = [], time.time()
    stamp = lambda: time.strftime("%M:%S", time.gmtime(time.time() - t0))
    ear, speaker = Ear(), Speaker()
    # while we join: open the Sarvam connection and pre-synthesize instant phrases (fillers, retry, closing)
    asyncio.create_task(asyncio.to_thread(lambda: (sarvam.warm(), sarvam.prime(L.PRIME))))
    bot = MeetBot(); await bot.join(url)
    if not await bot.wait_for_candidate(C.WAIT_MINUTES * 60):
        print("Candidate never joined"); await bot.leave(); return
    print("Candidate is in the call. Starting the interview.")
    t0 = time.time(); ear.flush()
    agent = InterviewAgent(job, resume)
    state = {"present": True}

    async def watch_presence():           # off the hot path: never slows a turn
        misses = 0
        while True:
            n = await bot.participant_count()
            misses = misses + 1 if (n is not None and n < 2) else 0
            state["present"] = misses < 2
            await asyncio.sleep(5)
    pres = asyncio.create_task(watch_presence())

    async def say(stream, can_barge=None):
        try: spoken, pre = await speaker.say(stream, ear, can_barge)
        except Exception as e:
            print("turn failed:", repr(e)); return None
        if spoken: transcript.append({"time": stamp(), "speaker": "Interviewer", "text": spoken})
        if pre is not None: agent.mark_interrupted(spoken)
        return pre

    def log_candidate(text, lang_mode):
        transcript.append({"time": stamp(), "speaker": "Candidate", "lang": lang_mode, "text": text})

    pre, silent = await say(agent.stream_question(None)), 0
    while not agent.done and state["present"]:
        if pre is None: pre = await asyncio.to_thread(ear.wait_onset, 45)
        pcm, fut = await asyncio.to_thread(ear.collect, pre) if pre else (None, None)
        t_end, pre = time.monotonic(), None
        committed = asyncio.Event()
        if pcm is None:                                   # silence / noise only
            silent += 1
            if silent >= 3: print("No response; ending"); break
            committed.set(); pre = await say(one(L.RETRY[agent.lang]), committed); continue
        res = {}
        pre = await say(reply_stream(agent, pcm, fut, res, committed, log_candidate), committed)
        if res.get("retry"):
            silent += 1
            if silent >= 3: print("No response; ending"); break
        else: silent = 0
        st = speaker.play_starts
        if st: print(f"[latency] you spoke {len(pcm)/32000:.1f}s | first sound {st[0]-t_end:.2f}s after you stopped"
                     + (f" | answer starts {st[1]-t_end:.2f}s" if len(st) > 1 else "")
                     + f" | transcript ready {res.get('stt_wait_s', 0):.2f}s | LLM first sentence {res.get('llm_first_s', 0):.2f}s")
    pres.cancel()
    await asyncio.gather(*agent.eval_tasks, return_exceptions=True)
    await bot.leave()
    json.dump(agent.plan, open(f"{out}/plan.json", "w"), indent=2, ensure_ascii=False)
    await build(job, resume, agent.turns, transcript, out)
    print(f"Report written to {out}/report.md")

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--meet-url", help="Optional. If omitted, the bot creates a Meet link itself.")
    ap.add_argument("--candidate-email", help="The link is emailed here (needs data/token.json)")
    ap.add_argument("--candidate-name", default="")
    ap.add_argument("--start-at", help='e.g. "2026-10-14 15:00" (uses TZ_OFFSET) or "2026-10-14T15:00+05:30"')
    ap.add_argument("--job", default="data/job.json"); ap.add_argument("--resume", default="data/resume.txt")
    ap.add_argument("--out", default=None)
    asyncio.run(run(ap.parse_args()))