"""Bhava-lord placements: what it means when the lord of one house sits in another (D1, whole-sign houses).

144 readings in plain words, drawn from the classical rules (Brihat Parashara Hora Shastra's chapter on the effects
of the house lords, and common practice) and written as tendencies, with no fear: no death, no longevity, no doom.
Each entry has "text" (the result in two or three sentences) and "life" (three everyday ways it shows). The
principle behind each one (what the two houses rule, the house-from-house count, kendra-trikona and Vipareeta
links) is built by principle() from HOUSE, so it reads the same way everywhere.

The reading for a real chart adds that chart's own facts on top (the lord's dignity, combustion, aspects and Dasha
periods); these texts are the general result only. Drafted 2026-10-23 for the owner's review.
"""
from __future__ import annotations

HOUSE = {
    1: "self, body, personality and life path",
    2: "wealth, family, speech and food",
    3: "effort, courage, siblings, skills and short travel",
    4: "home, mother, property, vehicles and peace of mind",
    5: "children, intelligence, creativity, learning and past merit",
    6: "work, service, health, debts and rivals",
    7: "marriage, partners, business and the public",
    8: "sudden change, hidden matters, research and inheritance",
    9: "fortune, father, teachers, dharma and long journeys",
    10: "career, status, authority and your actions",
    11: "gains, income, friends, elder siblings and wishes",
    12: "expenses, foreign lands, sleep, retreat and spiritual release",
}
KENDRA, TRIKONA, DUSTHANA = {1, 4, 7, 10}, {1, 5, 9}, {6, 8, 12}
VIPAREETA = {6: "Harsha", 8: "Sarala", 12: "Vimala"}


def ordinal(n: int) -> str:
    return f"{n}{'th' if 10 <= n % 100 <= 20 else {1: 'st', 2: 'nd', 3: 'rd'}.get(n % 10, 'th')}"


def principle(lord_of: int, sits_in: int) -> str:
    """The rule behind a placement, the same way for every chart: what each house rules, the house counted from the
    house, and the classic links (kendra-trikona, Vipareeta, a lord at home)."""
    a, b = lord_of, sits_in
    out = f"The {ordinal(a)} lord rules {HOUSE[a]}. "
    if a == b:
        out += "It sits in its own house, which protects and strengthens everything that house stands for."
    else:
        count = (b - a) % 12 + 1
        out += (f"It sits in the {ordinal(b)}, the house of {HOUSE[b]}, so the {ordinal(a)} house’s matters play out "
                f"through the {ordinal(b)}’s. Counted from the {ordinal(a)}, the {ordinal(b)} is the {ordinal(count)}.")
    if a in DUSTHANA and b in DUSTHANA:
        out += (f" A lord of a difficult house (6, 8, 12) placed in another difficult house forms the "
                f"{VIPAREETA[a]} Vipareeta Raja yoga: trouble works against trouble, and hard phases tend to end in gain.")
    elif a != b and ((a in KENDRA and b in TRIKONA) or (a in TRIKONA and b in KENDRA)):
        out += " A kendra (1, 4, 7, 10) lord and a trikona (1, 5, 9) house are linked here: a building block of Raja yoga."
    elif a in TRIKONA and b in DUSTHANA:
        out += " A lord of fortune in a difficult house works harder for its results; its strength decides how much."
    elif a in DUSTHANA and b in (KENDRA | TRIKONA) - {1}:
        out += (" A difficult-house lord in a good house brings effort into that area; it also tends to improve with "
                "time and work.")
    return out


def reading(lord_of: int, sits_in: int) -> dict:
    """{"lord_of", "sits_in", "text", "life", "principle"} for one placement."""
    r = PLACEMENTS[(lord_of, sits_in)]
    return {"lord_of": lord_of, "sits_in": sits_in, "text": r["text"], "life": list(r["life"]),
            "principle": principle(lord_of, sits_in)}


SIGN_LORDS = ["Mars", "Venus", "Mercury", "Moon", "Sun", "Mercury", "Venus", "Mars", "Jupiter", "Saturn", "Saturn",
              "Jupiter"]
SIGNS = ["Aries", "Taurus", "Gemini", "Cancer", "Leo", "Virgo", "Libra", "Scorpio", "Sagittarius", "Capricorn",
         "Aquarius", "Pisces"]
MALEFICS = {"Saturn", "Mars", "Rahu", "Ketu"}
DIGNITY_WORDS = {"exalted": "Exalted", "own": "Own sign", "friendly": "Friend’s sign", "neutral": "Neutral sign",
                 "enemy": "Enemy’s sign", "debilitated": "Debilitated"}
DIGNITY_SCORE = {"exalted": 2, "own": 2, "friendly": 1, "neutral": 0, "enemy": -1, "debilitated": -2}


def _month(iso: str) -> str:
    from datetime import datetime
    return datetime.fromisoformat(iso).strftime("%b %Y")


def _when(chart: dict, lord: str, now) -> str:
    """When this lord's results come alive: its running Mahadasha or antardasha, else the next antardasha of it,
    plus its own Mahadasha if that is still to come."""
    from datetime import datetime
    t = lambda iso: datetime.fromisoformat(iso)  # noqa: E731
    md_now = next((m for m in chart.get("dasha", []) if t(m["start"]) <= now < t(m["end"])), None)
    if md_now and md_now["lord"] == lord:
        return f"Running now: {lord} Mahadasha → {_month(md_now['end'])}"
    ads = [a for m in chart.get("dasha", []) for a in m.get("children", []) if a["lord"] == lord and t(a["end"]) > now]
    md_next = next((m for m in chart.get("dasha", []) if m["lord"] == lord and t(m["start"]) > now), None)
    out = []
    if ads:
        a = ads[0]
        out.append(f"Running now: {lord} antardasha → {_month(a['end'])}" if t(a["start"]) <= now
                   else f"{lord} antardasha {_month(a['start'])} – {_month(a['end'])}")
    if md_next:
        out.append(f"Mahadasha {md_next['start'][:4]}–{md_next['end'][:4]}")
    return " · ".join(out) or "Its Dasha periods have passed; transits over it still bring its themes up."


