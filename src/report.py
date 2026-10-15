"""Report builder. It never blocks the interview: the AI summary is optional; scores, evidence and the transcript
are computed in code, so a report can ALWAYS be written (even if Groq is down or the interview was cut short)."""
import asyncio, json, os
from . import config as C

STATUS = {"completed": "Completed", "candidate_left": "Candidate left early", "no_response": "Ended: no response from candidate",
          "candidate_never_joined": "Candidate never joined", "stopped_by_operator": "Stopped by the operator",
          "error": "Stopped by an error", "recovered": "Rebuilt from saved data"}

def _num(x):
    try: return float(x)
    except (TypeError, ValueError): return None

def scores(job, turns):
    per = {}
    for t in turns:
        ev = t.get("eval")
        sc = _num(ev.get("score")) if isinstance(ev, dict) else None
        if sc is None: continue
        per.setdefault(ev.get("requirement_id") or t.get("req"), []).append(
            (sc, str(ev.get("evidence", "")), t.get("q", ""), ev.get("evidence_verified"), t.get("difficulty")))
    rows, num, den = [], 0, 0
    for r in job["requirements"]:
        items = per.get(r["id"], [])
        avg = sum(i[0] for i in items) / len(items) if items else None
        if avg is not None: num += avg * r["weight"]; den += r["weight"]
        rows.append({"id": r["id"], "requirement": r["text"], "weight": r["weight"],
                     "score": None if avg is None else round(avg, 2),
                     "evidence": [{"question": q, "quote": e, "verified": v, "score": s, "difficulty": d} for s, e, q, v, d in items]})
    return rows, (round(num / den / 5 * 100, 1) if den else None)

def _fallback(turns, note):
    evs = [t["eval"] for t in turns if isinstance(t.get("eval"), dict)]
    uniq = lambda xs: list(dict.fromkeys(str(x) for x in xs if x))[:6]
    return {"summary": f"No AI summary was generated ({note}). The scores, evidence quotes and transcript below are complete for the answers given.",
            "strengths": uniq(s for e in evs for s in (e.get("strengths") or [])),
            "concerns": uniq(s for e in evs for s in (e.get("gaps") or []) + (e.get("red_flags") or [])),
            "resume_consistency": "", "recommendation": "needs_human_review",
            "rationale": "No AI recommendation was produced.", "topics_for_human_round": []}

async def _llm_narrative(job, rows, overall, turns):
    from .agent import client
    prompt = ("Write an objective hiring-team summary from this interview data. Only use facts present. "
              'Return JSON: {"summary":"", "strengths":[], "concerns":[], "resume_consistency":"", '
              '"recommendation":"advance|hold|reject", "rationale":"", "topics_for_human_round":[]}\n'
              + json.dumps({"role": job["title"], "overall_score_pct": overall, "requirements": rows,
                            "evals": [t.get("eval") for t in turns]}, ensure_ascii=False, default=str))
    r = await asyncio.wait_for(client.chat.completions.create(
        model=C.GROQ_MODEL, temperature=0.2, response_format={"type": "json_object"}, extra_body={"reasoning_effort": "low"},
        messages=[{"role": "user", "content": prompt}]), 45)
    return json.loads(r.choices[0].message.content)

async def build(job, resume, turns, transcript, out_dir, meta=None, use_llm=True):
    meta = meta or {}
    rows, overall = scores(job, turns)
    have_scores = any(r["score"] is not None for r in rows)
    narrative, note = {}, ""
    if not have_scores: note = "no scored answers"
    elif not use_llm: note = "skipped because the interview was stopped early"
    else:
        try: narrative = await _llm_narrative(job, rows, overall, turns)
        except Exception as e: note = f"summary call failed: {type(e).__name__}"
    narrative = {**_fallback(turns, note or "incomplete response"), **{k: v for k, v in narrative.items() if v not in (None, "", [])}}
    status = meta.get("status", "completed")
    last = turns[-1] if turns else {}
    unanswered = last.get("q") if (last and not last.get("a") and not last.get("intro")) else None
    report = {"role": job["title"], "company": job["company"], "meta": meta, "overall_score_pct": overall,
              "requirements": rows, **narrative, "uncovered": [x["id"] for x in rows if x["score"] is None],
              "unanswered_last_question": unanswered,
              "note": "AI-generated, advisory only. A human must make the hiring decision.", "transcript": transcript}
    with open(f"{out_dir}/report.json", "w", encoding="utf-8") as f: json.dump(report, f, indent=2, ensure_ascii=False, default=str)
    who = " ".join(x for x in [meta.get("candidate"), f"({meta['email']})" if meta.get("email") else ""] if x) or "unknown"
    md = [f"# Interview report: {job['title']}",
          f"**Candidate:** {who} | **Status:** {STATUS.get(status, status)} | **Duration:** {meta.get('duration', 'n/a')}",
          f"**Overall:** {overall if overall is not None else 'n/a'}%  |  **Recommendation:** {report.get('recommendation')}"]
    if status != "completed":
        md.append(f"\nNOTE: this interview did not finish normally ({STATUS.get(status, status)}"
                  + (f": {meta['reason']}" if meta.get("reason") else "") + "). Scores cover only the answers given; "
                  f"requirements without a score: {', '.join(report['uncovered']) or 'none'}.")
    if unanswered: md.append(f"\nLast question was not answered: {unanswered}")
    md += [f"\n{report.get('summary', '')}\n", "## Scores & evidence"]
    for x in rows:
        md.append(f"### {x['id']} {x['requirement']} (weight {x['weight']}): {x['score'] if x['score'] is not None else 'not covered'}/5")
        md += [f"- Q ({e['difficulty'] or '?'}, {e['score']:g}/5): {e['question']}\n  > \"{e['quote']}\" {'' if e['verified'] else '(unverified quote)'}" for e in x["evidence"]]
    md += ["\n## Strengths"] + [f"- {s}" for s in report.get("strengths", [])]
    md += ["\n## Concerns"] + [f"- {s}" for s in report.get("concerns", [])]
    md += ["\n## Transcript"] + [f"[{t.get('time')}] **{t.get('speaker')}:** {t.get('text')}" for t in transcript]
    with open(f"{out_dir}/report.md", "w", encoding="utf-8") as f: f.write("\n".join(md))
    return report