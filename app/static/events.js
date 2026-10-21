// Life events: "Your life so far" on Kundli › About you. People add what happened and when; we check each against the chart.
(function () {
  const esc = s => String(s ?? '').replace(/[&<>"]/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));
  const COMMON = ['married', 'child', 'job', 'promotion', 'job_change', 'home', 'abroad', 'degree'];
  const MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
  const FIT = { fits: ['good', 'Fits'], partly: ['', 'Partly'], no: ['warn', 'Doesn’t fit'], noted: ['', 'Noted'] };
  let S = {}, EL = null;

  window.renderEvents = async function (el, pid) {
    EL = el; S = { pid, data: null, adding: false, kind: null, more: false, open: null, err: '', busy: false, bt: null, btConfirm: false, btSel: null, method: 'kp', finder: null };
    if (pid == null) { el.innerHTML = '<h3>Your life so far</h3><p class="hint">Save this chart to add your life events.</p>'; return; }
    el.innerHTML = '<h3>Your life so far</h3><div class="hint">Loading…</div>';
    try {
      const r = await fetch(`/profiles/${pid}/events`), d = await r.json();
      if (!r.ok) throw new Error(d.detail || r.statusText);
      if (S.pid === pid) { S.data = d; paint(); }
    } catch (e) { el.innerHTML = `<h3>Your life so far</h3><p class="hint err">Couldn’t load your events: ${esc(e.message)}</p>`; }
  };

  const when = e => {
    const [y, m, d] = e.date.split('-').map(Number);
    return e.precision === 'year' ? String(y) : e.precision === 'month' ? `${MONTHS[m - 1]} ${y}` : `${d} ${MONTHS[m - 1]} ${y}`;
  };

  function form() {
    const kinds = S.data.kinds, y = new Date().getFullYear();
    const chip = k => `<button type="button" class="mdchip${S.kind === k.key ? ' on' : ''}" data-kind="${k.key}" aria-pressed="${S.kind === k.key}">${esc(k.label)}</button>`;
    // The common ones first; "More…" shows every kind in its group, with a search for long lists.
    const f = (S.find || '').trim().toLowerCase(), hit = k => !f || k.label.toLowerCase().includes(f);
    const groups = (S.data.groups || ['Other']).map(g => [g, kinds.filter(k => (k.group || 'Other') === g && hit(k))]).filter(([, ks]) => ks.length);
    const picker = S.more
      ? `<input id="evfind" class="evfind" type="search" placeholder="Search, e.g. trip, money, school" value="${esc(S.find || '')}" aria-label="Search events">
         ${groups.length ? groups.map(([g, ks]) => `<h6 class="evgrp">${esc(g)}</h6><div class="mdchips">${ks.map(chip).join('')}</div>`).join('') : '<p class="hint">No match. Try another word.</p>'}`
      : `<div class="mdchips">${kinds.filter(k => COMMON.includes(k.key)).map(chip).join('')}<button type="button" class="mdchip evmore" id="evmore">More…</button></div>`;
    return `<div class="evform">
      <h5>What happened?</h5>
      ${picker}
      <h5>When?</h5>
      <div class="evdate">
        <div><label for="evy">Year</label><input id="evy" type="number" inputmode="numeric" min="1900" max="${y}" placeholder="${y - 5}"></div>
        <div><label for="evm">Month <span class="opt">if you know</span></label><select id="evm"><option value="">—</option>${MONTHS.map((m, i) => `<option value="${i + 1}">${m}</option>`).join('')}</select></div>
        <div><label for="evd">Day <span class="opt">if you know</span></label><select id="evd"><option value="">—</option>${Array.from({ length: 31 }, (_, i) => `<option>${i + 1}</option>`).join('')}</select></div>
      </div>
      <div class="mdgo"><button type="button" class="btn" id="evsave"${S.busy ? ' disabled' : ''}>${S.busy ? 'Checking…' : 'Add'}</button><button type="button" class="btn ghost" id="evcancel">Cancel</button>${S.err ? `<span class="hint err">${esc(S.err)}</span>` : ''}</div>
      <p class="hint">The exact month makes the check much better. A year alone is only a rough check.</p>
    </div>`;
  }

  // Birth time rectification: the same events judged against birth times an hour either side of the saved one.
  const t12 = t => { const [h, m] = t.split(':').map(Number); return `${(h + 11) % 12 + 1}:${String(m).padStart(2, '0')} ${h < 12 ? 'AM' : 'PM'}`; };
  const AYN = { lahiri: 'Lahiri', pushya: 'Pushya', raman: 'Raman', fagan: 'Fagan-Bradley', tropical: 'Tropical' };
  const PARTS = [['any', 'I don’t know'], ['night', 'Night · 12–6 AM'], ['morning', 'Morning · 6 AM–12 PM'], ['afternoon', 'Afternoon · 12–6 PM'], ['evening', 'Evening · 6 PM–12 AM']];
  const mins = t => { const [h, m] = t.split(':').map(Number); return h * 60 + m; };
  const hhmm = n => `${String(Math.floor(n / 60)).padStart(2, '0')}:${String(n % 60).padStart(2, '0')}`;
  const SIGN_SHORT = x => x;
  // The searched day as a strip: each 15-minute cell is as tall as the most events fitting at any time inside it.
  function dayStrip(b) {
    const cells = {}; b.rows.forEach(r => { const k = Math.floor(mins(r.tob) / 15); cells[k] = Math.max(cells[k] || 0, r.fits); });
    const [lo, hi] = b.window;
    return `<div class="btstrip" role="img" aria-label="How many of your events fit at each time of day">${Object.keys(cells).map(k => {
      const t = +k * 15, inWin = t + 14 >= mins(lo) && t <= mins(hi) && cells[k] === b.best;
      return `<i class="${inWin ? 'best' : ''}" style="height:${Math.max(4, Math.round(cells[k] / b.events * 100))}%" title="${t12(hhmm(t))}: ${cells[k]} of ${b.events}"></i>`;
    }).join('')}</div><div class="btaxis"><span>${t12(b.rows[0].tob)}</span><span>${t12(b.rows[Math.floor(b.rows.length / 2)].tob)}</span><span>${t12(b.rows[b.rows.length - 1].tob)}</span></div>`;
  }
  function dayResult(b) {
    const STR = { weak: ['', 'Only a hint'], some: ['', 'Useful hint'], good: ['good', 'Good sign'] }[b.strength];
    const confirm = S.btConfirm && S.btSel
      ? `<div class="btconfirm"><p>Set your birth time to about <b>${t12(S.btSel)}</b>${b.unknown ? '' : ` (now ${t12(S.data.saved_tob || '')})`}? Your chart, periods and readings will all update, and we will mark the time as a best fit, not a certainty. You can change it any time.</p>
          <button type="button" class="btn" id="btyes">Yes, use ${t12(S.btSel)}</button><button type="button" class="btn ghost" id="btno">Cancel</button></div>` : '';
    return `<div class="btbox">
      <div class="bthead"><h4>${b.unknown ? 'Finding your birth time' : 'Searching the whole day'}</h4><span class="badge ${STR[0]}">${STR[1]}</span></div>
      <p>${esc(b.text)}</p>
      <p class="hint">${esc(b.note)}</p>
      ${dayStrip(b)}
      ${b.windows.length && b.narrowing ? `<ul class="btwins">${b.windows.map(w => {
        const mid = hhmm(Math.floor((mins(w.from) + mins(w.to)) / 2));
        return `<li><div><b>${t12(w.from)}${w.from === w.to ? '' : ' – ' + t12(w.to)}</b><small>${esc(w.lagna.join(' → '))} lagna · ${w.fits} of ${b.events} events fit</small></div>
          ${b.narrowing ? `<button type="button" class="btn ghost" data-usewin="${mid}">Use ${t12(mid)}</button>` : ''}</li>`;
      }).join('')}</ul>` : ''}
      ${b.windows.length > 1 && b.narrowing ? '<p class="hint">More than one window fits equally. Pick the one that matches what you know (for example, whether it was day or night), or add more events with their month to separate them.</p>' : ''}
      ${confirm}
      <button type="button" class="linkbtn" id="bthide">Hide</button>
    </div>`;
  }
  function birthTime() {
    const b = S.bt;
    if (!b) return '<button type="button" class="linkbtn evbt" id="evbt">Birth time rectification →</button>';
    if (b.scope === 'day' && !b.loading && !b.err) return dayResult(b);
    if (b.loading) return '<div class="btbox"><p class="hint">Rectifying: checking your events against nearby birth times…</p></div>';
    if (b.err) return `<div class="btbox"><p class="hint err">${esc(b.err)}</p></div>`;
    const [lo, hi] = b.window, inWin = r => r.tob >= lo && r.tob <= hi && r.fits === b.best;
    const STR = { weak: ['', 'Only a hint'], some: ['', 'Useful hint'], good: ['good', 'Good sign'] }[b.strength];
    return `<div class="btbox">
      <div class="bthead"><h4>Birth time rectification</h4><span class="badge ${STR[0]}">${STR[1]}</span></div>
      <p>${esc(b.text)}</p>
      <p class="hint">${esc(b.note)}${b.ayanamsha !== 'krishnamurti' ? ` Worked out with the ${esc(AYN[b.ayanamsha] || b.ayanamsha)} ayanamsa, as your chart is set; KP can give a different answer.` : ''}</p>
      <ol class="btrows" aria-label="Events that fit at each birth time">${b.rows.map(r => `<li class="${r.yours ? 'yours' : ''}${inWin(r) ? ' best' : ''}">
          <span class="bttime">${t12(r.tob)}${r.yours ? ' <em>yours</em>' : ''}</span>
          <span class="btbar" aria-hidden="true"><i style="width:${Math.round(r.fits / b.events * 100)}%"></i></span>
          <span class="btn2">${r.fits}/${b.events}</span>
          <span class="btdots" aria-hidden="true">${r.marks.map((m, i) => `<i class="${m}" title="${esc(b.labels[i])}: ${m === 'fits' ? 'fits' : m === 'partly' ? 'partly' : 'doesn’t fit'}"></i>`).join('')}</span></li>`).join('')}</ol>
      <p class="hint">Each dot is one of your events, in order: ${b.labels.map(esc).join(' · ')}. Filled = fits.</p>
      ${b.suggest ? (S.btConfirm
        ? `<div class="btconfirm"><p>Change your saved birth time from <b>${t12(b.rows.find(r => r.yours).tob)}</b> to <b>${t12(b.suggest)}</b>? Your chart, periods and readings will all update. You can change it back any time.</p>
            <button type="button" class="btn" id="btyes">Yes, use ${t12(b.suggest)}</button><button type="button" class="btn ghost" id="btno">Cancel</button></div>`
        : `<button type="button" class="btn ghost" id="btuse" data-t="${b.suggest}">Use ${t12(b.suggest)}</button>`) : ''}
      <button type="button" class="linkbtn" id="evbtday">Not sure about the hour? Search the whole day →</button>
      <button type="button" class="linkbtn" id="bthide">Hide rectification</button>
    </div>`;
  }
  async function loadBirthTime(q) {
    S.bt = { loading: true, scope: 'hour' }; paint();
    try {
      const r = await fetch(`/profiles/${S.pid}/events/birth-time${q || ''}`), d = await r.json();
      if (!r.ok) throw new Error(d.detail || r.statusText);
      S.bt = d;
    } catch (e) { S.bt = { err: 'Couldn’t run the rectification: ' + e.message }; }
    paint();
  }
  async function useTime() {
    const tob = (S.btSel || S.bt.suggest) + ':00';
    try {
      const p = await (await fetch(`/profiles/${S.pid}`)).json();
      const r = await fetch(`/profiles/${S.pid}`, { method: 'PUT', headers: { 'content-type': 'application/json' }, body: JSON.stringify({ ...p.request, tob, tob_unknown: false }) });
      const d = await r.json();
      if (!r.ok) throw new Error(d.detail || r.statusText);
      if (window.loadProfile) await window.loadProfile(S.pid);
    } catch (e) { S.bt = { ...S.bt, err: 'Couldn’t change the time: ' + e.message }; S.btConfirm = false; paint(); }
  }

  // "Don't know your birth time?": five prompts for the events that move a chart most, then a search of the day.
  const FINDER = [['A relationship', ['married', 'engaged', 'separation', 'love']], ['Work', ['job', 'promotion', 'job_change', 'job_loss', 'business']],
    ['A move', ['moved', 'abroad', 'away', 'home']], ['A child', ['child']], ['Studies or health', ['school', 'degree', 'illness', 'accident']]];
  function finder() {
    const f = S.finder, y = new Date().getFullYear(), label = k => (S.data.kinds.find(x => x.key === k) || {}).label || k;
    if (!f) return `<div class="evfind0"><b>Don’t know your birth time?</b><p class="hint">Your life events can narrow it down. Tell us about 4 or 5 things that happened, with the month if you remember it.</p>
      <button type="button" class="btn" id="fdopen">Find my birth time</button></div>`;
    const row = ([title, kinds], i) => `<div class="fdrow" data-fd="${i}"><label>${title}</label>
      <select data-fdk="${i}" aria-label="${esc(title)}: what happened">${kinds.length > 1 ? '<option value="">—</option>' : ''}${kinds.map(k => `<option value="${k}"${(f.rows[i].kind || (kinds.length === 1 ? kinds[0] : '')) === k ? ' selected' : ''}>${esc(label(k))}</option>`).join('')}</select>
      <select data-fdm="${i}" aria-label="${esc(title)}: month"><option value="">Month?</option>${MONTHS.map((m, j) => `<option value="${j + 1}"${+f.rows[i].month === j + 1 ? ' selected' : ''}>${m}</option>`).join('')}</select>
      <input data-fdy="${i}" type="number" inputmode="numeric" min="1900" max="${y}" placeholder="Year" value="${esc(f.rows[i].year || '')}" aria-label="${esc(title)}: year"></div>`;
    return `<div class="evform finder"><h5>Find my birth time</h5>
      <p class="hint">Fill in at least 4 rows. Leave a row empty if it didn’t happen. The month makes the search much sharper.</p>
      ${FINDER.map(row).join('')}
      <h5>Do you know roughly when you were born?</h5>
      <select id="fdpart" aria-label="Part of the day">${PARTS.map(([v, t]) => `<option value="${v}"${f.part === v ? ' selected' : ''}>${t}</option>`).join('')}</select>
      <div class="mdgo"><button type="button" class="btn" id="fdgo"${f.busy ? ' disabled' : ''}>${f.busy ? 'Searching…' : 'Search the day'}</button><button type="button" class="btn ghost" id="fdcancel">Cancel</button>${f.err ? `<span class="hint err">${esc(f.err)}</span>` : ''}</div></div>`;
  }
  async function runFinder() {
    const f = S.finder, rows = f.rows.map((r, i) => ({ ...r, kind: r.kind || (FINDER[i][1].length === 1 ? FINDER[i][1][0] : '') })).filter(r => r.kind && r.year);
    const have = S.data.events.filter(e => e.check.fit !== 'noted').length;
    if (rows.length + have < 4) { f.err = `Add ${4 - rows.length - have} more (a row needs what happened and the year).`; paint(); return; }
    f.busy = true; f.err = ''; paint();
    try {
      for (const r of rows) {
        const res = await fetch(`/profiles/${S.pid}/events`, { method: 'POST', headers: { 'content-type': 'application/json' },
          body: JSON.stringify({ kind: r.kind, year: +r.year, month: r.month ? +r.month : null, day: null }) });
        const d = await res.json();
        if (!res.ok) throw new Error(Array.isArray(d.detail) ? d.detail.map(x => x.msg).join('; ') : d.detail || res.statusText);
        S.data = d;
      }
      const part = f.part;
      S.finder = null;
      await loadBirthTime(`?scope=day&part=${part}`);
      if (window.loadAccuracy) window.loadAccuracy(S.pid);
    } catch (e) { f.busy = false; f.err = e.message; paint(); }
  }

  // KP, Karaka (natural significators, draft rules) or where both agree: one method at a time.
  function methodSummary(d, s) {
    const K = d.karaka;
    if (S.method === 'kar' && K) return `<div class="evsum"><b>${K.fits}<small> of ${K.events}</small></b><div><p>Checked by natural karakas: ${K.fits} of your ${K.events} events fit. By chance, about ${Math.round(K.expected)} would.</p><small>${esc(K.note)}</small></div></div>`;
    if (S.method === 'both' && K) return `<div class="evsum"><b>${K.agree}<small> of ${K.events}</small></b><div><p>Both methods fit ${K.agree} of your events: ✓✓ both fit · ✓· KP only · ·✓ karaka only · ·· neither.</p><small>Events where both fit are the strongest checks of your birth time.</small></div></div>`;
    return `<div class="evsum"><b>${s.fits}<small> of ${s.events}</small></b><div><p>${esc(s.text)}</p>${s.note ? `<small>${esc(s.note)}</small>` : ''}</div></div>`;
  }

  function paint() {
    const d = S.data, s = d.summary;
    EL.innerHTML = `<h3>Your life so far</h3>
      <p class="gsub">Add things that happened in your life. We check each one against your chart — the more you add, the better we know your chart.</p>
      ${d.accuracy && window.accCard ? window.accCard(d.accuracy) : ''}
      ${d.tob_unknown ? (S.bt && S.bt.scope === 'day' ? birthTime() : finder()) : ''}
      ${s && s.events < 3 ? `<p class="hint evhint">Add ${3 - s.events} more to see how well your chart explains your life.</p>` : ''}
      ${s && s.events >= 3 && d.karaka ? `<div class="seg evmeth" role="radiogroup" aria-label="Check by">${[['kp', 'KP'], ['kar', 'Karaka'], ['both', 'Both agree']].map(([k, t]) =>
          `<button type="button" role="radio" data-meth="${k}" aria-checked="${S.method === k}" class="${S.method === k ? 'on' : ''}">${t}</button>`).join('')}</div>` : ''}
      ${s && s.events >= 3 ? methodSummary(d, s) : ''}
      ${s && s.events >= 3 && !d.tob_unknown ? birthTime() : ''}
      ${d.events.length ? `<ul class="evlist">${d.events.map(e => {
        const k = e.karaka || { fit: 'noted' }, f = FIT[S.method === 'kar' ? k.fit : e.check.fit], open = S.open === e.id;
        const mark = S.method === 'both' && e.check.fit !== 'noted'
          ? `<span class="evagree" title="KP ${FIT[e.check.fit][1]} · Karaka ${FIT[k.fit][1]}">${e.check.fit === 'fits' ? '✓' : '·'}${k.fit === 'fits' ? '✓' : '·'}</span>`
          : `<span class="badge ${f[0]}">${f[1]}</span>`;
        return `<li><button type="button" class="evrow" data-open="${e.id}" aria-expanded="${open}">
            <span class="evwhen">${esc(when(e))}</span><span class="evlab">${esc(e.label)}</span>${mark}</button>
          ${open ? `<div class="evwhy">${e.check.fit === 'noted' ? `<p>${esc(e.check.why || '')}</p>` :
            `<p><b>KP · ${FIT[e.check.fit][1]}:</b> ${esc(e.check.why || '')}${e.check.rough ? ' Only the year is known, so this is a rough check.' : ''}</p>
             ${k.why ? `<p><b>Karaka · ${FIT[k.fit][1]}:</b> ${esc(k.why)}</p>` : ''}`}
            <button type="button" class="linkbtn" data-del="${e.id}">Remove this event</button></div>` : ''}</li>`;
      }).join('')}</ul>` : ''}
      ${S.adding ? form() : `<button type="button" class="btn ghost evadd" id="evadd">+ Add a past event</button>`}`;
  }

  document.addEventListener('input', e => {
    if (!S.finder || !EL || !EL.contains(e.target)) return;
    const t = e.target, i = t.dataset.fdk ?? t.dataset.fdm ?? t.dataset.fdy;
    if (i !== undefined) { const r = S.finder.rows[+i], f = t.dataset.fdk !== undefined ? 'kind' : t.dataset.fdm !== undefined ? 'month' : 'year'; r[f] = t.value; }
    if (t.id === 'fdpart') S.finder.part = t.value;
  });
  document.addEventListener('change', e => {
    if (!S.finder || !EL || !EL.contains(e.target)) return;
    const t = e.target, i = t.dataset.fdk ?? t.dataset.fdm;
    if (i !== undefined) S.finder.rows[+i][t.dataset.fdk !== undefined ? 'kind' : 'month'] = t.value;
    if (t.id === 'fdpart') S.finder.part = t.value;
  });
  document.addEventListener('input', e => {
    if (e.target.id !== 'evfind' || !EL || !EL.contains(e.target)) return;
    const keep = { y: (EL.querySelector('#evy') || {}).value, m: (EL.querySelector('#evm') || {}).value, d: (EL.querySelector('#evd') || {}).value };
    S.find = e.target.value; paint();
    ['y', 'm', 'd'].forEach(k => { const x = EL.querySelector('#ev' + k); if (x) x.value = keep[k] || ''; });
    const f = EL.querySelector('#evfind'); if (f) { f.focus(); f.setSelectionRange(f.value.length, f.value.length); }
  });
  document.addEventListener('click', async e => {
    if (!EL || !EL.contains(e.target)) return;
    const t = e.target.closest('button');
    if (!t) return;
    const keep = () => ({ y: (EL.querySelector('#evy') || {}).value, m: (EL.querySelector('#evm') || {}).value, d: (EL.querySelector('#evd') || {}).value });
    const restore = v => { if (!v) return; ['y', 'm', 'd'].forEach(k => { const f = EL.querySelector('#ev' + k); if (f) f.value = v[k] || ''; }); };
    if (t.dataset.meth) { S.method = t.dataset.meth; paint(); return; }
    if (t.id === 'evbt') { loadBirthTime(); return; }
    if (t.id === 'evbtday') { loadBirthTime('?scope=day'); return; }
    if (t.id === 'fdopen') { S.finder = { rows: FINDER.map(() => ({})), part: 'any', busy: false, err: '' }; paint(); return; }
    if (t.id === 'fdcancel') { S.finder = null; paint(); return; }
    if (t.id === 'fdgo') { runFinder(); return; }
    if (t.dataset.usewin) { S.btSel = t.dataset.usewin; S.btConfirm = true; paint(); return; }
    if (t.id === 'bthide') { S.bt = null; S.btConfirm = false; S.btSel = null; paint(); return; }
    if (t.id === 'btuse') { S.btSel = t.dataset.t || S.bt.suggest; S.btConfirm = true; paint(); return; }
    if (t.id === 'btno') { S.btConfirm = false; paint(); return; }
    if (t.id === 'btyes') { t.disabled = true; useTime(); return; }
    if (t.id === 'evadd') { S.adding = true; S.err = ''; paint(); EL.querySelector('[data-kind]').focus(); }
    else if (t.id === 'evcancel') { Object.assign(S, { adding: false, kind: null, more: false, err: '', find: '' }); paint(); }
    else if (t.id === 'evmore') { const v = keep(); S.more = true; paint(); restore(v); }
    else if (t.dataset.kind) { const v = keep(); S.kind = t.dataset.kind; paint(); restore(v); }
    else if (t.dataset.open) { S.open = S.open === +t.dataset.open ? null : +t.dataset.open; paint(); }
    else if (t.dataset.del) {
      const r = await fetch(`/profiles/${S.pid}/events/${t.dataset.del}`, { method: 'DELETE' });
      if (r.ok) { S.data = await r.json(); S.open = null; S.bt = null; paint(); if (window.loadAccuracy) window.loadAccuracy(S.pid); }
    } else if (t.id === 'evsave') {
      const v = keep();
      if (!S.kind) { S.err = 'Choose what happened.'; paint(); restore(v); return; }
      if (!v.y) { S.err = 'Add the year.'; paint(); restore(v); return; }
      S.busy = true; S.err = ''; paint(); restore(v);
      try {
        const r = await fetch(`/profiles/${S.pid}/events`, { method: 'POST', headers: { 'content-type': 'application/json' },
          body: JSON.stringify({ kind: S.kind, year: +v.y, month: v.m ? +v.m : null, day: v.d ? +v.d : null }) });
        const d = await r.json();
        if (!r.ok) throw new Error(Array.isArray(d.detail) ? d.detail.map(x => x.msg).join('; ') : d.detail || r.statusText);
        Object.assign(S, { data: d, adding: false, kind: null, more: false, busy: false, bt: null, btConfirm: false });
        paint();
        if (window.loadAccuracy) window.loadAccuracy(S.pid);
      } catch (err) { S.busy = false; S.err = err.message; paint(); restore(v); }
    }
  });
})();