def for_chart(chart: dict, now=None) -> dict:
    """The 12 house lords of this chart (D1, whole-sign houses from the lagna): where each sits, the general reading,
    and what this chart adds (dignity, combustion, retrograde, company, aspects, Dasha timing), graded Strong, Mixed
    or Needs care, plus the few links that stand out."""
    from datetime import datetime, timezone
    from core.dignity import dignity
    now = now or datetime.now(timezone.utc)
    L, g = chart["lagna"]["sign_index"], chart["grahas"]
    asp = (chart.get("strength") or {}).get("aspects", {})
    nb = (chart.get("strength") or {}).get("neecha_bhanga", {})
    house_of = lambda p: (g[p]["sign_index"] - L) % 12 + 1  # noqa: E731
    cards = []
    for h in range(1, 13):
        sign = (L + h - 1) % 12
        lord = SIGN_LORDS[sign]
        p, at = g[lord], house_of(lord)
        dig = dignity(lord, p["sign_index"])
        cancelled = dig == "debilitated" and (nb.get(lord) or {}).get("cancelled")
        score = DIGNITY_SCORE[dig] + (2 if cancelled else 0)
        why = ["Debilitated, cancelled (Neecha Bhanga)" if cancelled else DIGNITY_WORDS[dig]]
        if at == h:
            why.append("In its own house")
        if h in DUSTHANA and at in DUSTHANA and at != h:
            score += 1
            why.append(f"{VIPAREETA[h]} Vipareeta Raja yoga")
        elif at in KENDRA | TRIKONA:
            score += 1
        elif at in DUSTHANA:
            score -= 1
        if p.get("combust"):
            score -= 1
            why.append("Combust")
        if p.get("retrograde"):
            why.append("Retrograde")
        aspected_by = sorted(q for q, a in asp.items() if lord in a.get("planets", []) and q != lord)
        together = sorted(q for q, x in g.items() if q != lord and x["sign_index"] == p["sign_index"])
        if "Jupiter" in aspected_by + together and lord != "Jupiter":
            score += 1
            why.append("Jupiter’s aspect helps" if "Jupiter" in aspected_by else "With Jupiter (helps)")
        bad = [q for q in aspected_by + together if q in MALEFICS]
        if bad:
            score -= min(1, 0.5 * len(bad))
            if [q for q in aspected_by if q in MALEFICS]:
                why.append("Aspected by " + " and ".join(q for q in aspected_by if q in MALEFICS))
        if together:
            why.append("With " + ", ".join(together))
        own = [r for r in range(1, 13) if SIGN_LORDS[(L + r - 1) % 12] == lord]
        guards = [r for r in own if r in asp.get(lord, {}).get("houses", []) and r != at]
        if guards:
            why.append(f"Aspects its own {ordinal(guards[0])} house (protects it)")
        tag = "Strong" if score >= 2 else "Needs care" if score <= -1.5 else "Mixed"
        cards.append({**reading(h, at), "house": h, "sign": SIGNS[sign], "lord": lord, "lord_sign": p["sign"],
                      "dignity": dig, "tag": tag, "why": why, "when": _when(chart, lord, now),
                      "rules": own})
    return {"lagna": SIGNS[L], "cards": cards, "highlights": _highlights(cards)}


def _highlights(cards: list[dict]) -> list[dict]:
    """The links that stand out, in plain words: crowded houses, the lagna lord, 9th-10th, exchanges, Vipareeta."""
    by = {c["house"]: c for c in cards}
    out = []
    groups: dict[int, list[dict]] = {}
    for c in cards:
        groups.setdefault(c["sits_in"], []).append(c)
    for at, cs in sorted(groups.items(), key=lambda kv: -len(kv[1])):
        if len(cs) >= 3:
            lords = list(dict.fromkeys(c["lord"] for c in cs))
            out.append({"t": f"The lords of {len(cs)} houses meet in your {ordinal(at)} house",
                        "b": f"{', '.join(lords)} bring the matters of your "
                             f"{', '.join(ordinal(c['house']) for c in cs)} houses into the {ordinal(at)} "
                             f"({HOUSE[at]}): much of your life runs through this house."})
    one = by[1]
    out.append({"t": f"Lagna lord {one['lord']} in your {ordinal(one['sits_in'])} house",
                "b": f"Your own path runs through {HOUSE[one['sits_in']]}. Graded {one['tag'].lower()} "
                     f"({', '.join(w[0].lower() + w[1:] for w in one['why'][:2])})."})
    l9, l10 = by[9], by[10]
    if l9["lord"] != l10["lord"] and (l9["lord_sign"] == l10["lord_sign"] or (l9["sits_in"] == 10 and l10["sits_in"] == 9)):
        out.append({"t": f"Dharma–Karmadhipati link: 9th lord {l9['lord']} and 10th lord {l10['lord']}",
                    "b": "One of the most respected Raja yogas: work that feels meaningful and a steady rise. Its "
                         "strength depends on the two planets’ grades below."})
    seen = set()
    for c in cards:
        o = by[c["sits_in"]]
        if o["sits_in"] == c["house"] and c["lord"] != o["lord"] and frozenset((c["lord"], o["lord"])) not in seen:
            seen.add(frozenset((c["lord"], o["lord"])))
            out.append({"t": f"Lord exchange: {c['lord']} and {o['lord']}",
                        "b": f"The lords of your {ordinal(c['house'])} and {ordinal(o['house'])} swap houses "
                             "(parivartana), so the two areas strongly support each other."})
    for c in cards:
        if c["house"] in DUSTHANA and c["sits_in"] in DUSTHANA and c["sits_in"] != c["house"]:
            out.append({"t": f"{VIPAREETA[c['house']]} Vipareeta Raja yoga: {ordinal(c['house'])} lord in the "
                             f"{ordinal(c['sits_in'])}",
                        "b": "Hard phases tend to end in gain, especially in the Dasha of "
                             f"{c['lord']}."})
    return out[:5]


def _p(text: str, *life: str) -> dict:
    return {"text": text, "life": life}


