"""Studio Quality (STUDIO_PLAN.md step 6): does Astropositivism get better or worse as the astrologers teach it?

- The test set: published gold answers marked "in test set" (question + saved chart + the ideal answer).
- A run answers each test question afresh, with the live setup (and, to compare, with drafts turned on), leaving
  the question's own gold answer out of the teaching. An AI judge then marks the answer against the gold one on the
  same five checks astrologers use in Review (the remedy checks for remedy questions).
- Score per answer, out of 10: the share of checks passed, where a fact-check catch counts as one more fail.
  Per topic and overall: the average.
- Publish gate: publishing a lesson or gold answer first compares its topic (all topics for General) live vs with
  it; a drop of more than DROP_MARGIN asks the publisher to confirm a second time.
Runs are paid AI calls, so they run in the background, one at a time, with the cost estimated before and
recorded after.
"""
from __future__ import annotations

import json
import re
import threading
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone

from app import config, storage
from app.review import check_set

JUDGE_MODEL = "claude-haiku-4-5"
MAX_QUESTIONS = 60
DROP_MARGIN = 0.5      # judges vary a little run to run: only a bigger drop counts
WORKERS = 3
STALE = timedelta(minutes=45)
_threads: dict[int, threading.Thread] = {}

JUDGE_SYSTEM = (
    "You grade an AI astrologer's answer against the ideal answer a senior Vedic astrologer (KP and Nadi methods) "
    "wrote for the same question and the same chart. Judge only from the two texts and the fact-check note: does "
    "the answer agree with the ideal one on the chart facts, the method, the timing and the advice, and does it "
    "keep the house rules (warm, no fear, practical habits before mantras, gems only with a substitute and a "
    "consultation)? Mark each check pass, fail, or na when it does not apply to this question. Reply with JSON "
    'only: {"checks": {"<key>": "pass|fail|na", ...}, "note": "<one short sentence: the main difference>"}')


def topics_for(draft: dict) -> list[str] | None:
    """The test topics a lesson or gold answer can change: its own, or every topic for General (None)."""
    return None if draft["topic"] == "General" else [draft["topic"]]


def test_items(topics: list[str] | None = None) -> list[dict]:
    return [i for i in storage.test_set() if topics is None or i["topic"] in topics]


def per_answer_cost(model: str) -> float:
    """What one test answer has cost lately (testers' answers on this model), plus the judge."""
    rows = [r for r in storage.token_totals(False) if r["model"] == model and r["n"]]
    answer = (config.cost(model, rows[0]["inp"], rows[0]["out"], rows[0]["cr"], rows[0]["cw"]) or 0) / rows[0]["n"] \
        if rows else 0.01
    return round(answer + (config.cost(JUDGE_MODEL, 3000, 200, 0, 0) or 0), 4)


def estimate(n_answers: int, model: str | None = None) -> dict:
    model = model or config.model()
    per = per_answer_cost(model)
    return {"answers": n_answers, "per_answer": per, "cost": round(per * n_answers, 2), "model": model,
            "label": config.label(model), "minutes": max(1, round(n_answers * 20 / WORKERS / 60))}


def score(checks: dict, caught: bool) -> float | None:
    passed = sum(v == "pass" for v in checks.values())
    failed = sum(v == "fail" for v in checks.values()) + (1 if caught else 0)
    return round(10 * passed / (passed + failed), 1) if passed + failed else None


def _parse(text: str) -> dict:
    m = re.search(r"\{.*\}", text or "", re.S)
    if not m:
        raise ValueError("the judge did not return JSON")
    return json.loads(m.group(0))


def judge(question: str, gold: str, answer: str, factcheck: dict | None) -> tuple[dict, float]:
    """({"checks": {...}, "note": ...}, cost) from the AI judge, on the checks for this kind of question."""
    from app import chat
    _, checks, _ = check_set(question)
    fc = (factcheck or {}).get("found") or []
    note = (f"The automatic fact check caught {len(fc)} error(s) in the draft: {' | '.join(fc)}" if fc
            else "The automatic fact check found nothing wrong.")
    prompt = (f"QUESTION:\n{question}\n\nIDEAL ANSWER:\n{gold}\n\nANSWER TO GRADE:\n{answer}\n\nFACT CHECK: {note}\n\n"
              "CHECKS:\n" + "\n".join(f"- {k}: {name}" for k, name in checks))
    resp = chat._client().messages.create(model=JUDGE_MODEL, max_tokens=400, system=JUDGE_SYSTEM,
                                          messages=[{"role": "user", "content": prompt}])
    text = "".join(getattr(b, "text", "") for b in resp.content)
    u = resp.usage
    cost = config.cost(JUDGE_MODEL, u.input_tokens, u.output_tokens, getattr(u, "cache_read_input_tokens", 0) or 0,
                       getattr(u, "cache_creation_input_tokens", 0) or 0) or 0
    out = _parse(text)
    got = out.get("checks") if isinstance(out.get("checks"), dict) else {}
    return {"checks": {k: got.get(k) if got.get(k) in ("pass", "fail", "na") else "na" for k, _ in checks},
            "note": str(out.get("note") or "")[:300]}, cost


