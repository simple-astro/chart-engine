// Pancha Pakshi (Today) and the Sarvatobhadra chakra (Timing): money days, the chakra and the market reading.
(function () {
  const esc = s => String(s ?? '').replace(/[&<>"]/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));
  const post = (u, b) => fetch(u, { method: 'POST', headers: { 'content-type': 'application/json' }, body: JSON.stringify(b) })
    .then(async r => { const d = await r.json(); if (!r.ok) throw new Error(window.apiErr(d.detail) || r.statusText); return d; });
  const hm = (iso, tz) => new Date(iso).toLocaleTimeString([], { hour: 'numeric', minute: '2-digit', timeZone: tz });
  const span = (a, b, tz) => `${hm(a, tz)} – ${hm(b, tz)}`;
  const dayName = (iso, opt) => new Date(iso + 'T12:00').toLocaleDateString([], opt || { weekday: 'short', day: 'numeric', month: 'short' });
  const tzToday = tz => new Intl.DateTimeFormat('en-CA', { timeZone: tz, year: 'numeric', month: '2-digit', day: '2-digit' }).format(new Date());
  const BIRD_ICON = { Vulture: '🦅', Owl: '🦉', Crow: '🐦‍⬛', Cock: '🐓', Peacock: '🦚' };
  const RATE = { best: ['Best', 'good'], good: ['Good', 'good'], fair: ['Middling', ''], avoid: ['Wait', 'warn'] };
  const ACT_RATE = { Ruling: 'best', Eating: 'good', Walking: 'fair', Sleeping: 'avoid', Dying: 'avoid' };

  // ---------- Pancha Pakshi ----------
  let P = {};
  window.renderPakshi = async function (el, o) {
    P = { el, o, date: P.o && P.o.birth === o.birth ? P.date : null, open: null, data: null };
    el.hidden = false;
    if (!P.data) el.innerHTML = '<h3>Panch Pakshi</h3><div class="hint">Finding your bird…</div>';
    await loadPakshi();
  };
  async function loadPakshi() {
    const { el, o } = P, tz = o.loc.tz_name, day = P.date || tzToday(tz);
    try {
      const d = await post('/panchapakshi', { birth: o.birth, date: day, days: 1, lat: o.loc.lat, lon: o.loc.lon, tz_name: tz });
      if (P.el !== el) return;
      P.data = d; P.date = day; paintPakshi();
    } catch (e) { el.innerHTML = `<h3>Panch Pakshi</h3><div class="hint err">Couldn’t work out the Pakshi times: ${esc(e.message)}</div>`; }
  }
  function paintPakshi() {
    const d = P.data, tz = d.tz_name, plan = d.days[0], today = P.date === tzToday(tz);
    const now = today && d.now;
    const nowLine = now ? `<p class="pk-now"><span class="badge ${RATE[now.rating][1]}">${RATE[now.rating][0]}</span>
        Right now your ${esc(d.bird)} is <b>${esc(now.activity.toLowerCase())}</b> (${esc(now.sub.toLowerCase())} part) — ${esc(d.meaning[now.activity])}.
        <small>Until ${hm(now.until, tz)}</small></p>` : '';
    const best = plan.best.length ? `<div class="pk-best">${plan.best.map(b => `<span><b>${span(b.start, b.end, tz)}</b>${esc(b.main)} · ${esc(b.activity)}</span>`).join('')}</div>`
      : '<p class="hint">No doubly strong window on this day — use a Ruling or Eating yama below.</p>';
    const yama = (y, i) => {
      const r = ACT_RATE[y.activity], open = P.open === i;
      return `<li class="pk-y${open ? ' open' : ''}"><button type="button" data-pky="${i}" aria-expanded="${open}">
          <span class="pk-t">${span(y.start, y.end, tz)}</span><span class="badge ${RATE[r][1]}">${esc(y.activity)}</span><i class="chev" aria-hidden="true"></i></button>
        ${open ? `<ul class="pk-subs">${y.subs.map(s => `<li><span>${span(s.start, s.end, tz)}</span><span>${esc(s.activity)} <small>(${esc(s.bird)})</small></span><span class="badge ${RATE[s.rating][1]}">${RATE[s.rating][0]}</span></li>`).join('')}</ul>` : ''}</li>`;
    };
    P.el.innerHTML = `<h3>Panch Pakshi <small>${BIRD_ICON[d.bird] || ''} your bird: ${esc(d.bird)}</small></h3>
      ${nowLine}
      <div class="pk-head"><h4>${today ? 'Strongest times today' : 'Strongest times'}</h4>
        <label class="pk-date">Date <input type="date" id="pkdate" value="${P.date}"></label></div>
      ${best}
      <p class="hint">${esc(plan.weekday)} · ${esc(plan.paksha)} paksha. Tap a yama to see its five parts.</p>
      <div class="pk-cols"><div><h5>Day</h5><ol class="pk-ys">${plan.yamas.slice(0, 5).map((y, i) => yama(y, i)).join('')}</ol></div>
        <div><h5>Night</h5><ol class="pk-ys">${plan.yamas.slice(5).map((y, i) => yama(y, i + 5)).join('')}</ol></div></div>
      <p class="hint">Your bird comes from your birth Moon’s nakshatra (${esc(d.birth_nakshatra)}) in ${esc(d.birth_paksha)} paksha. Ruling and Eating are strong times to begin things; Walking is middling; Sleeping and Dying are times to wait. Times for ${esc(P.o.place)}.</p>`;
  }
  document.addEventListener('click', e => {
    const b = e.target.closest('[data-pky]'); if (!b || !P.el || !P.el.contains(b)) return;
    const i = +b.dataset.pky; P.open = P.open === i ? null : i; paintPakshi();
  });
  document.addEventListener('change', e => {
    if (e.target.id !== 'pkdate' || !e.target.value) return;
    P.date = e.target.value; P.open = null; loadPakshi();
  });

  // ---------- Sarvatobhadra ----------
  let S = {};
  const VERDICT = { good: ['Good for money moves', 'good'], mixed: ['Mixed', ''], careful: ['Go carefully', 'warn'] };
  const SIGNAL = { teji: ['Teji · rise', 'warn'], mandi: ['Mandi · fall', 'good'], mixed: ['Mixed', ''], quiet: ['Quiet', ''] };
  window.renderSbc = async function (el, o) {
    if (S.el === el && S.o && S.o.birth === o.birth && S.o.tz === o.tz && S.data) return;
    S = { el, o, view: S.view || 'money', data: null, market: null };
    el.innerHTML = '<h3>Sarvatobhadra Chakra</h3><div class="hint">Reading the chakra…</div>';
    try {
      const start = tzToday(o.tz);
      const [d, m] = await Promise.all([post('/sarvatobhadra', { birth: o.birth, start, days: 14, tz_name: o.tz }),
        fetch(`/sarvatobhadra/market?on=${start}&tz_name=${encodeURIComponent(o.tz)}`).then(async r => { const j = await r.json(); if (!r.ok) throw new Error(window.apiErr(j.detail) || r.statusText); return j; })]);
      if (S.el !== el) return;
      S.data = d; S.market = m; paintSbc();
    } catch (e) { el.innerHTML = `<h3>Sarvatobhadra Chakra</h3><div class="hint err">Couldn’t read the chakra: ${esc(e.message)}</div>`; }
  };
  const why = w => `${w.planet}${w.retrograde ? ' (R)' : ''} ${w.nature === 'benefic' ? 'supports' : 'presses on'} your ${w.point.replace(/ \(.*/, '').toLowerCase()}`;
  function moneyView() {
    return `<p class="hint">The slow planets set the background on your money points — your birth star and your 2nd (wealth) and 11th (gains) house signs — for weeks at a time. The Moon crosses a nakshatra a day and decides each day: supportive while waxing, pressing while waning. Benefics: Mercury, Jupiter, Venus; malefics: Sun, Mars, Saturn, Rahu, Ketu.</p>
      <ul class="sb-days">${S.data.money_days.map(d => {
        const v = VERDICT[d.verdict], seen = new Set(), top = d.why.filter(w => { const k = why(w); if (seen.has(k)) return false; seen.add(k); return true; }).slice(0, 3);
        return `<li><div class="sb-d"><b>${esc(dayName(d.date))}</b><span class="badge ${v[1]}">${v[0]}</span></div>
          <small>${top.length ? top.map(w => esc(why(w))).join(' · ') : 'No strikes on your money points'}</small></li>`;
      }).join('')}</ul>`;
  }
  function cell(c, mine) {
    const shade = mine ? c.marks.length : c.kind === 'n';  // colour only the boxes this view is about
    const ben = shade && c.strikes.some(s => s.nature === 'benefic'), mal = shade && c.strikes.some(s => s.nature === 'malefic');
    const cls = ['sb-c', 'k-' + c.kind, ben && mal ? 'both' : ben ? 'ben' : mal ? 'mal' : '', c.marks.length ? 'mark' : ''].join(' ');
    const title = [c.label, ...c.marks.map(m => 'Your ' + m.toLowerCase()), ...c.strikes.map(s => `${s.planet} (${s.nature}, ${s.line})`)].join('\n');
    return `<div class="${cls}" title="${esc(title)}"><span>${esc(c.label.replace(/ \(.*\)/, ''))}</span>${c.planets.length ? `<b>${esc(c.planets.join(' '))}</b>` : ''}</div>`;
  }
  function chakraView(grid, mine) {
    return `<div class="sb-grid" role="img" aria-label="Sarvatobhadra chakra for today">${grid.flat().map(c => cell(c, mine)).join('')}</div>
      <div class="sb-key"><span class="ben">Benefic strike</span><span class="mal">Malefic strike</span><span class="both">Both</span>${mine ? '<span class="mark">Your birth points</span>' : ''}</div>
      <p class="hint">North at the top. Each planet strikes straight across the grid and along both diagonals from its nakshatra; ${mine ? 'only your birth points are coloured' : 'only the nakshatras are coloured'}. Hover or long-press a box for every strike on it.</p>`;
  }
  function marketView() {
    const m = S.market;
    return `<p class="hint">Traditional teji-mandi reading for ${esc(dayName(m.date, { weekday: 'long', day: 'numeric', month: 'long' }))}: a malefic strike on a nakshatra is read as prices rising for the goods it rules, a benefic strike as prices falling.</p>
      ${m.has_goods ? '' : '<p class="hint">Your astrologer hasn’t linked goods to the nakshatras yet, so only the signals are shown.</p>'}
      <table class="sb-mkt"><thead><tr><th>Nakshatra</th><th>Reading</th><th>Struck by</th>${m.has_goods ? '<th>Goods</th>' : ''}</tr></thead><tbody>
      ${m.rows.filter(r => r.signal !== 'quiet').map(r => `<tr><td>${esc(r.nakshatra)}</td><td><span class="badge ${SIGNAL[r.signal][1]}">${SIGNAL[r.signal][0]}</span></td>
        <td>${esc([...r.malefic, ...r.benefic].join(', '))}</td>${m.has_goods ? `<td>${esc(r.goods || '—')}</td>` : ''}</tr>`).join('')}</tbody></table>
      <p class="hint"><b>Not investment advice.</b> This is a traditional astrological reading, not a market forecast; don’t trade on it.</p>`;
  }
  function paintSbc() {
    const tabs = [['money', 'Money days'], ['chakra', 'My chakra'], ['market', 'Market']];
    S.el.innerHTML = `<h3>Sarvatobhadra Chakra <small>financial astrology</small></h3>
      <div class="seg setseg sb-seg" role="tablist">${tabs.map(([k, t]) => `<button type="button" role="tab" data-sbv="${k}" aria-selected="${S.view === k}" class="${S.view === k ? 'on' : ''}">${t}</button>`).join('')}</div>
      <div class="sb-body">${S.view === 'money' ? moneyView() : S.view === 'chakra' ? chakraView(S.data.grid, true) : marketView() + chakraView(S.market.grid, false)}</div>`;
  }
  document.addEventListener('click', e => {
    const b = e.target.closest('[data-sbv]'); if (!b || !S.el || !S.el.contains(b)) return;
    S.view = b.dataset.sbv; paintSbc();
  });
})();
