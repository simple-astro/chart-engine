"""Teach (STUDIO_PLAN.md): lessons and gold answers the astrologers publish in the Studio.

- check(): the fixed rules every lesson and gold answer must pass, on save and on publish.
- context(): the published lessons for a question's topic (plus General) and the 1–2 closest gold answers,
  added to the question the way the KP verdicts are (the system prompt and its cache stay the same).
The content itself lives in the database, never in this repo.
"""
from __future__ import annotations

import re

from app import storage
from app.usage import TOPICS, _TOPICS

TOPIC_NAMES = ["General"] + [name for name, _ in TOPICS]
MAX_LESSONS = 8         # lessons added to one question
MAX_GOLD = 2            # example answers added to one question
GOLD_CHARS = 1200       # each example is cut to this many characters
LESSON_CHARS = 600
GOLD_MAX_CHARS = 4000

# ----- the fixed rules (STUDIO_PLAN.md §3) -----
_NEG = re.compile(r"\b(never|not|no|don't|do not|avoid|without|unless|instead of|rather than)\b|n't\b", re.I)
_FEAR = re.compile(r"\b(danger\w*|doom\w*|curse[ds]?|bad luck|terribl\w*|disaster\w*|fatal|ruin\w*|destroy\w*|"
                   r"misery|miserable|beware|scary|frighten\w*|catastroph\w*|evil|black magic)\b", re.I)
_DEATH = re.compile(r"\b(death|die|dies|dying|longevity|life ?span|lifespan|maraka|widow\w*|divorce\w*|"
                    r"separation|break ?up|breakup)\b", re.I)
_JAPA = re.compile(r"\b(japa|jaap|jap|chant\w*|mala)\b|\b\d{2,6}\s*times\b", re.I)
_ASKED = re.compile(r"\bif (they|the user|the person|someone|he|she) (ask|asks|asked|request)", re.I)
_GEM = re.compile(r"\b(gem\w*|gemstone\w*|ruby|emerald|pearl|sapphire|diamond|coral|hessonite|cat'?s eye|neelam|"
                  r"pukhraj|manik\w*|panna|moti|moonga|gomed|heera|lehsunia)\b", re.I)


def _plain(text: str, rx: re.Pattern) -> list[str]:
    """Matches of rx not negated earlier in their own sentence ("Never predict divorce" is fine)."""
    found = []
    for sent in re.split(r"(?<=[.!?])\s+|\n+", text):
        for m in rx.finditer(sent):
            if not _NEG.search(sent[:m.start()]):
                found.append(m.group(0).lower())
    return found


def check(text: str) -> list[str]:
    """Plain-language problems with a lesson or gold answer; empty when it may be saved or published."""
    problems = []
    if fear := _plain(text, _FEAR):
        problems.append(f"No fear wording ({', '.join(sorted(set(fear)))}). Say it gently, as a period to take care in.")
    if death := _plain(text, _DEATH):
        problems.append(f"No death, longevity or separation predictions ({', '.join(sorted(set(death)))}).")
    if (japa := _plain(text, _JAPA)) and not _ASKED.search(text):
        problems.append(f"No mantra japa or counts ({', '.join(sorted(set(japa)))}); lead with habits, seva and "
                        "daan. A mantra only if the person asks for one.")
    if _plain(text, _GEM) and not (re.search(r"substitut", text, re.I) and re.search(r"consult", text, re.I)):
        problems.append("A gemstone needs a substitute and \"consult an astrologer first\" in the same text.")
    return problems


# ----- using published teaching in answers -----
_STOP = set("""a an and are as at be been but by can could did do does for from had has have how i if in into is it
its me my of on or our should so than that the their them then there these they this to too was we were what when
where which who why will with would you your am any get got go going know tell about after before also more most
much very just now ji please""".split())


def topics_of(text: str) -> list[str]:
    return [name for name, rx in _TOPICS if rx.search(text or "")]


def _words(text: str) -> set[str]:
    return {w for w in re.findall(r"[a-z]+", (text or "").lower()) if len(w) > 2 and w not in _STOP}


def pick(items: list[dict], message: str) -> tuple[list[dict], list[dict]]:
    """The lessons and gold answers for this question: its topics' lessons first, then General ones; and the
    gold answers sharing most words with it, same topic first."""
    tops = topics_of(message)
    lessons = [i for i in items if i["kind"] == "lesson" and i["topic"] in tops]
    lessons += [i for i in items if i["kind"] == "lesson" and i["topic"] == "General"]
    q = _words(message)
    scored = []
    for i in items:
        if i["kind"] != "gold" or not (i["topic"] in tops or i["topic"] == "General"):
            continue
        score = len(q & _words(i.get("question") or i["text"][:300])) + (2 if i["topic"] in tops else 0)
        if score >= 2:
            scored.append((score, i["id"], i))
    gold = [i for _, _, i in sorted(scored, key=lambda t: (-t[0], -t[1]))[:MAX_GOLD]]
    return lessons[:MAX_LESSONS], gold


def _cut(text: str, n: int) -> str:
    text = text.strip()
    return text if len(text) <= n else text[:n].rsplit(" ", 1)[0] + " …"


def render(lessons: list[dict], gold: list[dict]) -> str:
    if not lessons and not gold:
        return ""
    out = ["\n\n[FROM YOUR ASTROLOGERS — lessons and example answers they approved. Follow the lessons and match the "
           "examples' method and voice. The chart data, the computed KP verdicts and the rules above always come "
           "first, and an example belongs to a different chart: never copy its planets, houses, dates or verdicts.]"]
    if lessons:
        out.append("Lessons:\n" + "\n".join(f"- ({i['topic']}) {_cut(i['text'], LESSON_CHARS)}" for i in lessons))
    for i in gold:
        asked = f' to "{_cut(i["question"], 200)}"' if i.get("question") else ""
        out.append(f"Example answer ({i['topic']}){asked}:\n{_cut(i['text'], GOLD_CHARS)}")
    return "\n".join(out)


def live_items(extra: list[int] | None = None) -> list[dict]:
    """The published lessons and gold answers, plus any drafts a Playground test turns on."""
    ids = storage.teach_version()["items"]
    return storage.teaching_items(sorted(set(ids) | set(extra or [])))


def context(message: str, extra: list[int] | None = None, off: bool = False, exclude: list[int] | None = None) -> str:
    """exclude: items left out (a Quality run never shows a test question its own gold answer)."""
    if off:
        return ""
    return render(*pick([i for i in live_items(extra) if i["id"] not in set(exclude or [])], message))