def _one(job: dict, model: str) -> dict:
    from app import chat
    gold = job["gold"]
    base = {"gold_id": gold["id"], "variant": job["variant"], "topic": gold["topic"], "question": gold["question"]}
    profile = storage.get(gold["profile_id"]) if gold.get("profile_id") else None
    if not profile:
        return {**base, "error": "The chart for this test question was deleted."}
    try:
        out = chat.answer_once(profile, gold["question"], model,
                               test={"exclude": [gold["id"]], "drafts": job["drafts"]})
        verdict, judge_cost = judge(gold["question"], gold["text"], out["text"], out["factcheck"])
    except Exception as exc:  # one failed question must not stop the run
        return {**base, "error": str(exc)[:300]}
    caught = bool((out["factcheck"] or {}).get("found"))
    return {**base, "answer": out["text"], "factcheck": out["factcheck"], "judge": verdict,
            "score": score(verdict["checks"], caught), "cost": (out.get("cost") or 0) + judge_cost}


def summarize(items: list[dict]) -> dict:
    """{"overall": {variant: avg}, "topics": {topic: {variant: avg, "n": questions}}}"""
    out: dict = {"overall": {}, "topics": {}}
    for v in sorted({i["variant"] for i in items}):
        got = [i["score"] for i in items if i["variant"] == v and i.get("score") is not None]
        out["overall"][v] = round(sum(got) / len(got), 1) if got else None
        for t in sorted({i["topic"] for i in items}):
            got = [i["score"] for i in items if i["variant"] == v and i["topic"] == t and i.get("score") is not None]
            row = out["topics"].setdefault(t, {"n": len({i["gold_id"] for i in items if i["topic"] == t})})
            row[v] = round(sum(got) / len(got), 1) if got else None
    return out


def drops(scores: dict | None) -> list[str]:
    """Topics where the drafts scored more than DROP_MARGIN below live."""
    out = []
    for t, row in ((scores or {}).get("topics") or {}).items():
        if row.get("live") is not None and row.get("draft") is not None and row["draft"] < row["live"] - DROP_MARGIN:
            out.append(t)
    return out


def _work(run_id: int, jobs: list[dict], model: str) -> None:
    try:
        with ThreadPoolExecutor(max_workers=WORKERS) as pool:
            for item in pool.map(lambda j: _one(j, model), jobs):
                storage.add_eval_item(run_id, item)
        storage.finish_run(run_id, summarize(storage.eval_items(run_id)))
    except Exception as exc:
        storage.finish_run(run_id, None, error=str(exc)[:300])


def busy() -> dict | None:
    """The run in progress, if any; a run left 'running' by a server restart is closed as failed."""
    r = storage.running_run()
    if r and datetime.now(timezone.utc) - datetime.fromisoformat(r["created_at"]) > STALE and r["id"] not in _threads:
        storage.finish_run(r["id"], summarize(storage.eval_items(r["id"])) or None,
                           error="Stopped before it finished (the server restarted). Run it again.")
        return None
    return r


def start(kind: str, gold: list[dict], drafts: list[int], actor: str, topics: list[str] | None = None) -> dict:
    """Start a run in the background: live only (drafts empty), or live and with the drafts."""
    model = config.model()
    variants = [("live", [])] + ([("draft", drafts)] if drafts else [])
    jobs = [{"gold": g, "variant": v, "drafts": d} for g in gold for v, d in variants]
    run = storage.add_run(kind, topics, drafts, storage.teach_version()["id"], model, JUDGE_MODEL, len(jobs), actor)
    t = threading.Thread(target=_work, args=(run["id"], jobs, model), daemon=True, name=f"quality-run-{run['id']}")
    _threads[run["id"]] = t
    t.start()
    return run


def wait(run_id: int, timeout: float | None = None) -> None:
    """For tests: block until a run's background work is done."""
    t = _threads.get(run_id)
    if t:
        t.join(timeout)


def latest_gate(draft_id: int) -> dict | None:
    """The newest finished gate run for this draft against the live teaching version now."""
    live = storage.teach_version()["id"]
    for r in storage.runs(100):
        if r["kind"] == "gate" and r["drafts"] == [draft_id] and r["teach_version"] == live and r["status"] == "done":
            return r
    return None
