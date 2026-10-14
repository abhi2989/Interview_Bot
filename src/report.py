"""Structured evaluation report: scores computed in code, narrative from Groq, evidence from per-answer evals."""
import json
from . import config as C
from .agent import client
def scores(job, turns):
    per = {}
    for t in turns:
        ev = t.get("eval")
        if ev: per.setdefault(ev["requirement_id"], []).append((ev["score"], ev["evidence"], t["q"], ev.get("evidence_verified")))
    rows, num, den = [], 0, 0
    for r in job["requirements"]:
        items = per.get(r["id"], [])
        avg = sum(s for s, *_ in items) / len(items) if items else None
        if avg is not None: num += avg * r["weight"]; den += r["weight"]
        rows.append({"id": r["id"], "requirement": r["text"], "weight": r["weight"],
                     "score": None if avg is None else round(avg, 2),
                     "evidence": [{"question": q, "quote": e, "verified": v} for _, e, q, v in items]})
    return rows, (round(num / den / 5 * 100, 1) if den else None)

async def build(job, resume, turns, transcript, out_dir):
    rows, overall = scores(job, turns)
    prompt = ("Write an objective hiring-team summary from this interview data. Only use facts present. "
              'Return JSON: {"summary":"", "strengths":[], "concerns":[], "resume_consistency":"", '
              '"recommendation":"advance|hold|reject", "rationale":"", "topics_for_human_round":[]}\n'
              + json.dumps({"role": job["title"], "overall_score_pct": overall, "requirements": rows,
                            "evals": [t.get("eval") for t in turns]}))
    r = await client.chat.completions.create(model=C.GROQ_MODEL, temperature=0.2,
        response_format={"type": "json_object"}, messages=[{"role": "user", "content": prompt}])
    narrative = json.loads(r.choices[0].message.content)
    report = {"role": job["title"], "company": job["company"], "overall_score_pct": overall,
              "requirements": rows, **narrative, "uncovered": [x["id"] for x in rows if x["score"] is None],
              "note": "AI-generated, advisory only. A human must make the hiring decision.",
              "transcript": transcript}
    json.dump(report, open(f"{out_dir}/report.json", "w"), indent=2, ensure_ascii=False)
    md = [f"# Interview report: {job['title']}", f"**Overall:** {overall}%  |  **Recommendation:** {report.get('recommendation')}",
          f"\n{report.get('summary','')}\n", "## Scores & evidence"]
    for x in rows:
        md.append(f"### {x['id']} {x['requirement']} (weight {x['weight']}): {x['score']}/5")
        md += [f"- Q: {e['question']}\n  > \"{e['quote']}\" {'' if e['verified'] else '(unverified quote)'}" for e in x["evidence"]]
    md += ["\n## Strengths"] + [f"- {s}" for s in report.get("strengths", [])]
    md += ["\n## Concerns"] + [f"- {s}" for s in report.get("concerns", [])]
    md += ["\n## Transcript"] + [f"[{t['time']}] **{t['speaker']}:** {t['text']}" for t in transcript]
    open(f"{out_dir}/report.md", "w").write("\n".join(md))
    return report
