import argparse, asyncio, json, os, re, signal, sys, time, traceback
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

def _write_json(path, obj):
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f: json.dump(obj, f, indent=2, ensure_ascii=False, default=str)
    os.replace(tmp, path)

def _check_files():
    """Fail early and clearly if src\\ mixes old and new files."""
    from . import audio, pipeline
    need = [(sarvam, "warm"), (sarvam, "prime"), (sarvam, "stt"), (L, "PRIME"), (L, "pick_filler"), (L, "REPEAT_RE"),
            (C, "EARLY_STT_MS"), (C, "PROFILE_DIR"), (C, "FILLER_MIN_SECONDS"), (audio, "Ear"), (audio, "Speaker"), (pipeline, "reply_stream")]
    missing = [f"{m.__name__.split('.')[-1]}.{n}" for m, n in need if not hasattr(m, n)]
    if missing:
        sys.exit("Some files in src\\ are from an OLD version (missing: " + ", ".join(missing) + ").\n"
                 "Delete src\\ and copy the full set of files again.")

async def run(a):
    _check_files()
    job = json.load(open(a.job, encoding="utf-8")); resume = open(a.resume, encoding="utf-8").read()
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
    _write_json(f"{out}/session.json", {"candidate": a.candidate_name, "email": a.candidate_email, "meet_url": url,
                                         "scheduled": start.isoformat() if start else None})
    if start:
        wait = (start - datetime.now(timezone.utc)).total_seconds() - 60
        if wait > 0: print(f"Waiting {wait/60:.0f} min until the interview time..."); await asyncio.sleep(wait)

    transcript, t0 = [], time.time()
    jl = open(f"{out}/transcript.jsonl", "a", encoding="utf-8")        # every line is saved the moment it happens
    elapsed = lambda: int(time.time() - t0)
    stamp = lambda: f"{elapsed() // 60:02d}:{elapsed() % 60:02d}"
    def add(entry):
        transcript.append(entry); jl.write(json.dumps(entry, ensure_ascii=False) + "\n"); jl.flush()

    agent = InterviewAgent(job, resume)
    bot = pres = admit = None
    status, reason, fast = "completed", "", False
    try:
        ear, speaker = Ear(), Speaker()
        # while we join: open the Sarvam connection and pre-synthesize instant phrases (fillers, retry, closing)
        asyncio.create_task(asyncio.to_thread(lambda: (sarvam.warm(), sarvam.prime(L.PRIME))))
        bot = MeetBot(); await bot.join(url)
        admit = asyncio.create_task(bot.auto_admit()) if C.AUTO_ADMIT else None   # start admitting as soon as we are in
        if not await bot.wait_for_candidate(C.WAIT_MINUTES * 60):
            status = "candidate_never_joined"; print("Candidate never joined")
        else:
            print("Candidate is in the call. Starting the interview.")
            t0 = agent.t0 = time.time(); ear.flush()
            state = {"present": True}

            async def watch_presence():           # off the hot path: never slows a turn
                misses = 0
                while True:
                    n = await bot.participant_count()
                    misses = misses + 1 if (n is not None and n < 2) else 0
                    state["present"] = misses < 2
                    await asyncio.sleep(5)
            pres = asyncio.create_task(watch_presence())

            def snapshot():                       # crash-safe copy of the interview so far (see src.make_report)
                try: _write_json(f"{out}/state.json", {"turns": agent.turns, "plan": agent.plan, "lang": agent.lang})
                except Exception: pass
            hooked = 0

            async def say(stream, can_barge=None):
                try: spoken, pre = await speaker.say(stream, ear, can_barge)
                except Exception as e:
                    print("turn failed:", repr(e)); return None
                if spoken: add({"time": stamp(), "speaker": "Interviewer", "text": spoken})
                if pre is not None: agent.mark_interrupted(spoken)
                return pre

            def log_candidate(text, lang_mode):
                add({"time": stamp(), "speaker": "Candidate", "lang": lang_mode, "text": text})

            pre, silent, end_reason = await say(agent.stream_question(None)), 0, None
            snapshot()
            while not agent.done and state["present"]:
                if pre is None: pre = await asyncio.to_thread(ear.wait_onset, 45)
                pcm, fut = await asyncio.to_thread(ear.collect, pre) if pre else (None, None)
                t_end, pre = time.monotonic(), None
                committed = asyncio.Event()
                if pcm is None:                                   # silence / noise only
                    silent += 1
                    if silent >= 3: end_reason = "no_response"; print("No response; ending"); break
                    committed.set(); pre = await say(one(L.RETRY[agent.lang]), committed); continue
                res = {}
                pre = await say(reply_stream(agent, pcm, fut, res, committed, log_candidate), committed)
                for t in agent.eval_tasks[hooked:]: t.add_done_callback(lambda _t: snapshot())   # save again when scoring lands
                hooked = len(agent.eval_tasks); snapshot()
                if res.get("retry"):
                    silent += 1
                    if silent >= 3: end_reason = "no_response"; print("No response; ending"); break
                else: silent = 0
                st = speaker.play_starts
                if st: print(f"[latency] you spoke {len(pcm)/32000:.1f}s | first sound {st[0]-t_end:.2f}s after you stopped"
                             + (f" | answer starts {st[1]-t_end:.2f}s" if len(st) > 1 else "")
                             + f" | transcript ready {res.get('stt_wait_s', 0):.2f}s | LLM first sentence {res.get('llm_first_s', 0):.2f}s")
            status = end_reason or ("completed" if agent.done else "candidate_left")
    except asyncio.CancelledError:
        status, fast = "stopped_by_operator", True
    except Exception as e:
        status, reason, fast = "error", repr(e), True
        traceback.print_exc()
    finally:
        for t in (pres, admit):
            if t: t.cancel()
        try:
            if agent.eval_tasks: await asyncio.wait(agent.eval_tasks, timeout=5 if fast else 30)
            if bot is not None:
                try: await asyncio.wait_for(bot.leave(), 15)
                except BaseException: pass
        except BaseException: pass
        jl.close()
        try:
            _write_json(f"{out}/plan.json", agent.plan)
            meta = {"candidate": a.candidate_name, "email": a.candidate_email, "meet_url": url, "status": status,
                    "reason": reason, "duration": f"{elapsed() // 60}:{elapsed() % 60:02d}"}
            await build(job, resume, agent.turns, transcript, out, meta=meta, use_llm=not fast)
            print(f"Report written to {out}/report.md (status: {status})")
        except BaseException as e:
            print(f"REPORT FAILED: {e!r}. Your data is saved in {out} (transcript.jsonl, state.json). "
                  f"Rebuild it with: python -m src.make_report {out} --no-llm")

async def _main(a):
    task, hits = asyncio.current_task(), {"n": 0}
    def on_signal():                          # Ctrl+C or `docker stop`: finish nicely and write the report
        hits["n"] += 1
        if hits["n"] == 1:
            print("\nStopping and saving the report from what was answered so far (press Ctrl+C again to quit immediately)...")
            task.cancel()
        else: os._exit(1)
    for sig in (signal.SIGINT, signal.SIGTERM):
        try: asyncio.get_running_loop().add_signal_handler(sig, on_signal)
        except (NotImplementedError, RuntimeError): pass
    await run(a)
    sys.stdout.flush(); os._exit(0)           # don't wait for leftover audio threads

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--meet-url", help="Optional. If omitted, the bot creates a Meet link itself.")
    ap.add_argument("--candidate-email", help="The link is emailed here (needs data/token.json)")
    ap.add_argument("--candidate-name", default="")
    ap.add_argument("--start-at", help='e.g. "2026-10-14 15:00" (uses TZ_OFFSET) or "2026-10-14T15:00+05:30"')
    ap.add_argument("--job", default="data/job.json"); ap.add_argument("--resume", default="data/resume.txt")
    ap.add_argument("--out", default=None)
    asyncio.run(_main(ap.parse_args()))