// Tap a house: highlight it, draw arrows from the planets that aspect it, and read it in plain words.
// The aspects follow the engine (core/yogas.py SPECIAL): all planets the 7th; Mars 4/8; Jupiter, Rahu, Ketu 5/9;
// Saturn 3/10. Houses are whole-sign from the lagna, as drawn.
(function () {
  const esc = s => String(s ?? '').replace(/[&<>"]/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));
  const SIGNS = ['Aries', 'Taurus', 'Gemini', 'Cancer', 'Leo', 'Virgo', 'Libra', 'Scorpio', 'Sagittarius', 'Capricorn', 'Aquarius', 'Pisces'];
  const LORD = ['Mars', 'Venus', 'Mercury', 'Moon', 'Sun', 'Mercury', 'Venus', 'Mars', 'Jupiter', 'Saturn', 'Saturn', 'Jupiter'];
  const SPECIAL = { Mars: [4, 7, 8], Jupiter: [5, 7, 9], Saturn: [3, 7, 10], Rahu: [5, 7, 9], Ketu: [5, 7, 9] };
  const UPACHAYA = [3, 6, 10, 11];
  const ord = n => n + (n % 100 >= 11 && n % 100 <= 13 ? 'th' : ({ 1: 'st', 2: 'nd', 3: 'rd' }[n % 10] || 'th'));
  const COVERS = {
    1: 'yourself — your body, health and how you come across', 2: 'money, savings, family and speech',
    3: 'courage, effort, siblings, skills and short trips', 4: 'home, mother, property, vehicles and peace of mind',
    5: 'children, studies, creativity, romance and past merit', 6: 'work, service, health routines, debts and rivals',
    7: 'marriage, partners and business deals', 8: 'sudden changes, research, inheritance and in-laws',
    9: 'luck, father, teachers, faith and long journeys', 10: 'career, status and public reputation',
    11: 'gains, income, friends and wishes coming true', 12: 'expenses, foreign lands, rest, giving and spiritual life',
  };
  const SHORT = { 1: 'self and health', 2: 'money and family', 3: 'effort and siblings', 4: 'home and mother', 5: 'children and studies',
    6: 'work and health routines', 7: 'marriage and partners', 8: 'sudden changes', 9: 'luck and father', 10: 'career and status',
    11: 'gains and friends', 12: 'expenses and foreign lands' };
  const STYLE = ['boldly and quickly', 'steadily, valuing comfort and security', 'with curiosity, words and variety',
    'with care and feeling, protecting your own', 'with pride, warmth and a wish to lead', 'carefully, with detail and service',
    'with balance, fairness and charm', 'intensely, privately and with depth', 'with optimism, principle and the big picture',
    'with discipline, patience and a long view', 'with ideas, independence and care for the group', 'intuitively, gently and with compassion'];
  const BRINGS = { Sun: 'authority and confidence', Moon: 'feeling and changing moods', Mars: 'energy, drive and some heat',
    Mercury: 'intelligence, talk and trade', Jupiter: 'wisdom, growth and protection', Venus: 'comfort, beauty and harmony',
    Saturn: 'discipline, delays and endurance', Rahu: 'ambition and the unusual', Ketu: 'detachment and inner depth' };

  function benefic(c, p) {
    if (p === 'Moon') return (c.grahas.Moon.longitude - c.grahas.Sun.longitude + 360) % 360 < 180; // waxing
    return ['Jupiter', 'Venus', 'Mercury'].includes(p);
  }
  const houseOf = (c, p) => (c.grahas[p].sign_index - c.lagna.sign_index + 12) % 12 + 1;

  // Planets aspecting house h: [{planet, from (house), n (which aspect), good}]
  function aspecting(c, h) {
    const out = [];
    Object.keys(c.grahas).forEach(p => {
      const from = houseOf(c, p);
      (SPECIAL[p] || [7]).forEach(n => { if ((from + n - 2) % 12 + 1 === h) out.push({ planet: p, from, n, good: benefic(c, p) }); });
    });
    return out;
  }

  window.houseFocusReading = function (c, h) {
    const sign = (c.lagna.sign_index + h - 1) % 12, lord = LORD[sign], lh = houseOf(c, lord);
    const inside = Object.keys(c.grahas).filter(p => houseOf(c, p) === h);
    const asp = aspecting(c, h);
    const dig = window.planetDignity ? window.planetDignity(c, lord) : null;
    const sav = c.ashtakavarga ? c.ashtakavarga.sav[sign] : null;
    const up = UPACHAYA.includes(h);
    // A simple tally: benefic touch helps; malefic touch strains, except in the growth houses (3, 6, 10, 11).
    let score = 0;
    inside.concat(asp.map(a => a.planet)).forEach(p => { score += benefic(c, p) ? 1 : up ? 0.5 : -1; });
    if (dig === 'exalted' || dig === 'own') score += 1; else if (dig === 'debilitated') score -= 1;
    if (sav != null) score += sav >= 28 ? 1 : sav < 25 ? -1 : 0;
    const verdict = score >= 1.5 ? ['good', 'Well supported'] : score <= -1.5 ? ['warn', 'Needs effort'] : ['', 'Mixed'];
    const lines = [];
    lines.push(`${SIGNS[sign]} here: you handle ${SHORT[h]} ${STYLE[sign]}.`);
    lines.push(`Its lord ${lord} sits in your ${ord(lh)} house${lh === h ? ' — in its own house, which keeps this area in your own hands' : `, so this area is tied to your ${SHORT[lh]}`}` +
      (dig === 'exalted' ? ', and is exalted: a strong lord.' : dig === 'own' ? ', in its own sign: a steady lord.' : dig === 'debilitated' ? ', but is debilitated: this area asks for extra care.' : '.'));
    if (inside.length) lines.push(`Planets here: ${inside.map(p => `${p} brings ${BRINGS[p]}`).join('; ')}${up && inside.some(p => !benefic(c, p)) ? ' — malefics grow stronger with time in this house of effort.' : '.'}`);
    else lines.push('No planets sit here, so its lord and the planets aspecting it shape it.');
    if (asp.length) lines.push(asp.map(a => `${a.planet} looks at this house (its ${ord(a.n)} aspect): ${a.good ? 'support and protection' : up ? 'push and drive — useful in this house' : 'pressure, so effort is needed'}`).join('. ') + '.');
    if (sav != null) lines.push(`Ashtakavarga score ${sav}: ${sav >= 28 ? 'this house gets good support' : sav < 25 ? 'results here come with more effort' : 'average support'}.`);
    return { h, sign: SIGNS[sign], covers: COVERS[h], lord, lordHouse: lh, inside, aspects: asp, sav, verdict, lines,
      ask: `Tell me about my ${ord(h)} house (${SIGNS[sign]}, which covers ${SHORT[h]}). Its lord ${lord} is in my ${ord(lh)} house` +
        (inside.length ? `, ${inside.join(', ')} ${inside.length > 1 ? 'are' : 'is'} in it` : '') + `. What does it mean for me, and what should I do?` };
  };

  // Highlight house h and draw curved arrows from each aspecting planet's house (green = benefic, red = malefic).
  const CENTRE = [[200, 95], [100, 45], [45, 100], [95, 200], [45, 300], [100, 355], [200, 305], [300, 355], [355, 300], [305, 200], [355, 100], [300, 45]];
  // A South Indian chart puts its own house centres on the svg (data-centres); North Indian uses CENTRE.
  const centres = svg => (svg && svg.dataset.centres ? JSON.parse(svg.dataset.centres) : CENTRE);
  window.drawHouseFocus = function (svg, c, h) {
    if (!svg) return;
    const CENTRE = centres(svg);
    svg.querySelectorAll('.hz').forEach(z => z.classList.toggle('sel', h != null && +z.dataset.h === h));
    let g = svg.querySelector('#harrows');
    if (g) g.remove();
    if (h == null) return;
    g = document.createElementNS('http://www.w3.org/2000/svg', 'g'); g.id = 'harrows';
    const [tx, ty] = CENTRE[h - 1];
    g.innerHTML = aspecting(c, h).map((a, i) => {
      const [fx, fy] = CENTRE[a.from - 1];
      const mx = (fx + tx) / 2, my = (fy + ty) / 2, dx = tx - fx, dy = ty - fy, len = Math.hypot(dx, dy) || 1;
      const bend = 40 + 12 * i, cx = mx - dy / len * bend, cy = my + dx / len * bend;
      // stop short of the target centre so the arrowhead sits on the house, not on its text
      const ex = tx - (tx - cx) / Math.hypot(tx - cx, ty - cy) * 18, ey = ty - (ty - cy) / Math.hypot(tx - cx, ty - cy) * 18;
      return `<path class="harrow ${a.good ? 'good' : 'bad'}" d="M${fx} ${fy} Q${cx} ${cy} ${ex} ${ey}" marker-end="url(#ah-${a.good ? 'good' : 'bad'})"/>`;
    }).join('');
    if (!svg.querySelector('#ah-good')) {
      const defs = svg.querySelector('defs') || svg.insertBefore(document.createElementNS('http://www.w3.org/2000/svg', 'defs'), svg.firstChild);
      defs.insertAdjacentHTML('beforeend', ['good', 'bad'].map(k => `<marker id="ah-${k}" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse"><path d="M0 0L10 5L0 10z" class="ahead ${k}"/></marker>`).join(''));
    }
    svg.appendChild(g);
  };

  // ----- Planet links on the chart, one kind at a time: Placement (where each house lord sits), Aspects, Conjunctions.
  // Colours follow the planet's role for this lagna (as today.chart_planets): helpful, needs care, or mixed.
  const ABR = { Sun: 'Su', Moon: 'Mo', Mars: 'Ma', Mercury: 'Me', Jupiter: 'Ju', Venus: 'Ve', Saturn: 'Sa', Rahu: 'Ra', Ketu: 'Ke' };
  const ORDER = Object.keys(ABR);
  const ADDS = { Sun: 'authority and recognition', Moon: 'feeling and public contact', Mars: 'drive and technical skill',
    Mercury: 'intellect and trade', Jupiter: 'wisdom and growth', Venus: 'comfort, art and relationships',
    Saturn: 'hard work and structure', Rahu: 'ambition and the unusual', Ketu: 'detachment and research' };
  const join = xs => xs.length < 2 ? (xs[0] || '') : xs.slice(0, -1).join(', ') + ' and ' + xs[xs.length - 1];
  const rulesOf = (c, p) => [...Array(12).keys()].map(i => i + 1).filter(h => LORD[(c.lagna.sign_index + h - 1) % 12] === p);
  function nature(c, p) {
    const hs = rulesOf(c, p), has = xs => hs.some(h => xs.includes(h));
    if ((has([4, 10]) && has([5, 9])) || has([1, 5, 9])) return 'good';
    return has([6, 8, 12]) ? 'bad' : 'mix';
  }
  const linkAspects = (c, p, nodes) => ((p === 'Rahu' || p === 'Ketu') && nodes === '7' ? [7] : SPECIAL[p] || [7])
    .map(n => (houseOf(c, p) + n - 2) % 12 + 1);
  function pairs(c) {
    const out = [];
    ORDER.forEach((a, i) => ORDER.slice(i + 1).forEach(b => {
      if (c.grahas[a].sign_index === c.grahas[b].sign_index)
        out.push({ a, b, gap: Math.round(Math.abs(c.grahas[a].degrees_in_sign - c.grahas[b].degrees_in_sign)) });
    }));
    return out.sort((x, y) => x.gap - y.gap);
  }
  // The yoga (one of these names) formed by exactly these planets.
  const CONJ_YOGAS = ['Budha-Aditya', 'Chandra-Mangala', 'Guru-Chandal', 'Grahan', 'Angarak', 'Punarphoo'];
  const yogaOf = (c, ps, names) => ((c.yoga_check || {}).yogas || []).find(y => names.some(n => y.name.startsWith(n)) &&
    y.planets.length === ps.length && ps.every(p => y.planets.includes(p)));
  const toYogas = name => ` <button type="button" class="lnkyoga">${esc(name)} in Yogas →</button>`;

  // {key: html or null, rows: [{cls, html}]} for the plain-English list under the chart.
  window.linkReading = function (c, mode, focus, nodes) {
    const show = p => !focus || p === focus, rows = [];
    let key = null;
    if (mode === 'place') {
      const l1 = LORD[c.lagna.sign_index], l9 = LORD[(c.lagna.sign_index + 8) % 12], l10 = LORD[(c.lagna.sign_index + 9) % 12];
      if (!focus) key = `Your Lagna lord ${l1} sits in your ${ord(houseOf(c, l1))} house: your path runs through ${SHORT[houseOf(c, l1)]}.`;
      if (l9 !== l10 && houseOf(c, l9) === houseOf(c, l10) && (show(l9) || show(l10))) {
        const y = yogaOf(c, [l9, l10], ['Dharma-Karmadhipati']);
        key = (focus ? '' : key + ' ') + `Your 9th and 10th lords (${l9} and ${l10}) sit together in your ${ord(houseOf(c, l9))}` +
          (y ? `: this is your ${esc(y.name)} yoga.${toYogas(y.name)}` : '.');
      }
      ORDER.filter(show).forEach(p => {
        const r = rulesOf(c, p), h = houseOf(c, p);
        if (!r.length) return;
        rows.push({ cls: nature(c, p), html: r.length === 1 && r[0] === h
          ? `<b>${p}</b> rules your ${ord(h)} house and sits in it, in its own sign: ${SHORT[h]} are well supported.`
          : `<b>${p}</b>${p === l1 ? ' (your Lagna lord)' : ''} rules your ${join(r.map(ord))} and sits in your ${ord(h)}: ` +
            `${r.map(x => SHORT[x]).join('; ')} are tied to ${SHORT[h]}.` });
      });
      if (show('Rahu') || show('Ketu'))
        rows.push({ cls: 'mix', html: `<b>Rahu and Ketu</b> rule no sign. Each acts for the lord of the sign it sits in: ` +
          `Rahu for ${LORD[c.grahas.Rahu.sign_index]}, Ketu for ${LORD[c.grahas.Ketu.sign_index]}.` });
    } else if (mode === 'asp') {
      const got = {};
      ORDER.forEach(p => linkAspects(c, p, nodes).forEach(t => (got[t] = got[t] || []).push(p)));
      if (!focus) {
        const top = Object.entries(got).filter(([, ps]) => ps.length > 1).sort((x, y) => y[1].length - x[1].length).slice(0, 2);
        if (top.length) key = 'Where looks meet: ' + top.map(([h, ps]) => `your ${ord(+h)} house (${SHORT[h]}) gets looks from ${join(ps)}`).join('; ') + '.';
      }
      ORDER.filter(show).forEach(p => {
        const t = linkAspects(c, p, nodes);
        rows.push({ cls: nature(c, p), html: `<b>${p}</b> looks at your ${join(t.map(ord))}: ${t.map(h => SHORT[h]).join('; ')}.` });
      });
    } else if (mode === 'conj') {
      const all = pairs(c), ps = all.filter(x => show(x.a) || show(x.b)), close = all.filter(x => x.gap <= 5);
      if (!focus) key = close.length ? `Close pairs (within 5°) act most strongly together: ${close.map(x => `${x.a}–${x.b} ${x.gap}°`).join(', ')}.`
        : 'No planets sit within 5° of each other, so the links below are wide and gentle.';
      ps.forEach(x => {
        let s = `<b>${x.a} and ${x.b}</b>, ${x.gap}° apart (${x.gap <= 5 ? 'close' : 'wide'}): ${ADDS[x.a]} meets ${ADDS[x.b]}.`;
        const other = x.a === 'Sun' ? x.b : x.b === 'Sun' ? x.a : null;
        if (other && c.grahas[other].combust) s += ` ${other} is combust, inside the Sun's glare.`;
        const y = yogaOf(c, [x.a, x.b], CONJ_YOGAS);
        if (y) s += ` This pair forms your ${esc(y.name)} yoga.${toYogas(y.name)}`;
        rows.push({ cls: x.gap <= 5 ? 'good' : '', html: s });
      });
      const alone = ORDER.filter(p => show(p) && !all.some(x => x.a === p || x.b === p));
      if (alone.length) rows.push({ cls: '', html: `${join(alone.map(p => `<b>${p}</b>`))} ${alone.length > 1 ? 'sit' : 'sits'} alone in ${alone.length > 1 ? 'their signs' : 'its sign'}.` });
    }
    return { key, rows };
  };

  // Draw the links on the main chart svg. Glyph centres come from the drawn planet labels; arrows bend away from the
  // middle so they do not cross it. Without a focus planet all links show faintly.
  window.drawLinks = function (svg, c, mode, focus, nodes) {
    if (!svg) return;
    svg.querySelectorAll('.lk').forEach(e => e.remove());
    svg.classList.toggle('lkfocus', !!(mode && focus));
    svg.querySelectorAll('.pg').forEach(t => t.classList.toggle('lkon', t.dataset.p === focus));
    if (!mode) return;
    const NS = 'http://www.w3.org/2000/svg';
    let defs = svg.querySelector('defs') || svg.insertBefore(document.createElementNS(NS, 'defs'), svg.firstChild);
    if (!svg.querySelector('#lk-good')) defs.insertAdjacentHTML('beforeend', ['good', 'bad', 'mix'].map(k =>
      `<marker id="lk-${k}" viewBox="0 0 10 10" refX="7" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse"><path d="M0 0L10 5L0 10z" class="lkhead ${k}"/></marker>`).join(''));
    const CENTRE = centres(svg);
    const sn = [...svg.querySelectorAll('text.sn')].map(t => [+t.getAttribute('x'), +t.getAttribute('y') - 4]);
    const pos = p => {
      const t = svg.querySelector(`.pg[data-p="${p}"]`);
      try { const b = t.getBBox(); if (b.width) return [b.x + b.width / 2, b.y + b.height / 2]; } catch (e) { /* not drawn yet */ }
      return CENTRE[houseOf(c, p) - 1];
    };
    const curve = (a, b) => {
      const dx = b[0] - a[0], dy = b[1] - a[1], L = Math.hypot(dx, dy) || 1, mx = (a[0] + b[0]) / 2, my = (a[1] + b[1]) / 2;
      let nx = -dy / L, ny = dx / L;
      if ((mx + nx - 200) ** 2 + (my + ny - 200) ** 2 < (mx - 200) ** 2 + (my - 200) ** 2) { nx = -nx; ny = -ny; }
      const cx = Math.min(396, Math.max(4, mx + nx * L * .22)), cy = Math.min(396, Math.max(4, my + ny * L * .22));
      const pull = (p, d) => { const vx = cx - p[0], vy = cy - p[1], l = Math.hypot(vx, vy) || 1; return [p[0] + vx / l * d, p[1] + vy / l * d]; };
      const s = pull(a, 10), e = pull(b, 12), f = n => n.toFixed(1);
      return `M${f(s[0])} ${f(s[1])}Q${f(cx)} ${f(cy)} ${f(e[0])} ${f(e[1])}`;
    };
    const show = p => !focus || p === focus, faint = focus ? '' : ' faint';
    const arrows = [], under = [];
    if (mode === 'place') ORDER.filter(show).forEach(p => rulesOf(c, p).forEach(h => {
      if (h === houseOf(c, p)) under.push(`<circle class="lkown" cx="${sn[h - 1][0]}" cy="${sn[h - 1][1]}" r="9"/>`);
      else arrows.push(`<path class="lkarr ${nature(c, p)}${faint}" d="${curve(sn[h - 1], pos(p))}" marker-end="url(#lk-${nature(c, p)})"/>`);
    }));
    if (mode === 'asp') ORDER.filter(show).forEach(p => linkAspects(c, p, nodes).forEach(t =>
      arrows.push(`<path class="lkarr dash ${nature(c, p)}${faint}" d="${curve(pos(p), sn[t - 1])}" marker-end="url(#lk-${nature(c, p)})"/>`)));
    if (mode === 'conj') pairs(c).filter(x => show(x.a) || show(x.b)).forEach(x => {
      const [a, b] = [pos(x.a), pos(x.b)];
      under.push(`<line class="lkbond ${x.gap <= 5 ? 'close' : 'wide'}" x1="${a[0]}" y1="${a[1]}" x2="${b[0]}" y2="${b[1]}"/>`);
    });
    const g1 = document.createElementNS(NS, 'g'), g2 = document.createElementNS(NS, 'g');
    g1.setAttribute('class', 'lk'); g2.setAttribute('class', 'lk');
    g1.innerHTML = under.join(''); g2.innerHTML = arrows.join('');
    svg.insertBefore(g1, svg.querySelector('text.sn'));   // bonds and rings sit under the labels
    svg.appendChild(g2);
  };

  window.renderHouseReading = function (el, c, h) {
    if (h == null) { el.hidden = true; el.innerHTML = ''; return; }
    const r = window.houseFocusReading(c, h);
    el.hidden = false;
    el.innerHTML = `<div class="hrhead"><div><small>Your ${ord(h)} house · ${esc(r.sign)}</small><h3>${esc(r.covers[0].toUpperCase() + r.covers.slice(1))}</h3></div>
        <span class="badge ${r.verdict[0]}">${r.verdict[1]}</span><button type="button" class="hrclose" aria-label="Close">×</button></div>
      <ul class="hrlist">${r.lines.map(x => `<li>${esc(x)}</li>`).join('')}</ul>
      ${r.aspects.length ? `<div class="hrkey"><span><i class="good"></i>supportive aspect</span><span><i class="bad"></i>challenging aspect</span></div>` : ''}
      <button type="button" class="btn ghost" data-hask="1">Ask Astropositivism about this house →</button>
      <form class="hrq" autocomplete="off"><label for="hrq-in">Or ask Astropositivism your own question about this house</label>
        <div><input id="hrq-in" maxlength="400" placeholder="e.g. Will I save more money this year?"><button type="submit" class="btn">Send</button></div></form>`;
    el.querySelector('[data-hask]').onclick = () => window.askSukh && window.askSukh(r.ask);
    // A detailed question of the person's own, sent with this house's facts so Astropositivism answers about the right house.
    el.querySelector('.hrq').onsubmit = e => {
      e.preventDefault();
      const q = el.querySelector('#hrq-in').value.trim();
      if (!q || !window.askSukh) return;
      window.askSukh(`About my ${ord(h)} house (${r.sign}, ${SHORT[h]}; its lord ${r.lord} is in my ${ord(r.lordHouse)} house` +
        (r.inside.length ? `; ${r.inside.join(', ')} in it` : '') + `): ${q}`);
    };
    el.querySelector('.hrclose').onclick = () => window.selectHouse && window.selectHouse(null);
  };
})();
