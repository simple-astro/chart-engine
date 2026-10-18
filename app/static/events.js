// Life events: "Your life so far" on Kundli › About you. People add what happened and when; we check each against the chart.
(function () {
  const esc = s => String(s ?? '').replace(/[&<>"]/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));
  const COMMON = ['married', 'child', 'job', 'promotion', 'job_change', 'home', 'abroad', 'degree'];
  const MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
  const FIT = { fits: ['good', 'Fits'], partly: ['', 'Partly'], no: ['warn', 'Doesn’t fit'], noted: ['', 'Noted'] };
  let S = {}, EL = null;

  window.renderEvents = async function (el, pid) {
    EL = el; S = { pid, data: null, adding: false, kind: null, more: false, open: null, err: '', busy: false, bt: null, btConfirm: false };
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
    const kinds = S.data.kinds, shown = S.more ? kinds : kinds.filter(k => COMMON.includes(k.key));
    const y = new Date().getFullYear();
    return `<div class="evform">
      <h5>What happened?</h5>
      <div class="mdchips">${shown.map(k => `<button type="button" class="mdchip${S.kind === k.key ? ' on' : ''}" data-kind="${k.key}" aria-pressed="${S.kind === k.key}">${esc(k.label)}</button>`).join('')}
        ${S.more ? '' : '<button type="button" class="mdchip evmore" id="evmore">More…</button>'}</div>
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
  function birthTime() {
    const b = S.bt;
    if (!b) return '<button type="button" class="linkbtn evbt" id="evbt">Birth time rectification →</button>';
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
        : `<button type="button" class="btn ghost" id="btuse">Use ${t12(b.suggest)}</button>`) : ''}
      <button type="button" class="linkbtn" id="bthide">Hide rectification</button>
    </div>`;
  }
  async function loadBirthTime() {
    S.bt = { loading: true }; paint();
    try {
      const r = await fetch(`/profiles/${S.pid}/events/birth-time`), d = await r.json();
      if (!r.ok) throw new Error(d.detail || r.statusText);
      S.bt = d;
    } catch (e) { S.bt = { err: 'Couldn’t run the rectification: ' + e.message }; }
    paint();
  }
  async function useTime() {
    const tob = S.bt.suggest + ':00';
    try {
      const p = await (await fetch(`/profiles/${S.pid}`)).json();
      const r = await fetch(`/profiles/${S.pid}`, { method: 'PUT', headers: { 'content-type': 'application/json' }, body: JSON.stringify({ ...p.request, tob }) });
      const d = await r.json();
      if (!r.ok) throw new Error(d.detail || r.statusText);
      if (window.loadProfile) await window.loadProfile(S.pid);
    } catch (e) { S.bt = { ...S.bt, err: 'Couldn’t change the time: ' + e.message }; S.btConfirm = false; paint(); }
  }

  function paint() {
    const d = S.data, s = d.summary;
    EL.innerHTML = `<h3>Your life so far</h3>
      <p class="gsub">Add things that happened in your life. We check each one against your chart — the more you add, the better we know your chart.</p>
      ${d.accuracy && window.accCard ? window.accCard(d.accuracy) : ''}
      ${s && s.events < 3 ? `<p class="hint evhint">Add ${3 - s.events} more to see how well your chart explains your life.</p>` : ''}
      ${s && s.events >= 3 ? `<div class="evsum"><b>${s.fits}<small> of ${s.events}</small></b><div><p>${esc(s.text)}</p>${s.note ? `<small>${esc(s.note)}</small>` : ''}</div></div>` : ''}
      ${s && s.events >= 3 ? birthTime() : ''}
      ${d.events.length ? `<ul class="evlist">${d.events.map(e => {
        const f = FIT[e.check.fit], open = S.open === e.id;
        return `<li><button type="button" class="evrow" data-open="${e.id}" aria-expanded="${open}">
            <span class="evwhen">${esc(when(e))}</span><span class="evlab">${esc(e.label)}</span><span class="badge ${f[0]}">${f[1]}</span></button>
          ${open ? `<div class="evwhy"><p>${esc(e.check.why || '')}${e.check.rough ? ' Only the year is known, so this is a rough check.' : ''}</p>
            <button type="button" class="linkbtn" data-del="${e.id}">Remove this event</button></div>` : ''}</li>`;
      }).join('')}</ul>` : ''}
      ${S.adding ? form() : `<button type="button" class="btn ghost evadd" id="evadd">+ Add a past event</button>`}`;
  }

  document.addEventListener('click', async e => {
    if (!EL || !EL.contains(e.target)) return;
    const t = e.target.closest('button');
    if (!t) return;
    const keep = () => ({ y: (EL.querySelector('#evy') || {}).value, m: (EL.querySelector('#evm') || {}).value, d: (EL.querySelector('#evd') || {}).value });
    const restore = v => { if (!v) return; ['y', 'm', 'd'].forEach(k => { const f = EL.querySelector('#ev' + k); if (f) f.value = v[k] || ''; }); };
    if (t.id === 'evbt') { loadBirthTime(); return; }
    if (t.id === 'bthide') { S.bt = null; S.btConfirm = false; paint(); return; }
    if (t.id === 'btuse') { S.btConfirm = true; paint(); return; }
    if (t.id === 'btno') { S.btConfirm = false; paint(); return; }
    if (t.id === 'btyes') { t.disabled = true; useTime(); return; }
    if (t.id === 'evadd') { S.adding = true; S.err = ''; paint(); EL.querySelector('[data-kind]').focus(); }
    else if (t.id === 'evcancel') { Object.assign(S, { adding: false, kind: null, more: false, err: '' }); paint(); }
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
