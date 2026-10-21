// Life graph (My Charts › Graphs): when is my best time for a life matter? Promise, Dasha and transit lanes, the best
// windows, and (looking back) the person's own events. Data: /profiles/{id}/graph/life (the same engine as Coming up).
(function () {
  const esc = s => String(s ?? '').replace(/[&<>"]/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));
  const MON = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
  const day = iso => new Date(iso + 'T12:00:00Z').getTime() / 864e5;
  const fmt = iso => { const d = new Date(iso + 'T12:00:00Z'); return `${MON[d.getUTCMonth()]} ${d.getUTCFullYear()}`; };
  const fmtD = iso => { const d = new Date(iso + 'T12:00:00Z'); return `${d.getUTCDate()} ${MON[d.getUTCMonth()]} ${d.getUTCFullYear()}`; };
  const AB = { Sun: 'Su', Moon: 'Mo', Mars: 'Ma', Mercury: 'Me', Jupiter: 'Ju', Venus: 'Ve', Saturn: 'Sa', Rahu: 'Ra', Ketu: 'Ke' };
  const WORD = { strong: 'Strong', favourable: 'Good', mixed: 'Mixed', challenging: 'Challenging' };
  const PROMISE = { promised: ['good', 'Promised'], 'promised with obstacles': ['mid', 'Promised, with obstacles'], 'not clearly promised': ['low', 'Not clearly promised'] };
  const PROMISE_RISK = { indicated: ['care', 'Shown in the chart'], possible: ['steady', 'Mildly shown'], 'not strongly indicated': ['go', 'Not strongly shown'] };
  // Traffic-light tones from the engine's verdict. Red (hold) only for a double-hard period: a hard Dasha period while
  // Jupiter and Saturn line up the same way. Risk topics flip: a strong period there means more risk.
  const SYM = { go: '✓', good: '✓', steady: '~', care: '!', hold: '!!' };
  const TONE_WORD = { event: { go: 'Go', good: 'Good', steady: 'Steady', care: 'Take care', hold: 'Hold off' },
    risk: { go: 'Low risk', good: 'Mostly safe', steady: 'Watch', care: 'Take care', hold: 'High risk' } };
  const ADVICE = {
    event: { go: 'A strong time to act: apply, ask, begin.', good: 'Good for steady moves and follow-ups.', steady: 'Keep going steadily; big moves can wait for green.',
      care: 'Slower going: prepare rather than push.', hold: 'Hold big decisions; use this time to plan and build up.' },
    risk: { go: 'A safe stretch for this. Keep your usual routine.', good: 'Mostly calm. Keep regular care.', steady: 'Keep an eye on it; nothing to worry about.',
      care: 'Take more care in this stretch.', hold: 'The most sensitive stretch: take extra care and act early.' } };
  const LEVEL = { go: 4, good: 3, steady: 2, care: 1, hold: 0 };
  const tl = k => `<span class="tl tl-${k}" aria-hidden="true">${SYM[k]}</span>`;
  let S = { pid: null, topic: 'career', ahead: 24, back: 0, data: null, sel: null, err: '' };
  let EL = null;

  window.renderLifeGraph = async function (el, pid) {
    EL = el;
    if (pid == null) { el.innerHTML = '<div class="hint">Save this chart to see its life graph.</div>'; return; }
    if (S.pid !== pid) S = { pid, topic: S.topic, ahead: S.ahead, back: S.back, data: null, sel: null, err: '' };
    if (S.data && S.data.loadedFor === `${S.topic}|${S.ahead}|${S.back}`) { paint(); return; }
    await load();
  };

  async function load() {
    const key = `${S.topic}|${S.ahead}|${S.back}`, pid = S.pid;
    EL.innerHTML = '<div class="hint">Drawing your life graph…</div>';
    try {
      const r = await fetch(`/profiles/${pid}/graph/life?topic=${S.topic}&ahead=${S.ahead}&back=${S.back}`), d = await r.json();
      if (!r.ok) throw new Error(window.apiErr ? window.apiErr(d.detail) : d.detail || r.statusText);
      if (S.pid !== pid || key !== `${S.topic}|${S.ahead}|${S.back}`) return;
      d.loadedFor = key; S.data = d; S.err = '';
      S.sel = d.windows.findIndex(w => w.starts <= d.today && d.today < w.ends);
      if (S.sel < 0) S.sel = 0;
      paint();
    } catch (e) { S.err = e.message; EL.innerHTML = `<div class="hint err">Couldn’t draw the life graph: ${esc(e.message)}</div>`; }
  }

  // Jupiter/Saturn over a period: the months inside it, else the month nearest its middle.
  function transitSum(d, w) {
    const inside = d.transit.filter(m => w.starts <= m.date && m.date < w.ends);
    if (inside.length) return inside.reduce((s, m) => s + m.score, 0);
    const mid = (day(w.starts) + day(w.ends)) / 2;
    const near = d.transit.reduce((a, m) => !a || Math.abs(day(m.date) - mid) < Math.abs(day(a.date) - mid) ? m : a, null);
    return near ? near.score : 0;
  }
  function tone(d, w) {
    const ts = transitSum(d, w);
    if (d.kind === 'risk') return { strong: ts > 0.2 ? 'hold' : 'care', favourable: 'steady', mixed: 'good', challenging: 'go' }[w.verdict] || 'steady';
    return { strong: 'go', favourable: 'good', mixed: 'steady', challenging: ts < -0.2 ? 'hold' : 'care' }[w.verdict] || 'steady';
  }

  function scale(d) {
    const sc = d.windows.map(w => w.score), lo = Math.min(...sc), hi = Math.max(...sc), span = hi - lo || 1;
    return { t: w => (w.score - lo) / span, flat: hi - lo < 0.5 };
  }

  function svg(d, W) {
    const L = 64, R = 8, X0 = L, PW = Math.max(200, W - L - R);
    const t0 = day(d.from), t1 = day(d.to), x = iso => X0 + (Math.max(t0, Math.min(t1, day(iso))) - t0) / (t1 - t0) * PW;
    const nowX = x(d.today), risk = d.kind === 'risk', tones = d.windows.map(w => tone(d, w));
    const lanes = { head: 14, axis: 34, promise: 40, dasha: 70, transit: 112, overall: 142, events: 0 };
    const hasEv = d.events.length > 0;
    const oh = 52, evY = lanes.overall + oh + 10, H = (hasEv ? evY + 22 : lanes.overall + oh + 8);
    const best = risk ? '' : d.best.map(([a, b]) => `<rect x="${x(a)}" y="26" width="${Math.max(2, x(b) - x(a))}" height="${H - 30}" fill="var(--acc)" opacity=".12"/>`).join('');
    const sep = [];
    // Mahadasha · Antardasha labels along the top
    let run = null;
    d.windows.forEach(w => { const k = `${AB[w.maha]}/${AB[w.antar]}`; if (run && run.k === k) run.e = w.ends; else { run = { k, s: w.starts, e: w.ends }; sep.push(run); } });
    const head = sep.map(r => { const a = x(r.s), b = x(r.e); return b - a > 26 ? `<text x="${(a + b) / 2}" y="${lanes.head}" text-anchor="middle" font-size="10" fill="var(--mut)">${r.k}</text><line x1="${a}" x2="${a}" y1="2" y2="22" stroke="var(--line)"/>` : ''; }).join('');
    // month axis: a tick every 3, 6 or 12 months depending on the range, the year at January
    const months = (t1 - t0) / 30.44, every = [3, 6, 12].find(k => k * PW / months >= 46) || 12;
    let axis = '';
    for (let m = new Date(d.from + 'T12:00:00Z'), n = 0; day(m.toISOString().slice(0, 10)) <= t1; m = new Date(Date.UTC(m.getUTCFullYear(), m.getUTCMonth() + 1, 1, 12)), n++) {
      const iso = m.toISOString().slice(0, 10), mo = m.getUTCMonth(), px = x(iso);
      if (mo % every === 0) axis += `<line x1="${px}" x2="${px}" y1="${lanes.axis - 8}" y2="${H - 6}" stroke="var(--line)" opacity="${mo === 0 ? 1 : .45}"/><text x="${px + 2}" y="${lanes.axis}" font-size="9.5" fill="var(--mut)">${every === 12 ? m.getUTCFullYear() : MON[mo] + (mo === 0 ? ' ' + String(m.getUTCFullYear()).slice(2) : '')}</text>`;
    }
    const p = d.promise, pk = (risk ? PROMISE_RISK : { promised: ['go'], 'promised with obstacles': ['steady'], 'not clearly promised': ['care'] })[p.verdict] || ['steady'];
    const pv = PROMISE[p.verdict] || ['low', p.verdict], plabel = risk ? (PROMISE_RISK[p.verdict] || [0, p.verdict])[1] : pv[1];
    const promise = `<rect x="${X0}" y="${lanes.promise}" width="${PW}" height="22" rx="6" fill="var(--tl-${pk[0]})"/>
      <text x="${X0 + 8}" y="${lanes.promise + 15}" font-size="11" font-weight="600" fill="var(--tl-${pk[0]}-on)">${SYM[pk[0]]} ${esc(plabel)} · ${p.cusp}th cusp sub lord ${esc(p.cusp_sub_lord)}</text>`;
    const words = TONE_WORD[d.kind] || TONE_WORD.event;
    const blocks = d.windows.map((w, i) => {
      const a = x(w.starts), b = x(w.ends), on = i === S.sel, k = tones[i], wd = b - a;
      const label = wd > 30 ? `${SYM[k]} ${AB[w.praty]}` : wd > 12 ? SYM[k] : '';
      return `<g class="lgblk" data-i="${i}" role="button" tabindex="0" aria-label="${esc(`${w.maha}, ${w.antar}, ${w.praty} period, ${fmt(w.starts)} to ${fmt(w.ends)}: ${words[k]}`)}">
        <rect x="${a + .5}" y="${lanes.dasha}" width="${Math.max(2, wd - 1)}" height="30" rx="5" fill="${k === 'hold' ? 'url(#lghatch)' : `var(--tl-${k})`}" stroke="${on ? 'var(--ink)' : 'none'}" stroke-width="2"/>
        ${label ? `<text x="${(a + b) / 2}" y="${lanes.dasha + 19}" text-anchor="middle" font-size="10" font-weight="700" fill="var(--tl-${k}-on)">${label}</text>` : ''}</g>`;
    }).join('');
    const dots = d.transit.map(m => {
      const px = x(m.date), r = 2 + Math.min(4, Math.abs(m.score) * 5);
      return m.score > 0 ? `<circle cx="${px}" cy="${lanes.transit + 10}" r="${r}" fill="var(--tl-${risk ? 'care' : 'go'})"><title>${esc(fmt(m.date))}: ${esc(m.notes.join('; ') || (risk ? 'adds to it' : 'helps'))}</title></circle>`
        : m.score < 0 ? `<circle cx="${px}" cy="${lanes.transit + 10}" r="${r}" fill="none" stroke="var(--tl-${risk ? 'go' : 'hold'})" stroke-width="1.8"><title>${esc(fmt(m.date))}: ${esc(m.notes.join('; '))}</title></circle>`
        : `<circle cx="${px}" cy="${lanes.transit + 10}" r="2" fill="none" stroke="var(--mut)"><title>${esc(fmt(m.date))}: quiet</title></circle>`;
    }).join('');
    // Overall: the tone level as a step line over easier (green), middle (yellow) and harder (orange) bands.
    const yO = lv => lanes.overall + oh - 6 - lv / 4 * (oh - 12);
    let pts = '';
    d.windows.forEach((w, i) => { const y = yO(LEVEL[tones[i]]); pts += `${x(w.starts)},${y} ${x(w.ends)},${y} `; });
    const band = (y0, h, k) => `<rect x="${X0}" y="${y0}" width="${PW}" height="${h}" fill="var(--tl-${k})" opacity=".16"/>`;
    const top = lanes.overall, h3 = oh / 3;
    const overall = `${band(top, h3, 'go')}${band(top + h3, h3, 'steady')}${band(top + 2 * h3, h3, 'care')}
      <text x="${X0 + PW - 4}" y="${top + 10}" text-anchor="end" font-size="9" fill="var(--mut)">${risk ? 'Safer' : 'Easier'}</text>
      <text x="${X0 + PW - 4}" y="${top + oh - 3}" text-anchor="end" font-size="9" fill="var(--mut)">${risk ? 'More risk' : 'Harder'}</text>
      <polyline points="${pts.trim()}" fill="none" stroke="var(--ink)" stroke-width="2" stroke-linejoin="round"/>`;
    const evs = d.events.map(e => `<g><title>${esc(e.label)} · ${esc(fmt(e.date))} · ${e.fit === 'fits' ? 'fell in a supportive period' : e.fit === 'partly' ? 'partly' : 'not in a supportive period'}</title>
      <path d="M${x(e.date)} ${evY + 3} l6 7 l-6 7 l-6 -7z" fill="${e.fit === 'fits' ? 'var(--ok)' : e.fit === 'partly' ? 'color-mix(in srgb, var(--ok) 40%, transparent)' : 'none'}" stroke="${e.fit === 'no' ? 'var(--bad)' : 'var(--ok)'}" stroke-width="1.6"/></g>`).join('');
    const label = (y, t) => `<text x="2" y="${y}" font-size="10.5" fill="var(--mut)">${t}</text>`;
    return `<svg viewBox="0 0 ${W} ${H}" width="${W}" height="${H}" role="img" aria-label="Life graph for ${esc(d.title)}: promise, Dasha periods coloured from go to hold off, and Jupiter and Saturn transits">
      <defs><pattern id="lghatch" width="8" height="8" patternUnits="userSpaceOnUse" patternTransform="rotate(45)"><rect width="8" height="8" fill="var(--tl-hold)"/><rect width="3" height="8" fill="var(--tl-hold2)"/></pattern></defs>
      ${best}${head}${axis}${label(lanes.promise + 15, 'Promise')}${promise}${label(lanes.dasha + 19, 'Dasha')}${blocks}${label(lanes.transit + 14, 'Transit')}${dots}${label(lanes.overall + 28, 'Overall')}${overall}
      ${hasEv ? label(evY + 15, 'My events') + evs : ''}
      <line x1="${nowX}" x2="${nowX}" y1="22" y2="${H - 4}" stroke="var(--ink)" stroke-dasharray="3 3"/><text x="${nowX}" y="12" text-anchor="middle" font-size="9.5" font-weight="700" fill="var(--ink)">Today</text>
    </svg>`;
  }

  function detail(d) {
    const w = d.windows[S.sel]; if (!w) return '';
    const sc = scale(d), t = sc.t(w), k = tone(d, w), kind = d.kind === 'risk' ? 'risk' : 'event';
    const rank = t >= .75 ? 'one of your strongest periods' : t >= .4 ? 'a middle period' : 'quieter than your best periods';
    const reasons = w.reasons.map(r => `<li>${esc(r.replace(/^(\w+) (\w+): planet ([\d,]+), nakshatra (\w+) ([\d,]+), sub (\w+) ([\d,]+) → (.*)$/, (m, a, b, c, dd, e, f, g, h) => `${a} ${b}: its sub lord ${f} points to houses ${g.replace(/,/g, ' ')} — ${h}`))}</li>`).join('');
    const tn = w.transit.map(n => `<li>${esc(n.replace(' (negating)', ' (works against it)').replace(' (part of the combination)', ' (helps)'))}</li>`).join('');
    return `<div class="lgcard"><div class="lgtone">${tl(k)}<b>${TONE_WORD[kind][k]} · ${esc(w.maha)} › ${esc(w.antar)} › ${esc(w.praty)}</b></div>
      <small>${esc(fmtD(w.starts))} – ${esc(fmtD(w.ends))}</small>
      <small>${ADVICE[kind][k]}</small>
      <small>The period lords: <b>${WORD[w.verdict]}</b> · Overall, with the transits and the significator: ${sc.flat ? 'all your periods are alike for this matter' : rank}</small>
      <ul>${reasons}</ul>${tn ? `<h6>Transits</h6><ul>${tn}</ul>` : ''}</div>`;
  }

  function paint() {
    const d = S.data; if (!d) return;
    const W = Math.max(300, Math.floor((EL.clientWidth || 340) - 2));
    const chip = t => `<button type="button" class="mdchip${t.key === S.topic ? ' on' : ''}" data-topic="${t.key}" aria-pressed="${t.key === S.topic}">${esc(t.label)}</button>`;
    const chips = d.topics.filter(t => t.kind !== 'risk').map(chip).join('') + `<span class="lgrisk">Risks</span>` + d.topics.filter(t => t.kind === 'risk').map(chip).join('');
    const risk = d.kind === 'risk', kind = risk ? 'risk' : 'event', words = TONE_WORD[kind], tones = d.windows.map(w => tone(d, w));
    let best;
    if (risk) {  // the stretches to take care in, neighbours of the same tone joined
      const care = [];
      d.windows.forEach((w, i) => { const k = tones[i]; if ((k !== 'hold' && k !== 'care') || w.ends <= d.today) return;
        const last = care[care.length - 1]; if (last && last.b === w.starts && last.k === k) last.b = w.ends; else care.push({ a: w.starts, b: w.ends, k }); });
      best = care.length ? care.slice(0, 4).map(c => `<li>${tl(c.k)}<span><b>${esc(fmt(c.a))} – ${esc(fmt(c.b))}</b> · ${words[c.k]}</span></li>`).join('') : '<li>No sensitive stretch ahead in this range.</li>';
    } else {
      const ahead = [...d.best_ahead].sort((x, y) => x[0] < y[0] ? -1 : 1);
      best = ahead.length ? ahead.map(([a, b]) => `<li>${tl('go')}<b>${esc(fmt(a))} – ${esc(fmt(b))}</b></li>`).join('') : '<li>No clearly supportive window ahead in this range. Try looking further ahead.</li>';
    }
    const ci = d.windows.findIndex(w => w.starts <= d.today && d.today < w.ends), ck = ci >= 0 ? tones[ci] : null;
    const next = ci >= 0 ? d.windows.findIndex((w, i) => i > ci && (risk ? tones[i] === 'hold' || tones[i] === 'care' : tones[i] === 'go') && tones[i] !== ck) : -1;
    const now = ck ? `<p class="lgnow">${tl(ck)}<span>Right now: <b>${words[ck].toLowerCase()}</b> until ${esc(fmt(d.windows[ci].ends))}.${next > 0 ? ` Next: <b>${risk ? words[tones[next]].toLowerCase() : 'green'}</b> from ${esc(fmt(d.windows[next].starts))}.` : ''}</span></p>` : '';
    const legend = ['go', 'good', 'steady', 'care', 'hold'].map(k => `<span>${tl(k)}${words[k]}</span>`).join('');
    EL.innerHTML = `<div class="lg">
      <div class="lgchips" role="group" aria-label="Life matter">${chips}</div>
      <div class="lgctl"><label>Look ahead <select id="lgahead">${[12, 24, 36, 60].map(m => `<option value="${m}"${S.ahead === m ? ' selected' : ''}>${m} months</option>`).join('')}</select></label>
        <label>Look back <select id="lgback">${[[0, 'No'], [36, '3 years'], [60, '5 years'], [120, '10 years']].map(([m, t]) => `<option value="${m}"${S.back === m ? ' selected' : ''}>${t}</option>`).join('')}</select></label></div>
      ${now}<p class="lgtitle"><b>${esc(d.title)}</b> · houses ${d.houses_for.join(', ')}${d.significators.length ? ' · significator ' + esc(d.significators.join(', ')) : ''}</p>
      <div class="lgsvg">${svg(d, W)}</div>
      <div class="lgkey">${legend}<span><i class="lgk lgk-tr" style="background:var(--tl-${risk ? 'care' : 'go'})"></i>Jupiter or Saturn ${risk ? 'adds to it' : 'helps'}</span><span><i class="lgk lgk-against" style="border-color:var(--tl-${risk ? 'go' : 'hold'})"></i>${risk ? 'eases it' : 'works against it'}</span>${risk ? '' : '<span><i class="lgk lgk-band"></i>Best window</span>'}${d.events.length ? '<span><i class="lgk lgk-ev"></i>Your own events (filled = fell in a supportive period)</span>' : ''}</div>
      <div class="lgbest"><h5>${risk ? 'Take extra care' : 'Your best windows ahead'}</h5><ul>${best}</ul>
        <button type="button" class="btn ghost" data-ask="${risk ? `When should I take extra care about ${esc(d.title.toLowerCase())} in my chart?` : `When is the best time for ${esc(d.title.toLowerCase())} in my chart?`}">Ask Astropositivism →</button></div>
      <p class="hint">Tap a period to see why. Colours follow the engine’s verdict for each period${risk ? '; for a risk, green means low risk' : ''}. Red only when a hard period and Jupiter or Saturn line up the same way. These are tendencies, not promises.</p>
      ${detail(d)}</div>`;
  }

  document.addEventListener('click', e => {
    if (!EL || !EL.contains(e.target)) return;
    const c = e.target.closest('[data-topic]'); if (c) { S.topic = c.dataset.topic; S.data = null; load(); return; }
    const b = e.target.closest('.lgblk'); if (b) { S.sel = +b.dataset.i; paint(); }
  });
  document.addEventListener('keydown', e => {
    if (!EL || !EL.contains(e.target) || (e.key !== 'Enter' && e.key !== ' ')) return;
    const b = e.target.closest('.lgblk'); if (b) { e.preventDefault(); S.sel = +b.dataset.i; paint(); }
  });
  document.addEventListener('change', e => {
    if (!EL || !EL.contains(e.target)) return;
    if (e.target.id === 'lgahead') { S.ahead = +e.target.value; S.data = null; load(); }
    if (e.target.id === 'lgback') { S.back = +e.target.value; S.data = null; load(); }
  });
  let rz; addEventListener('resize', () => { clearTimeout(rz); rz = setTimeout(() => { if (EL && EL.offsetParent && S.data) paint(); }, 150); });
})();
