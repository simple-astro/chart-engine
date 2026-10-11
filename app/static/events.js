// Life events: "Your life so far" on My Life. People add what happened and when; we check each against the chart.
(function () {
  const esc = s => String(s ?? '').replace(/[&<>"]/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));
  const COMMON = ['married', 'child', 'job', 'promotion', 'job_change', 'home', 'abroad', 'degree'];
  const MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
  const FIT = { fits: ['good', 'Fits'], partly: ['', 'Partly'], no: ['warn', 'Doesn’t fit'] };
  let S = {}, EL = null;

  window.renderEvents = async function (el, pid) {
    EL = el; S = { pid, data: null, adding: false, kind: null, more: false, open: null, err: '', busy: false };
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

  function paint() {
    const d = S.data, s = d.summary;
    EL.innerHTML = `<h3>Your life so far</h3>
      <p class="gsub">Add things that happened in your life. We check each one against your chart — the more you add, the better we know your chart.</p>
      ${s && s.events < 3 ? `<p class="hint evhint">Add ${3 - s.events} more to see how well your chart explains your life.</p>` : ''}
      ${s && s.events >= 3 ? `<div class="evsum"><b>${s.fits}<small> of ${s.events}</small></b><div><p>${esc(s.text)}</p>${s.note ? `<small>${esc(s.note)}</small>` : ''}</div></div>` : ''}
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
    if (t.id === 'evadd') { S.adding = true; S.err = ''; paint(); EL.querySelector('[data-kind]').focus(); }
    else if (t.id === 'evcancel') { Object.assign(S, { adding: false, kind: null, more: false, err: '' }); paint(); }
    else if (t.id === 'evmore') { const v = keep(); S.more = true; paint(); restore(v); }
    else if (t.dataset.kind) { const v = keep(); S.kind = t.dataset.kind; paint(); restore(v); }
    else if (t.dataset.open) { S.open = S.open === +t.dataset.open ? null : +t.dataset.open; paint(); }
    else if (t.dataset.del) {
      const r = await fetch(`/profiles/${S.pid}/events/${t.dataset.del}`, { method: 'DELETE' });
      if (r.ok) { S.data = await r.json(); S.open = null; paint(); }
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
        Object.assign(S, { data: d, adding: false, kind: null, more: false, busy: false });
        paint();
      } catch (err) { S.busy = false; S.err = err.message; paint(); restore(v); }
    }
  });
})();