PLACEMENTS: dict[tuple[int, int], dict] = {
    # ----- 1st lord: you, your body and your path -----
    (1, 1): _p("A strong sense of self: you shape your own life and bounce back well from setbacks. Confidence, health "
               "and independence grow as you trust your own judgement, and people see you as someone who stands on "
               "their own feet.",
               "You like to decide for yourself and do well running your own work or business.",
               "Your body responds well to routine, exercise and a regular sleep time.",
               "Your personal reputation matters to you, and you build it carefully."),
    (1, 2): _p("Your path runs through money, family and speech. You build wealth by your own effort, stay close to "
               "family, and your words carry weight; what you say and how you earn become part of who you are.",
               "Earning, saving and providing for the family give you a sense of purpose.",
               "Speaking, teaching, sales, finance or food-related work suit you.",
               "Family ties stay close, and you may become the one others rely on."),
    (1, 3): _p("Self-made through courage and effort. You grow by taking initiative, communicating and staying "
               "active, and the more you try, the more doors open; waiting for luck suits you less than acting.",
               "Writing, media, sales, sport, technology or short travel suit you.",
               "Close bonds with siblings, friends or a team you lead.",
               "Hobbies and skills you practise can grow into real work."),
    (1, 4): _p("Happiness centres on home, mother and inner peace. A comfortable home, property and vehicles tend to "
               "come in time, and you feel most yourself when your home life is settled and calm.",
               "You value a settled home and are likely to own property.",
               "A close bond with your mother, who shapes your values.",
               "Education and a peaceful mind are your foundation for everything else."),
    (1, 5): _p("Your path runs through learning, creativity and children. You have good judgement and a teacher’s "
               "mind, and luck comes through ideas, study and advising others; past merit shows in how things work out.",
               "You learn by understanding rather than memorising, and others come to you for advice.",
               "Children, students or creative projects become central to your life.",
               "Decisions made from careful judgement, including investments, tend to work out."),
    (1, 6): _p("You grow by working hard, serving others and overcoming competition. You are strong at solving "
               "problems and do not give up easily; your health does best with a steady routine and sensible limits.",
               "Service, health care, law, defence or competitive fields suit you.",
               "You beat rivals by persistence rather than by force.",
               "Keep debts small, and keep a regular routine for food, exercise and rest."),
    (1, 7): _p("Your life centres on partners and the public. Marriage and partnerships shape who you become, and you "
               "may live or work away from your birthplace; you grow through relationships rather than alone.",
               "You do well in business, client work, sales or public-facing roles.",
               "Your spouse has a strong influence on your choices and direction.",
               "Travel and dealing with many kinds of people come naturally."),
    (1, 8): _p("A deep, searching nature, drawn to research, hidden subjects and transformation. Life brings changes "
               "that test you, and each one tends to leave you stronger, wiser and more self-aware.",
               "Research, investigation, insurance, healing, psychology or occult study suit you.",
               "Sudden changes often turn into new beginnings.",
               "Regular check-ups, rest and a calm routine keep your health steady."),
    (1, 9): _p("Fortunate and principled: luck, faith and good teachers guide your life. You are drawn to higher "
               "learning and long journeys, and you do best when you follow your values rather than shortcuts.",
               "Teaching, law, religion, philosophy or travel suit you.",
               "A supportive father figure or mentor helps you at key moments.",
               "Pilgrimage, study abroad or long journeys bring growth."),
    (1, 10): _p("Career and reputation are central to your life. Ambitious and capable, you rise through your own work "
                "and become known for it; you feel most yourself when you are doing something that matters.",
                "Leadership, management, government or public roles suit you.",
                "Recognition from employers or people in authority.",
                "Balance work with rest so that ambition does not cost you your health."),
    (1, 11): _p("Gains come through your own effort, friends and networks. Wishes tend to be fulfilled, income grows "
                "steadily, and people like having you around; your circle is one of your greatest assets.",
                "A wide circle of friends and useful contacts.",
                "Good for business, sales and income-earning work.",
                "Elder siblings or seniors support you."),
    (1, 12): _p("Your path leads beyond home: foreign lands, spiritual life or work behind the scenes. You are "
                "generous and inward-looking, and you recharge in quiet; keep an eye on spending and rest.",
                "Living or working abroad is likely or favourable.",
                "A pull towards meditation, retreat, charity or healing work.",
                "Plan your spending and keep your sleep regular."),

    # ----- 2nd lord: wealth, family and speech -----
    (2, 1): _p("Wealth comes through your own personality and effort. You are well-spoken and devoted to family, and "
               "you earn by being yourself; your face and voice can be part of how you make a living.",
               "Self-employment, or work that uses your voice or presence.",
               "Your family supports you, and you support them.",
               "You enjoy good food and comfort; keep both in balance."),
    (2, 2): _p("A 2nd lord at home protects money and family. Savings build steadily, speech is good, and family life "
               "stays close; what you build tends to last.",
               "You build wealth step by step and keep it.",
               "Finance, banking, speech or food-related work suits you.",
               "Family values and traditions matter deeply to you."),
    (2, 3): _p("Earnings come through effort, skills and communication. Writing, media, sales or short travel bring "
               "money, and the more you use your skills, the more you earn.",
               "Income through crafts, skills, writing or communication.",
               "Business with siblings or neighbours is possible.",
               "Spend wisely on hobbies, gadgets and travel."),
    (2, 4): _p("Wealth supports home and comfort: property, vehicles and family land. The mother or her family may "
               "help with resources, and money spent on the home is usually money well kept.",
               "Money goes into property and a comfortable home.",
               "Family assets, possibly from the mother’s side.",
               "Education adds to your earning power."),
    (2, 5): _p("Wealth through intelligence, education and investments. Children bring joy and may add to the "
               "family’s fortune, and your knowledge itself becomes a source of income.",
               "Teaching, advising or creative work earns well.",
               "Careful, long-term investing suits you better than quick bets.",
               "Family values pass on naturally to your children."),
    (2, 6): _p("Money comes through service, work and solving problems, and some goes out on debts or health. Steady "
               "work builds wealth, and avoiding loans keeps it.",
               "Earning through jobs, health care, law or service.",
               "Avoid lending to or borrowing from family carelessly.",
               "Watch your diet, and handle family disagreements calmly."),
    (2, 7): _p("Wealth through your spouse, partners and business. Marriage tends to improve your finances, and "
               "partnerships bring in money you could not earn alone.",
               "Business partnerships and trade suit you.",
               "Your spouse may add to the family’s wealth.",
               "Kind words keep relationships, and finances, strong."),
    (2, 8): _p("Money comes through sudden events, inheritance, insurance or a partner’s resources. Finances have ups "
               "and downs, so savings and planning matter more for you than for most.",
               "Inheritance, insurance or research-related income.",
               "Keep an emergency fund for surprises.",
               "Choose your words carefully within the family."),
    (2, 9): _p("Fortunate for wealth: money comes through luck, the father, teachers or righteous work. The family "
               "keeps its traditions, and wealth grows when it is used well.",
               "Teaching, law, banking or religion suit you.",
               "Support from your father or elders.",
               "Wealth grows when you share some of it for good causes."),
    (2, 10): _p("Earnings through career and status. Your profession brings steady income, often in finance, speech or "
                "a family business, and your reputation and income rise together.",
                "Banking, finance, teaching or speaking roles.",
                "A family business or a respected position.",
                "Your word in business is your bond."),
    (2, 11): _p("A classic wealth link: income and savings support each other. Gains come through friends, networks and "
                "more than one source, and money tends to grow once it starts.",
                "Multiple sources of income.",
                "Friends and elder siblings help financially.",
                "Good for building long-term wealth."),
    (2, 12): _p("Money tends to flow out to travel, family duties, charity or foreign lands. Savings grow through "
                "planning, and earning from abroad is possible; counted from the 2nd, the 12th is a house of gain.",
                "Money goes on travel, family duties, health or a home away from your birthplace.",
                "Savings grow with a fixed plan rather than good intentions.",
                "You may speak little, or speak best in quiet, one-to-one settings."),

    # ----- 3rd lord: effort, courage and siblings -----
    (3, 1): _p("Courageous, energetic and self-made. You speak your mind and act on your own initiative, and people "
               "notice your drive; you make things happen rather than wait for them.",
               "Sport, media, sales or any field that needs nerve.",
               "A natural communicator, performer or organiser.",
               "Learn patience: not every fight needs fighting."),
    (3, 2): _p("Earnings through communication, skills and effort. Your words, writing and hands bring money, and "
               "what you learn by practice becomes income.",
               "Writing, media, marketing, crafts or teaching.",
               "Siblings may share in the family’s resources.",
               "Choose your words with care in family matters."),
    (3, 3): _p("A 3rd lord at home: courage, skills and supportive siblings. Your effort brings results, and you keep "
               "growing through practice, communication and short journeys.",
               "Hobbies can turn into work.",
               "Good bonds with siblings and neighbours.",
               "Short travel and communication bring opportunities."),
    (3, 4): _p("Effort goes into home, property and the mother. Comforts come through your own hard work, and you may "
               "build or improve a home with your own hands.",
               "Home-based work, property or vehicles.",
               "Siblings may live close to home.",
               "Writing or study from home suits you."),
    (3, 5): _p("Creative courage: a talent for writing, the arts and communication. Children may be bold and "
               "talented, and your ideas come alive when you put them into words or performance.",
               "Writing, performance, design or media.",
               "Competitive exams go well with steady effort.",
               "Hobbies bring joy and sometimes income."),
    (3, 6): _p("Effort that defeats rivals: good for competition, sport and service. You work hard and win, and a "
               "difficult house of effort in another house of effort gives stamina.",
               "Competitive jobs, defence, law or health care.",
               "Handle disagreements with siblings calmly.",
               "Physical activity keeps your health strong."),
    (3, 7): _p("Courage and communication in partnerships, with travel for business. Your partner may be active and "
               "outspoken, and deals come through talking, writing and moving around.",
               "Sales, trade or media partnerships.",
               "Frequent travel for work.",
               "Siblings may connect you with partners or clients."),
    (3, 8): _p("Effort goes into research and hidden matters, and courage is tested by sudden change. Persistence pays "
               "off, and you are good at getting to the bottom of things.",
               "Research, investigation, occult study or insurance work.",
               "Choose safe adventures over risky ones.",
               "Siblings’ matters ask for patience and care."),
    (3, 9): _p("Effort brings fortune: courage in following your beliefs, and long journeys. Speaking, writing or "
               "teaching about values and dharma suits you, and your initiative is blessed.",
               "Writing or teaching on philosophy, law or religion.",
               "Travel abroad for study or work.",
               "Siblings may be fortunate or live far away."),
    (3, 10): _p("Career through communication, skills and initiative. Your hard work is seen and rewarded, and you "
                "build your position through effort rather than inheritance.",
                "Media, sales, marketing, writing or technology careers.",
                "A self-made rise in your career.",
                "Siblings may support your work."),
    (3, 11): _p("Gains through effort, skills and networking, with good friends and supportive siblings. Initiative "
                "turns into income, and your wishes come true when you act on them.",
                "Income from hobbies, media or communication.",
                "Elder siblings and friends open doors.",
                "Taking initiative fulfils your wishes."),
    (3, 12): _p("Effort and courage work best far from home or behind the scenes. Writing, research, travel or "
                "spiritual practice suit you, and energy spread too thin is the main thing to watch.",
                "Your effort shows best in research, background work or projects abroad.",
                "Younger siblings may live far away, or you support them quietly.",
                "Spiritual practice and retreat can be your form of courage."),

    # ----- 4th lord: home, mother and peace -----
    (4, 1): _p("Inner peace and a happy home are part of who you are. Comfort, education and your mother’s support "
               "shape your personality, and people find you warm and steady.",
               "A warm, homely personality.",
               "Property and vehicles come in time.",
               "Your mother’s influence is strong."),
    (4, 2): _p("Home and family wealth go together: property, family assets and a comfortable family life. What the "
               "family owns tends to grow and stay in the family.",
               "Family property or land.",
               "Earning from property, vehicles or education.",
               "Close ties with your mother’s family."),
    (4, 3): _p("Comforts come through effort, and you may move home a few times. Siblings may share the home, and "
               "your peace of mind comes from staying active rather than sitting still.",
               "Writing or working from home.",
               "Short trips linked to property or family.",
               "Activity builds your peace of mind."),
    (4, 4): _p("A 4th lord at home: a happy home, property, vehicles and a supportive mother. Inner peace comes "
               "naturally, and your home is your source of strength.",
               "You are likely to own property in time.",
               "A close, warm family atmosphere.",
               "Inner calm and a good education."),
    (4, 5): _p("Home and mother are a source of wisdom and support; happiness comes through children, study and a "
               "creative life. A kendra lord in a trikona is a classic auspicious link.",
               "A happy home life centred on children, study and creativity.",
               "Your mother is wise or devout, and supports your education.",
               "Property and vehicles come through good advice, education or children."),
    (4, 6): _p("Home life is busy with work and duties, and property or vehicles may involve loans or paperwork. "
               "Patience and good records bring peace.",
               "Keep property and loan papers in good order.",
               "Your mother’s health may need attention.",
               "Working from home, or serving the family at home."),
    (4, 7): _p("Happiness through marriage and partners: your spouse brings comfort. Property may come through "
               "business or partnership, and two kendra lords linked support each other.",
               "A home shared happily with your partner.",
               "Property linked to business.",
               "You may live away from your birthplace after marriage."),
    (4, 8): _p("Changes of home and property, and inheritance is possible. Inner peace comes through understanding "
               "life’s deeper side rather than holding on to the familiar.",
               "Family or ancestral property.",
               "Moves of residence; check property papers carefully.",
               "Meditation helps your peace of mind."),
    (4, 9): _p("A fortunate home life: blessings from both parents, a devout home, and property by good fortune. "
               "Higher learning and faith make your home a happy place.",
               "Pilgrimage, temples or a religious home.",
               "Property through your father or through luck.",
               "Higher education brings comfort."),
    (4, 10): _p("Home and career connect: success in property, education or vehicles, and a respected family. Two "
                "kendra lords linked strengthen both home and work.",
                "Property, education, farming or hospitality careers.",
                "Working from home or in a family business.",
                "Balance your time between home and work."),
    (4, 11): _p("Gains through property, vehicles and your mother, and your wish for a good home comes true. Comforts "
                "increase as income grows.",
                "Income from property or rentals.",
                "Friends who feel like family.",
                "Comforts increase steadily."),
    (4, 12): _p("Home may be far from your birthplace or abroad, and spending goes on home and comforts. Peace comes "
                "through spiritual practice rather than possessions.",
                "Settling abroad or far from where you were born.",
                "Plan expenses on your home and vehicles.",
                "Meditation and retreats bring peace."),

    # ----- 5th lord: children, intelligence and past merit -----
    (5, 1): _p("Intelligent and creative, with past merit that shows in your personality. Children and students look "
               "up to you, and your judgement guides others; a trikona lord in the lagna is a blessing.",
               "Advising, teaching or creative work.",
               "Good judgement in decisions.",
               "Children bring joy and pride."),
    (5, 2): _p("Wealth through intelligence, education and investments, in a learned family. Children may add to the "
               "family’s fortune, and your knowledge becomes your income.",
               "Earning through knowledge, advice or creativity.",
               "Sound long-term investments.",
               "Good speech and a love of learning."),
    (5, 3): _p("Creative communication: writing, the arts and media. Your intelligence shows through effort and "
               "practice, and your ideas travel when you share them.",
               "Writing, performance or media.",
               "Children may be talented communicators.",
               "You learn best through practice."),
    (5, 4): _p("Happiness at home through children and learning, with a good education and a peaceful mind. A "
               "trikona lord in a kendra brings fortune into home life.",
               "Higher education and a learned home.",
               "Property through intelligence or through children.",
               "A close bond between your mother and your children."),
    (5, 5): _p("A 5th lord at home: intelligence, creativity, joy from children and good fortune from past merit. Your "
               "mind is your greatest asset.",
               "Success in education and creative fields.",
               "Joy from children.",
               "Good intuition and judgement."),
    (5, 6): _p("Intelligence applied to service, problem-solving and competition. Studies and children’s matters ask "
               "for patience, and speculation is best avoided.",
               "Medicine, law or competitive exams.",
               "Avoid speculation and loans.",
               "A healthy routine supports your concentration."),
    (5, 7): _p("Romance and partnership are linked: love may lead to marriage, and your partner is intelligent and "
               "creative. A trikona lord in a kendra supports married life.",
               "A creative or learned partner.",
               "Business built on ideas and creativity.",
               "Children bring you and your partner closer."),
    (5, 8): _p("A deep, intuitive intelligence, drawn to research, the occult and hidden knowledge. Studies or "
               "children’s matters may take patience, and insight often comes suddenly.",
               "Research, astrology, psychology or investigation.",
               "Avoid risky speculation.",
               "Sudden insights and changes of direction."),
    (5, 9): _p("Children, intelligence and past merit are tied to luck, dharma and teachers: one of the best places "
               "for a 5th lord. Two trikona lords linked bring real fortune.",
               "A natural pull towards higher study, philosophy, law or religion.",
               "Children may be fortunate, or may study far away.",
               "Good ideas come with faith; guiding others suits you."),
    (5, 10): _p("Intelligence drives your career: success through ideas, advice and creativity. The 5th and 10th "
                "lords linked form a Raja yoga, and recognition comes for what you know.",
                "Advisory, teaching, government or creative leadership.",
                "Recognition for your intelligence.",
                "Children may follow your profession."),
    (5, 11): _p("Gains through intelligence, investments and children, and wishes tend to be fulfilled. Ideas turn "
                "into income, and friends share your interests.",
                "Income from creative work or investments.",
                "Friends from education or creative circles.",
                "Children support your gains."),
    (5, 12): _p("Intelligence turns inward or abroad: spiritual study or education overseas. Spending goes on "
                "children or creative pursuits, and mantra and meditation come easily.",
                "Study or work abroad.",
                "Meditation, mantra and spiritual learning.",
                "Plan your spending on children and leisure."),

    # ----- 6th lord: work, service, health and rivals -----
    (6, 1): _p("Competitive and hard-working: you take challenges on directly. You are good in a crisis, and your "
               "health and stress levels need regular care.",
               "Service, health care, law or defence.",
               "You overcome rivals by effort.",
               "Routine, exercise and rest keep you strong."),
    (6, 2): _p("Money through service and work; the family may face disagreements or spending on health. Careful "
               "speech and a healthy diet help.",
               "Earning through jobs and service.",
               "Avoid loans within the family.",
               "A healthy diet and kind words."),
    (6, 3): _p("Effort defeats obstacles: good for competition and courage. Siblings may be competitive, and you grow "
               "stronger through every challenge you take on.",
               "Sport, defence or competitive careers.",
               "You win through persistence.",
               "Keep relations with siblings friendly."),
    (6, 4): _p("Work and duties touch home life, and property or vehicles may involve loans. Your mother’s health "
               "needs care, and a calm routine at home helps.",
               "Handle property paperwork carefully.",
               "Working from home is possible.",
               "Peace of mind comes through routine."),
    (6, 5): _p("Effort in studies and with children; competitive exams suit you. Avoid speculation, and give "
               "children’s needs patience.",
               "Competitive studies and exams.",
               "Patience with children’s needs.",
               "Avoid gambling and risky investments."),
    (6, 6): _p("The 6th lord at home forms Harsha yoga: you overcome rivals, setbacks and illness well. Good for "
               "service and competition, and debts stay under control.",
               "Strong resistance to rivals and setbacks.",
               "Service or health careers do well.",
               "Debts stay manageable."),
    (6, 7): _p("Partnerships need care: differences with a spouse or business partners are possible. Clear "
               "agreements, patience and respect keep them strong.",
               "Use written contracts in business.",
               "Patience and respect in marriage.",
               "Work with clients or the public."),
    (6, 8): _p("Harsha Vipareeta Raja yoga: obstacles tend to undo themselves, and difficulties turn into gain. Rivals "
               "lose their hold, and you come through hard times well.",
               "Rivals lose their power over you.",
               "Research, insurance or healing work.",
               "Regular health check-ups."),
    (6, 9): _p("Daily work and service connect with teachers, the father’s side or long journeys. Keep dealings with "
               "elders clear and fair, and work with purpose.",
               "Work in teaching, law, religious or charitable bodies, travel or foreign service.",
               "Differences of view with a father figure or teacher; keep them respectful.",
               "Your health benefits from routine and purposeful work."),
    (6, 10): _p("A career in service, competition or problem-solving; hard work is rewarded with rising status. You do "
                "well where others find the work too demanding.",
                "Government service, health care, law or defence.",
                "Competitive workplaces suit you.",
                "Manage stress at work."),
    (6, 11): _p("Gains through service, competition and overcoming rivals, with income from employment. Effort turns "
                "steadily into earnings.",
                "Steady income from a job.",
                "Some friends may also be competitors.",
                "Keep loans to a minimum."),
    (6, 12): _p("Harsha Vipareeta Raja yoga: debts and rivals fade, and spending on health or service brings relief. "
                "Quiet, helpful work suits you.",
                "Work in hospitals, charities or abroad.",
                "Rivals lose ground.",
                "Rest and sleep restore your health."),

    # ----- 7th lord: marriage, partners and business -----
    (7, 1): _p("Partners and the public play a big part in your life, and your spouse influences you strongly. You "
               "grow through relationships and dealings with people.",
               "Good for business and dealing with the public.",
               "Marriage shapes your identity.",
               "Travel for work."),
    (7, 2): _p("Wealth through marriage and partnerships: your spouse adds to the family’s resources. Business and "
               "family money go hand in hand.",
               "Business with family or partners.",
               "Your spouse supports the finances.",
               "Speak kindly in partnerships."),
    (7, 3): _p("Your partner is courageous and active, and business comes through communication and travel. Deals "
               "come from talking, writing and moving around.",
               "Media, trade or travel business.",
               "Short trips with your partner.",
               "Siblings involved in partnerships."),
    (7, 4): _p("A happy home with your partner, and property through marriage or business. Two kendra lords linked "
               "support each other, and married life brings comfort.",
               "A comfortable married life.",
               "Property or vehicles through partnership.",
               "Your partner gets on well with your mother."),
    (7, 5): _p("Love and marriage are connected, with a creative, intelligent partner. A kendra lord in a trikona "
               "blesses the relationship, and children strengthen it.",
               "A love marriage is possible.",
               "Business that uses creativity.",
               "Children strengthen the bond."),
    (7, 6): _p("Partnerships need care and clear agreements; your partner may be service-minded. Patience turns "
               "differences into understanding.",
               "Use written contracts.",
               "Patience in marriage.",
               "Your partner may work in health or service."),
    (7, 7): _p("A 7th lord at home: a good partner, and success in business and public life. Partnerships tend to be "
               "stable and supportive.",
               "Stable partnerships.",
               "Business and client work.",
               "A respected spouse."),
    (7, 8): _p("Partnerships go through changes, and your spouse may bring an inheritance or a deep transformation. "
               "Patience and openness strengthen the bond.",
               "Joint finances, or inheritance through your spouse.",
               "Avoid hasty decisions in relationships.",
               "Your spouse’s health needs care."),
    (7, 9): _p("Your partner brings luck and values; marriage can come through teachers, travel or another culture. "
               "Fortune often rises after marriage.",
               "Your partner may come from another culture, place or background, or through teachers or travel.",
               "Fortune often rises after marriage or a key partnership.",
               "Business partners do best when ethics and learning are shared."),
    (7, 10): _p("Career through partnerships, business or public dealing; your spouse supports your work. Two kendra "
                "lords linked strengthen both marriage and career.",
                "Business, consulting, law or diplomacy.",
                "You may work alongside your spouse.",
                "Public recognition."),
    (7, 11): _p("Gains through partners and marriage; friends may become business partners. Partnerships tend to pay, "
                "and your social circle widens after marriage.",
                "Profitable partnerships.",
                "Your spouse brings gains.",
                "A wide social circle."),
    (7, 12): _p("Your partner may come from far away, or marriage may take you abroad, with spending on "
                "relationships. Shared time and shared values keep you close.",
                "A partner from abroad, or living abroad.",
                "Expenses on your partner.",
                "A shared spiritual life."),

    # ----- 8th lord: change, hidden matters and research -----
    (8, 1): _p("Life brings deep changes that build resilience, and an interest in research and the hidden side of "
               "life. You understand people and situations deeply.",
               "Research, investigation or healing.",
               "A regular health routine.",
               "Transformation through experience."),
    (8, 2): _p("Finances see ups and downs, and inheritance is possible. Careful speech and an emergency fund help, "
               "and family money may come through unexpected routes.",
               "Inheritance or joint family money.",
               "Keep savings for surprises.",
               "Speak gently within the family."),
    (8, 3): _p("Courage is tested by sudden change, and your skills suit research. Patience with siblings, and care "
               "while travelling, keep things steady.",
               "Investigative writing or research.",
               "Take care while travelling.",
               "Siblings may need your support at times."),
    (8, 4): _p("Changes of home or residence, and inheritance of property is possible. Inner calm comes through "
               "spiritual practice and accepting change.",
               "Family or inherited property.",
               "Check property papers before you buy.",
               "Meditation brings peace of mind."),
    (8, 5): _p("A deep, intuitive mind; studies or children’s matters may need patience. Insight comes suddenly, "
               "and hidden knowledge attracts you.",
               "Occult study or research.",
               "Avoid speculation.",
               "Patience with children’s matters."),
    (8, 6): _p("Sarala Vipareeta Raja yoga: hidden obstacles defeat themselves, and difficulties turn into strength. "
               "You recover well and outlast rivals.",
               "Rivals weaken over time.",
               "Health improves with care.",
               "Good for research and healing work."),
    (8, 7): _p("Partnerships transform you, and your spouse may bring change or an inheritance. Openness and honest "
               "talk strengthen the marriage.",
               "Joint finances with your spouse.",
               "Talk things through rather than react.",
               "Your spouse’s family may play a big role."),
    (8, 8): _p("An 8th lord at home forms Sarala yoga: resilience, depth and an interest in research and the occult. "
               "Changes lead to renewal rather than loss.",
               "Research, insurance or occult sciences.",
               "Inheritance is possible.",
               "Resilience in tough times."),
    (8, 9): _p("Your beliefs are tested and deepened, and there may be changes around your father or teachers. Fortune "
               "comes after patience, and faith grows through experience.",
               "Deep study of philosophy or the occult.",
               "Support your father when he needs it.",
               "Faith grows through experience."),
    (8, 10): _p("Your career has changes and turning points; research, investigation or behind-the-scenes work suits "
                "you. Each change tends to bring renewal.",
                "Research, insurance, surgery, mining or investigation.",
                "Career changes bring growth.",
                "Keep work relationships transparent."),
    (8, 11): _p("Gains through sudden events, inheritance or research, and income can fluctuate. Saving in good "
                "months smooths the rest.",
                "Income from research, insurance or inheritance.",
                "Save during good months.",
                "Friends from unusual or deep fields."),
    (8, 12): _p("Sarala Vipareeta Raja yoga: sudden changes and hidden matters are spent away, and difficult phases "
                "tend to end in gain. Rest and quiet restore you.",
                "A deep, private emotional life, and interest in research, the occult or healing.",
                "Unexpected expenses or changes that tend to resolve in your favour.",
                "Rest, sleep and time alone recharge you."),

    # ----- 9th lord: fortune, father, teachers and dharma -----
    (9, 1): _p("Fortunate and principled: luck follows your own effort, and you are respected for your values. A "
               "trikona lord in the lagna blesses your whole life.",
               "Teaching, law, religion or advisory roles.",
               "Support from your father and mentors.",
               "Long journeys bring growth."),
    (9, 2): _p("Wealth through fortune, your father and righteous work, in a blessed family. Money comes more easily "
               "when you act with integrity.",
               "Income through teaching, advice or tradition.",
               "Family wealth grows over generations.",
               "Generosity brings more fortune."),
    (9, 3): _p("Fortune through effort and courage, with travel and communication about dharma. Your initiative is "
               "lucky, especially when it serves a belief.",
               "Writing or speaking on values and beliefs.",
               "Pilgrimages and long journeys.",
               "Siblings may be lucky for you."),
    (9, 4): _p("Blessings at home: a devout home, property by good fortune and a supportive mother. A trikona lord in a "
               "kendra brings luck into home life.",
               "Property through your father or through luck.",
               "Religious practice at home.",
               "Higher education brings comfort."),
    (9, 5): _p("Two trikona lords linked: great fortune through intelligence, children and past merit. Luck and wisdom "
               "work together in your life.",
               "Success in education, teaching or advisory work.",
               "Children bring fortune.",
               "Spiritual practice and mantra come naturally."),
    (9, 6): _p("Fortune through service and work, and differences with your father or teachers need care. Luck grows "
               "with steady, honest work.",
               "Service in law, health or religious bodies.",
               "Support your father’s health.",
               "Luck grows with steady work."),
    (9, 7): _p("Fortune through your spouse and partners: marriage brings luck. A trikona lord in a kendra is a Raja "
               "yoga link, so partnerships raise you.",
               "A principled, fortunate partner.",
               "Business with ethical partners.",
               "Travel after marriage."),
    (9, 8): _p("Fortune comes after tests, with an interest in deep philosophy and the occult. Your father’s matters "
               "need care, and luck often arrives after delays.",
               "Research into religion, philosophy or astrology.",
               "Patience with your father’s needs.",
               "Luck often arrives after delays."),
    (9, 9): _p("A strong 9th lord at home: fortune, faith, a guiding father figure and good teachers. Luck rises "
               "through ethics, higher learning and long journeys.",
               "Luck rises through right action, ethics and higher learning.",
               "A strong father figure or mentor shapes your path.",
               "Long journeys, pilgrimage and teaching bring blessings."),
    (9, 10): _p("Dharma–Karmadhipati Raja yoga: a rise through meaningful work, one of the most respected links. Your "
                "career serves a larger purpose and brings honour.",
                "Teaching, law, religion, government or advisory careers.",
                "Mentors open doors in your career.",
                "Your work serves a larger purpose."),
    (9, 11): _p("Gains through fortune, mentors and your father, and wishes are fulfilled. Principled friends and good "
                "luck support your income.",
                "Income through teaching or advice.",
                "Influential, principled friends.",
                "Luck in gains and wishes."),
    (9, 12): _p("Fortune abroad or in spiritual life, with spending on religion, travel and charity. Giving and going "
                "far bring you luck.",
                "Living or travelling abroad brings luck.",
                "Charity and pilgrimage.",
                "A strong spiritual path."),

    # ----- 10th lord: career, status and action -----
    (10, 1): _p("A self-made career: your work defines you, and you lead naturally. Two kendra matters meet in you, so "
                "your actions and your identity are one.",
                "Leadership or running your own business.",
                "Recognition for your personal effort.",
                "Health and energy matter for your work."),
    (10, 2): _p("Your career brings wealth, often through finance, speech or a family business. Steady work builds "
                "steady money.",
                "Banking, finance, teaching or speaking.",
                "A family business.",
                "Steady income from your profession."),
    (10, 3): _p("Career through communication, media, travel and skills. You rise by doing, writing and connecting, "
                "and your career keeps you on the move.",
                "Media, marketing, writing, sales or technology.",
                "Frequent work travel.",
                "Siblings may join your work."),
    (10, 4): _p("Career linked to home, property, education or vehicles. Two kendra lords linked strengthen both home "
                "and work, and the family name matters.",
                "Property, education, farming or hospitality.",
                "Working from home or a family business.",
                "A respected family name."),
    (10, 5): _p("A Raja yoga link: career through intelligence, advice and creativity. You are recognised for your "
                "ideas, and your work uses your mind.",
                "Advisory, teaching or creative careers.",
                "Investment or analysis as part of your work.",
                "Recognition for your ideas."),
    (10, 6): _p("A career in service, competition, health or law, where hard work is rewarded. You rise by solving "
                "problems others avoid.",
                "Government service, health care, law or defence.",
                "You do well in competitive workplaces.",
                "Manage work stress."),
    (10, 7): _p("Career through partnerships and the public: business suits you. Two kendra lords linked strengthen "
                "both, and clients may come from far away.",
                "Business, trade, consulting or law.",
                "You may work abroad or with clients from far away.",
                "Your spouse supports your career."),
    (10, 8): _p("Your career has changes and turning points; research or behind-the-scenes work suits you. Each "
                "change tends to renew your direction.",
                "Research, insurance, surgery or investigation.",
                "Career changes bring renewal.",
                "Save for periods between jobs."),
    (10, 9): _p("Career tied to knowledge, teaching, advice, law, publishing or travel: work that feels meaningful. "
                "With the 9th lord this is the Dharma–Karmadhipati link.",
                "Meaningful work in teaching, advice, law, publishing, travel or religion.",
                "Mentors and elders open doors in your career.",
                "Changes of job often bring you closer to your purpose."),
    (10, 10): _p("A 10th lord at home: success, status and authority through your work. Your career is stable and "
                 "you are known in your field.",
                 "A strong, stable career.",
                 "Leadership positions.",
                 "Recognition in your field."),
    (10, 11): _p("Your career brings steady gains and influential contacts. Ambitions tend to be fulfilled, and your "
                 "network grows with your position.",
                 "High income from your profession.",
                 "Networking helps your career.",
                 "Your ambitions tend to be fulfilled."),
    (10, 12): _p("A career abroad or behind the scenes: foreign companies, hospitals, research or spiritual "
                 "institutions. Plan for the costs of building your career.",
                 "Work abroad or in foreign companies.",
                 "Behind-the-scenes or research roles.",
                 "Spending on education or travel for work."),

    # ----- 11th lord: gains, friends and wishes -----
    (11, 1): _p("Gains come to you readily, and friends and income support your path. People like to help you, and "
                "your wishes tend to come true through your own effort.",
                "Income through your own effort.",
                "A friendly, sociable nature.",
                "Elder siblings help you."),
    (11, 2): _p("A strong wealth link (Dhana yoga): income and savings support each other. Money that comes in tends "
                "to stay and grow.",
                "Steady savings.",
                "Family wealth grows.",
                "Earning through speech or finance."),
    (11, 3): _p("Gains through effort, skills and communication, with supportive siblings. Initiative brings rewards, "
                "and several small efforts add up.",
                "Income from media, writing or skills.",
                "Siblings help you gain.",
                "Initiative brings rewards."),
    (11, 4): _p("Gains through property, vehicles and home-based work. Your wish for comfort is fulfilled, and your "
                "mother supports your progress.",
                "Income from property or rentals.",
                "Comforts at home increase.",
                "Your mother supports your gains."),
    (11, 5): _p("Gains through intelligence, investments and children: a Dhana link. Your ideas pay, and learned "
                "friends support you.",
                "Income from creative work or investments.",
                "Children bring gains.",
                "Learned friends."),
    (11, 6): _p("Gains through service and competition, and loans are best avoided. Hard work brings steady income, "
                "especially in demanding fields.",
                "Income from a job.",
                "Competitive workplaces pay well.",
                "Keep debts low."),
    (11, 7): _p("Gains through partners and marriage. Business and partnerships bring income, and friends may become "
                "partners.",
                "Profitable partnerships.",
                "Your spouse brings gains.",
                "Friends become partners."),
    (11, 8): _p("Gains through sudden events, inheritance or research, and income can fluctuate. Saving in good "
                "months keeps you secure.",
                "Income from insurance, research or inheritance.",
                "Save during good months.",
                "Unusual but useful friends."),
    (11, 9): _p("Gains through fortune, mentors, the father’s side and long-distance links. With the 9th lord this "
                "forms a Dhana yoga, and wishes come true through dharma.",
                "Gains through fortune, mentors, institutions and long-distance links.",
                "Friends tend to be learned or spiritual.",
                "Wishes come true when they align with your values."),
    (11, 10): _p("Gains through career and status, with an influential network. Your position brings income, and "
                 "your ambitions are fulfilled.",
                 "High earnings from your work.",
                 "Seniors and contacts help your career.",
                 "Ambitions are fulfilled."),
    (11, 11): _p("An 11th lord at home: steady gains and supportive friends, and wishes are fulfilled. Income tends to "
                 "come from more than one source.",
                 "Many sources of income.",
                 "A loyal circle of friends.",
                 "Elder siblings do well."),
    (11, 12): _p("Gains go towards travel, charity or life abroad, and income from foreign sources is possible. "
                 "Balance what comes in with what goes out.",
                 "Income from abroad.",
                 "Spending on friends and causes.",
                 "Balance income and spending."),

    # ----- 12th lord: expenses, abroad and release -----
    (12, 1): _p("A spiritual, generous nature, and you may live abroad. Keep an eye on expenses and rest, and give "
                "yourself quiet time to recharge.",
                "Living or working abroad.",
                "Generosity and charity.",
                "Regular sleep and rest."),
    (12, 2): _p("Expenses on family, so plan your finances. Income from foreign sources is possible, and a savings "
                "plan keeps the family secure.",
                "Spending on family needs.",
                "Earnings from abroad.",
                "A savings plan helps."),
    (12, 3): _p("Spending on travel and hobbies; siblings may live abroad; effort goes into spiritual practice. Your "
                "energy works best in private or far away.",
                "Travel and hobbies cost more than you expect.",
                "Siblings abroad.",
                "Writing or practice done in private."),
    (12, 4): _p("A home away from your birthplace, with expenses on home. Peace comes through spiritual practice "
                "rather than possessions.",
                "Settling far away or abroad.",
                "Plan spending on your home.",
                "Meditation at home."),
    (12, 5): _p("Spending on children and education; spiritual study or education abroad. Mantra and meditation suit "
                "your mind.",
                "Studies abroad.",
                "Spending on children.",
                "Mantra and spiritual learning."),
    (12, 6): _p("Vimala Vipareeta Raja yoga: losses and expenses reduce, and rivals weaken. Spending comes under "
                "control and quiet service brings relief.",
                "Rivals lose ground.",
                "Expenses come under control.",
                "Service in hospitals or charities."),
    (12, 7): _p("A partner from abroad, or marriage abroad, with expenses on your partner. Shared spiritual interests "
                "keep you close.",
                "A partner from a distant place.",
                "Travel with your partner.",
                "Shared spiritual interests."),
    (12, 8): _p("Vimala Vipareeta Raja yoga: losses tend to turn into gains, with an interest in the occult and "
                "spiritual release. Unexpected relief comes in hard times.",
                "Research or the occult.",
                "Unexpected relief from expenses.",
                "A deep spiritual life."),
    (12, 9): _p("Spending goes to travel, pilgrimage, higher study or your father, and foreign lands can be lucky. A "
                "12th lord in a trikona spends on good causes.",
                "Money spent on travel, study, pilgrimage or a teacher.",
                "Living or working abroad can be lucky.",
                "A spiritual practice linked to a teacher or tradition grows over time."),
    (12, 10): _p("A career abroad or in foreign companies, hospitals or ashrams, with expenses for your career. Work "
                 "behind the scenes suits you.",
                 "Work abroad.",
                 "Behind-the-scenes roles.",
                 "Plan your career spending."),
    (12, 11): _p("Gains from abroad and spending on friends, so balance income and expenses. Foreign links can be a "
                 "steady source of income.",
                 "Income from foreign sources.",
                 "Generous with friends.",
                 "Track your spending."),
    (12, 12): _p("A 12th lord at home forms Vimala yoga: comfortable expenses, peaceful sleep and spiritual growth. "
                 "Life abroad is favourable.",
                 "Living abroad suits you.",
                 "Restful sleep and retreats.",
                 "A growing spiritual life."),
}
