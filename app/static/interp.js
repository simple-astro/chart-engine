// Rule-based chart interpretation. Builds readable text from the /chart response
// using classical significations; it is general guidance, not a personal prediction.
(function () {
  const SIGN = {
    Aries: 'direct, energetic and self-starting; quick to act and to lead',
    Taurus: 'steady, practical and sensual; values security, comfort and loyalty',
    Gemini: 'curious, communicative and adaptable; thrives on ideas and variety',
    Cancer: 'sensitive, caring and protective; strongly tied to home, family and mood',
    Leo: 'confident, warm and proud; wants recognition and to take the lead',
    Virgo: 'analytical, careful and service-minded; attentive to detail and improvement',
    Libra: 'diplomatic, fair-minded and relationship-oriented; seeks balance and harmony',
    Scorpio: 'intense, private and determined; drawn to depth, research and transformation',
    Sagittarius: 'optimistic, freedom-loving and philosophical; seeks meaning and growth',
    Capricorn: 'disciplined, ambitious and responsible; patient builder of long-term goals',
    Aquarius: 'independent, original and humanitarian; values ideas, friends and reform',
    Pisces: 'imaginative, compassionate and intuitive; spiritual and sometimes escapist',
  };
  const PLANET = {
    Sun: 'self, vitality, authority and father',
    Moon: 'mind, emotions, mother and public',
    Mars: 'energy, courage, drive and conflict',
    Mercury: 'intellect, speech, trade and learning',
    Jupiter: 'wisdom, growth, teachers and fortune',
    Venus: 'love, partnership, comfort and the arts',
    Saturn: 'discipline, duty, delay and endurance',
    Rahu: 'ambition, obsession, foreign and unconventional themes',
    Ketu: 'detachment, past-life skills and spiritual insight',
  };
  const HOUSE = {
    1: 'self, body and personality', 2: 'wealth, family and speech', 3: 'courage, siblings and effort',
    4: 'home, mother, property and inner peace', 5: 'children, creativity, intelligence and romance',
    6: 'work, health, service, debts and competition', 7: 'marriage, partnerships and business',
    8: 'transformation, longevity, inheritance and the hidden', 9: 'fortune, dharma, higher learning and father',
    10: 'career, status and public life', 11: 'gains, networks and fulfilment of desires',
    12: 'losses, expenses, foreign lands, sleep and moksha',
  };
  const KEY = {
    1: 'personality & health', 2: 'finances & family', 3: 'initiative & siblings', 4: 'home & property',
    5: 'children & creativity', 6: 'job, service & health issues', 7: 'marriage & partnerships',
    8: 'sudden change & research', 9: 'luck & higher learning', 10: 'career & reputation',
    11: 'income & gains', 12: 'expenses & foreign/spiritual matters',
  };
  const KENDRA = [1, 4, 7, 10], TRIKONA = [1, 5, 9], DUSTHANA = [6, 8, 12];
  const esc = s => String(s).replace(/[&<>]/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;' }[c]));
  const list = a => a.length <= 1 ? a.join('') : a.slice(0, -1).join(', ') + ' and ' + a[a.length - 1];

  window.interpret = function (c) {
    const g = c.grahas, l = c.lagna, houses = c.houses, out = [];
    const ownedBy = p => houses.filter(h => h.sign_lord === p).map(h => h.house);
    const nature = h => KENDRA.includes(h) ? 'a pillar (kendra) house' : TRIKONA.includes(h) ? 'a fortunate (trikona) house' : DUSTHANA.includes(h) ? 'a challenging (dusthana) house' : 'a growth (upachaya/neutral) house';

    // 1. Core personality
    const moon = g.Moon, sun = g.Sun, core = [];
    core.push(`<b>Lagna (${esc(l.sign)}):</b> outwardly ${SIGN[l.sign]}.`);
    core.push(`<b>Moon (${esc(moon.sign)}, ${esc(moon.nakshatra)} pada ${moon.pada}):</b> emotionally ${SIGN[moon.sign]}. Its nakshatra lord ${esc(moon.nakshatra_lord)} colours the mind and the starting daśā.`);
    core.push(`<b>Sun (${esc(sun.sign)}):</b> sense of purpose and authority is ${SIGN[sun.sign]}.`);
    out.push({ title: 'Core personality', items: core });

    // 2. Planets in houses
    const pl = Object.entries(g).map(([n, p]) => {
      let t = `<b>${n} in H${p.house}</b> (${esc(p.sign)}): ${PLANET[n]} are directed toward ${HOUSE[p.house]} — ${nature(p.house)}.`;
      const notes = [];
      if (p.retrograde) notes.push('retrograde, so results turn inward and come with review or delay');
      if (p.combust) notes.push('combust (close to the Sun), so its independence is reduced');
      if (notes.length) t += ' It is ' + notes.join('; ') + '.';
      return t;
    });
    out.push({ title: 'Planets in houses', items: pl });

    // 3. House lords
    const hl = houses.map(h => {
      const lord = h.sign_lord, at = g[lord].house;
      const where = at === h.house ? 'in its own house, which strengthens the matters of this house'
        : DUSTHANA.includes(at) ? 'in a difficult house, so these matters need extra effort or can bring ups and downs'
        : KENDRA.includes(at) || TRIKONA.includes(at) ? 'in a supportive house, which tends to help these matters'
        : 'in a neutral house';
      return `<b>H${h.house} (${KEY[h.house]})</b>, lord ${lord} sits in H${at}: links ${HOUSE[h.house].split(',')[0]} with ${HOUSE[at].split(',')[0]} — ${where}.`;
    });
    out.push({ title: 'House lords: where they sit', items: hl });

    // 4. KP significations (house results by sub-lord promise)
    const sg = c.significators, kp = [];
    for (const h of houses) {
      const sub = h.kp.sub_lord, sigs = (sg.by_planet[sub] || {}).houses || [];
      const good = sigs.filter(x => x !== h.house).length;
      kp.push(`<b>H${h.house} (${KEY[h.house]}):</b> cusp sub-lord ${sub} signifies houses ${sigs.join(', ') || '—'}` +
        (sigs.includes(h.house) ? ` — it supports its own house, a positive promise.` : ` — it does not signify H${h.house} directly, so results come indirectly or later.`));
    }
    out.push({ title: 'KP view: promise of each house (cusp sub-lord)', items: kp });

    // 5. Strengths & flags
    const flags = [];
    const kendraPl = Object.entries(g).filter(([, p]) => KENDRA.includes(p.house)).map(([n]) => n);
    const dust = Object.entries(g).filter(([, p]) => DUSTHANA.includes(p.house)).map(([n]) => n);
    if (kendraPl.length) flags.push(`Planets in kendra houses (1/4/7/10): ${list(kendraPl)} — these tend to be visible and active in life.`);
    if (dust.length) flags.push(`Planets in dusthana houses (6/8/12): ${list(dust)} — areas that ask for patience, resilience or inner work.`);
    const retro = Object.entries(g).filter(([n, p]) => p.retrograde && n !== 'Rahu' && n !== 'Ketu').map(([n]) => n);
    if (retro.length) flags.push(`Retrograde: ${list(retro)} — qualities of these planets are more internal and may mature later.`);
    const stel = Object.entries(g).filter(([n, p]) => p.house === g[p.kp.star_lord].house && n !== p.kp.star_lord).map(([n]) => n);
    if (stel.length) flags.push(`${list(stel)} share a house with their star lord, which strongly links their results to that house.`);
    out.push({ title: 'Strengths & points to note', items: flags.length ? flags : ['No standout flags.'] });

    // 6. Current daśā
    const now = Date.now(), cur = (c.dasha || []).find(d => now >= new Date(d.start) && now < new Date(d.end));
    if (cur) {
      const sub = (cur.children || []).find(d => now >= new Date(d.start) && now < new Date(d.end));
      const desc = n => {
        const sig = (sg.by_planet[n] || {}).houses || [], own = ownedBy(n);
        return `${n} (${PLANET[n]}) — placed in H${g[n].house}, rules H${own.join(', H') || '—'}, signifies ${sig.map(x => 'H' + x).join(', ') || '—'}.`;
      };
      const fd = s => new Date(s).toLocaleDateString(undefined, { year: 'numeric', month: 'short' });
      const items = [`<b>Mahā daśā ${cur.lord}</b> (${fd(cur.start)} – ${fd(cur.end)}): ${desc(cur.lord)} Themes of those houses dominate this period.`];
      if (sub) items.push(`<b>Antar daśā ${sub.lord}</b> (${fd(sub.start)} – ${fd(sub.end)}): ${desc(sub.lord)} Expect the sub-period's events to blend ${cur.lord} and ${sub.lord} themes.`);
      out.push({ title: 'Current period (Vimśottarī daśā)', items });
    }
    return out;
  };
})();
