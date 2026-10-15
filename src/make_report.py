"""Rebuild a report from the data saved during an interview (after a crash or a hard stop):
docker run --rm --env-file .env -v "${PWD}/src:/app/src" -v "${PWD}/data:/app/data" -v "${PWD}/output:/app/output" --entrypoint python interview-bot -m src.make_report output/<folder> [--no-llm]"""
import asyncio, json, os, sys
from .report import build

async def main():
    folder = next((a for a in sys.argv[1:] if not a.startswith("--")), None)
    if not folder: sys.exit("Usage: python -m src.make_report output/<folder> [--no-llm]")
    load = lambda p: json.load(open(p, encoding="utf-8"))
    state = load(f"{folder}/state.json")
    transcript = [json.loads(l) for l in open(f"{folder}/transcript.jsonl", encoding="utf-8") if l.strip()] \
        if os.path.exists(f"{folder}/transcript.jsonl") else []
    session = load(f"{folder}/session.json") if os.path.exists(f"{folder}/session.json") else {}
    job, resume = load("data/job.json"), open("data/resume.txt", encoding="utf-8").read()
    meta = {"candidate": session.get("candidate"), "email": session.get("email"), "status": "recovered",
            "duration": transcript[-1]["time"] if transcript else "n/a"}
    await build(job, resume, state["turns"], transcript, folder, meta=meta, use_llm="--no-llm" not in sys.argv)
    print(f"Report written to {folder}/report.md")

asyncio.run(main())