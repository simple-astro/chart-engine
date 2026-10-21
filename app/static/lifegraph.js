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

  function scale(d) {
    const sc = d.windows.map(w => w.score), lo = Math.min(...sc), hi = Math.max(...sc), span = hi - lo || 1;
    return { t: w => (w.score - lo) / span, flat: hi - lo < 0.5 };
  }
  const shade = t => `color-mix(in srgb, var(--acc) ${Math.round(16 + 74 * t)}%, transparent)`;

  function svg(d, W) {
    const L = 64, R = 8, X0 = L, PW = Math.max(200, W - L - R);
    const t0 = day(d.from), t1 = day(d.to), x = iso => X0 + (Math.max(t0, Math.min(t1, day(iso))) - t0) / (t1 - t0) * PW;
    const sc = scale(d), nowX = x(d.today);
    const lanes = { head: 14, axis: 34, promise: 40, dasha: 70, transit: 112, overall: 142, events: 0 };
    const hasEv = d.events.length > 0;
    const oh = 52, evY = lanes.overall + oh + 10, H = (hasEv ? evY + 22 : lanes.overall + oh + 8);
    const best = d.best.map(([a, b]) => `<rect x="${x(a)}" y="26" width="${Math.max(2, x(b) - x(a))}" height="${H - 30}" fill="var(--acc)" opacity=".12"/>`).join('');
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
    const p = d.promise, pv = PROMISE[p.verdict] || ['low', p.verdict];
    const promise = `<rect x="${X0}" y="${lanes.promise}" width="${PW}" height="22" rx="6" fill="${pv[0] === 'good' ? 'var(--acc)' : pv[0] === 'mid' ? 'color-mix(in srgb, var(--acc) 45%, transparent)' : 'var(--soft)'}" ${pv[0] === 'low' ? 'stroke="var(--line)"' : ''}/>
      <text x="${X0 + 8}" y="${lanes.promise + 15}" font-size="11" fill="${pv[0] === 'good' ? 'var(--onacc)' : 'var(--ink)'}">${esc(pv[1])} · ${p.cusp}th cusp sub lord ${esc(p.cusp_sub_lord)}</text>`;
    const blocks = d.windows.map((w, i) => {
      const a = x(w.starts), b = x(w.ends), on = i === S.sel;
      return `<g class="lgblk" data-i="${i}" role="button" tabindex="0" aria-label="${esc(`${w.maha}, ${w.antar}, ${w.praty} period, ${fmt(w.starts)} to ${fmt(w.ends)}: ${WORD[w.verdict]}`)}">
        <rect x="${a + .5}" y="${lanes.dasha}" width="${Math.max(2, b - a - 1)}" height="30" rx="5" fill="${shade(sc.t(w))}" stroke="${on ? 'var(--ink)' : 'none'}" stroke-width="1.6"/>
        ${b - a > 22 ? `<text x="${(a + b) / 2}" y="${lanes.dasha + 19}" text-anchor="middle" font-size="10" fill="var(--ink)">${AB[w.praty]}</text>` : ''}</g>`;
    }).join('');
    const dots = d.transit.map(m => {
      const px = x(m.date), r = 2 + Math.min(4, Math.abs(m.score) * 5);
      return m.score > 0 ? `<circle cx="${px}" cy="${lanes.transit + 10}" r="${r}" fill="var(--acc)"><title>${esc(fmt(m.date))}: ${esc(m.notes.join('; ') || 'helps')}</title></circle>`
        : m.score < 0 ? `<circle cx="${px}" cy="${lanes.transit + 10}" r="${r}" fill="none" stroke="var(--bad)" stroke-width="1.5"><title>${esc(fmt(m.date))}: ${esc(m.notes.join('; '))}</title></circle>`
        : `<circle cx="${px}" cy="${lanes.transit + 10}" r="2" fill="none" stroke="var(--mut)"><title>${esc(fmt(m.date))}: quiet</title></circle>`;
    }).join('');
    const yO = t => lanes.overall + oh - 4 - t * (oh - 12);
    let pts = '';
    d.windows.forEach(w => { const y = yO(sc.t(w)); pts += `${x(w.starts)},${y} ${x(w.ends)},${y} `; });
    const overall = `<polyline points="${pts.trim()}" fill="none" stroke="var(--acc)" stroke-width="2" stroke-linejoin="round"/>
      <line x1="${X0}" x2="${X0 + PW}" y1="${lanes.overall + oh - 2}" y2="${lanes.overall + oh - 2}" stroke="var(--line)"/>`;
    const evs = d.events.map(e => `<g><title>${esc(e.label)} · ${esc(fmt(e.date))} · ${e.fit === 'fits' ? 'fell in a supportive period' : e.fit === 'partly' ? 'partly' : 'not in a supportive period'}</title>
      <path d="M${x(e.date)} ${evY + 3} l6 7 l-6 7 l-6 -7z" fill="${e.fit === 'fits' ? 'var(--ok)' : e.fit === 'partly' ? 'color-mix(in srgb, var(--ok) 40%, transparent)' : 'none'}" stroke="${e.fit === 'no' ? 'var(--bad)' : 'var(--ok)'}" stroke-width="1.6"/></g>`).join('');
    const label = (y, t) => `<text x="2" y="${y}" font-size="10.5" fill="var(--mut)">${t}</text>`;
    return `<svg viewBox="0 0 ${W} ${H}" width="${W}" height="${H}" role="img" aria-label="Life graph for ${esc(d.title)}: promise, Dasha periods and Jupiter and Saturn transits, with the best windows shaded">
      ${best}${head}${axis}${label(lanes.promise + 15, 'Promise')}${promise}${label(lanes.dasha + 19, 'Dasha')}${blocks}${label(lanes.transit + 14, 'Transit')}${dots}${label(lanes.overall + 28, 'Overall')}${overall}
      ${hasEv ? label(evY + 15, 'My events') + evs : ''}
      <line x1="${nowX}" x2="${nowX}" y1="22" y2="${H - 4}" stroke="var(--ink)" stroke-dasharray="3 3"/><text x="${nowX}" y="12" text-anchor="middle" font-size="9.5" font-weight="700" fill="var(--ink)">Today</text>
    </svg>`;
  }

  function detail(d) {
    const w = d.windows[S.sel]; if (!w) return '';
    const sc = scale(d), t = sc.t(w);
    const rank = t >= .75 ? 'one of your strongest periods' : t >= .4 ? 'a middle period' : 'quieter than your best periods';
    const reasons = w.reasons.map(r => `<li>${esc(r.replace(/^(\w+) (\w+): planet ([\d,]+), nakshatra (\w+) ([\d,]+), sub (\w+) ([\d,]+) → (.*)$/, (m, a, b, c, dd, e, f, g, h) => `${a} ${b}: its sub lord ${f} points to houses ${g.replace(/,/g, ' ')} — ${h}`))}</li>`).join('');
    const tn = w.transit.map(n => `<li>${esc(n.replace(' (negating)', ' (works against it)').replace(' (part of the combination)', ' (helps)'))}</li>`).join('');
    return `<div class="lgcard"><b>${esc(w.maha)} › ${esc(w.antar)} › ${esc(w.praty)}</b>
      <small>${esc(fmtD(w.starts))} – ${esc(fmtD(w.ends))}</small>
      <small>The period lords: <b>${WORD[w.verdict]}</b> · Overall, with the transits and the significator: ${sc.flat ? 'all your periods are alike for this matter' : rank}</small>
      <ul>${reasons}</ul>${tn ? `<h6>Transits</h6><ul>${tn}</ul>` : ''}</div>`;
  }

  function paint() {
    const d = S.data; if (!d) return;
    const W = Math.max(300, Math.floor((EL.clientWidth || 340) - 2));
    const chips = d.topics.map(t => `<button type="button" class="mdchip${t.key === S.topic ? ' on' : ''}" data-topic="${t.key}" aria-pressed="${t.key === S.topic}">${esc(t.label)}</button>`).join('');
    const ahead = [...d.best_ahead].sort((x, y) => x[0] < y[0] ? -1 : 1);
    const best = ahead.length ? ahead.map(([a, b]) => `<li><b>${esc(fmt(a))} – ${esc(fmt(b))}</b></li>`).join('') : '<li>No clearly supportive window ahead in this range. Try looking further ahead.</li>';
    EL.innerHTML = `<div class="lg">
      <div class="lgchips" role="group" aria-label="Life matter">${chips}</div>
      <div class="lgctl"><label>Look ahead <select id="lgahead">${[12, 24, 36, 60].map(m => `<option value="${m}"${S.ahead === m ? ' selected' : ''}>${m} months</option>`).join('')}</select></label>
        <label>Look back <select id="lgback">${[[0, 'No'], [36, '3 years'], [60, '5 years'], [120, '10 years']].map(([m, t]) => `<option value="${m}"${S.back === m ? ' selected' : ''}>${t}</option>`).join('')}</select></label></div>
      <p class="lgtitle"><b>${esc(d.title)}</b> · houses ${d.houses_for.join(', ')}${d.significators.length ? ' · significator ' + esc(d.significators.join(', ')) : ''}</p>
      <div class="lgsvg">${svg(d, W)}</div>
      <div class="lgkey"><span><i class="lgk lgk-dasha"></i>Stronger Dasha period</span><span><i class="lgk lgk-tr"></i>Jupiter or Saturn helps</span><span><i class="lgk lgk-against"></i>works against it</span><span><i class="lgk lgk-band"></i>Best window</span>${d.events.length ? '<span><i class="lgk lgk-ev"></i>Your own events (filled = fell in a supportive period)</span>' : ''}</div>
      <div class="lgbest"><h5>Your best windows ahead</h5><ul>${best}</ul>
        <button type="button" class="btn ghost" data-ask="When is the best time for ${esc(d.title.toLowerCase())} in my chart?">Ask Astropositivism →</button></div>
      <p class="hint">Tap a period to see why. Colours compare your periods with each other, so some are always brighter; the words in the detail are the engine’s own verdict. These are tendencies, not promises.</p>
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
