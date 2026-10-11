// State of mind: a quick mood log under the Today card, Sukh's reply, and the person's own patterns.
(function () {
  const esc = s => String(s ?? '').replace(/[&<>"]/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));
  const tone = v => `color-mix(in srgb, var(--g2) ${Math.round((v + 3) / 6 * 100)}%, var(--acc2))`;
  const group = v => v < 0 ? 'unpleasant' : v > 0 ? 'pleasant' : 'neutral';
  const SCALE = ['Very unpleasant', 'Unpleasant', 'Slightly unpleasant', 'Neutral', 'Slightly pleasant', 'Pleasant', 'Very pleasant'];
  let S = {}, EL = null;

  const fresh = pid => ({ pid, opts: null, v: null, feelings: [], causes: [], scope: 'now', note: '', logs: [], share: false,
    reply: null, pat: null, showPat: false, busy: false, err: '' });

  window.renderMood = async function (el, pid) {
    EL = el; S = fresh(pid);
    if (pid == null) {
      el.innerHTML = '<h3>How are you feeling?</h3><p class="hint">Save this chart to keep a private mood log.</p>';
      return;
    }
    el.innerHTML = '<h3>How are you feeling?</h3><div class="hint">Loading…</div>';
    try {
      const r = await fetch(`/profiles/${pid}/mood?limit=60`), d = await r.json();
      if (!r.ok) throw new Error(d.detail || r.statusText);
      if (S.pid !== pid) return;
      Object.assign(S, { opts: d.options, logs: d.logs, share: d.share });
      paint();
    } catch (e) { el.innerHTML = `<h3>How are you feeling?</h3><p class="hint err">Couldn’t load your mood log: ${esc(e.message)}</p>`; }
  };

  function chips(list, chosen, kind) {
    return `<div class="mdchips">${list.map(x => `<button type="button" class="mdchip${chosen.includes(x) ? ' on' : ''}" data-${kind}="${esc(x)}" aria-pressed="${chosen.includes(x)}">${esc(x)}</button>`).join('')}</div>`;
  }

  // The last 14 days: one dot per day, coloured by that day's average mood.
  function strip() {
    if (!S.logs.length) return '';
    const by = {};
    S.logs.forEach(l => (by[l.local_date] = by[l.local_date] || []).push(l.valence));
    const days = [], t = new Date();
    for (let i = 13; i >= 0; i--) {
      const d = new Date(t.getFullYear(), t.getMonth(), t.getDate() - i);
      days.push(d.getFullYear() + '-' + String(d.getMonth() + 1).padStart(2, '0') + '-' + String(d.getDate()).padStart(2, '0'));
    }
    return `<div class="mdstrip" aria-label="Your mood over the last two weeks">${days.map(k => {
      const vs = by[k], a = vs && vs.reduce((x, y) => x + y, 0) / vs.length;
      const lab = new Date(k + 'T00:00').toLocaleDateString(undefined, { weekday: 'short', day: 'numeric' });
      return `<span title="${esc(lab)}${vs ? ': ' + SCALE[Math.round(a) + 3] + ' (' + vs.length + ' log' + (vs.length > 1 ? 's' : '') + ')' : ': no log'}">
        <i${vs ? ` style="background:${tone(a)}"` : ' class="none"'}></i><small>${lab.split(' ')[0].slice(0, 1)}</small></span>`;
    }).join('')}</div>`;
  }

  function form() {
    const v = S.v, o = S.opts;
    return `<div class="seg mdscope" role="radiogroup" aria-label="When"><button type="button" role="radio" data-scope="now" class="${S.scope === 'now' ? 'on' : ''}" aria-checked="${S.scope === 'now'}">Right now</button><button type="button" role="radio" data-scope="day" class="${S.scope === 'day' ? 'on' : ''}" aria-checked="${S.scope === 'day'}">Today overall</button></div>
      <div class="mdscale">
        <div class="mdorb" style="background:${v === null ? 'var(--line)' : tone(v)}"></div>
        <b class="mdval">${v === null ? 'Slide to choose' : SCALE[v + 3]}</b>
        <input type="range" id="mdv" min="-3" max="3" step="1" value="${v ?? 0}" aria-label="How you feel, from very unpleasant to very pleasant" aria-valuetext="${v === null ? 'Not chosen' : SCALE[v + 3]}">
        <div class="mdends"><span>Very unpleasant</span><span>Very pleasant</span></div>
      </div>
      ${v === null ? '' : `<h5>What describes this feeling?</h5>${chips(o.feelings[group(v)], S.feelings, 'f')}`}
      ${v === null || !S.feelings.length ? '' : `<h5>What’s having the biggest impact?</h5>${chips(o.causes, S.causes, 'c')}
        <details class="mdnote"${S.note ? ' open' : ''}><summary>Add a note</summary><textarea id="mdnote" rows="2" maxlength="500" placeholder="Only you can see this">${esc(S.note)}</textarea></details>`}
      <div class="mdgo"><button type="button" class="btn" id="mdsave"${v === null || S.busy ? ' disabled' : ''}>${S.busy ? 'Saving…' : 'Log my mood'}</button>${S.err ? `<span class="hint err">${esc(S.err)}</span>` : ''}</div>`;
  }

  function replyView() {
    const r = S.reply, l = S.logs[0];
    return `<div class="mdreply">
        <div class="mdhead"><div class="mdorb" style="background:${tone(l.valence)}"></div>
          <div><b>${esc(r.headline)}</b><small>${esc([l.feelings.join(', '), l.causes.join(', ')].filter(Boolean).join(' · ') || 'Logged')}</small></div></div>
        ${r.care ? `<div class="mdcare"><p>${esc(r.care.text)}</p><ul>${r.care.helplines.map(h => `<li>${esc(h.region)}: <b>${esc(h.name)}</b>${h.number ? ' — <b class="num">' + esc(h.number) + '</b>' : ''}</li>`).join('')}</ul></div>` : ''}
        ${r.sky ? `<p class="tsukh"><img src="/static/sun.svg" alt="" width="22" height="22"><span>${esc(r.sky)}</span></p>` : ''}
        <p>${esc(r.timing)}</p>
        <div class="tup"><small>Try this now · ${esc(r.do.planet)}</small><p>${esc(r.do.text)}.</p></div>
        <div class="mdgo"><button type="button" class="btn" id="mdask">Ask Sukh about this</button><button type="button" class="btn ghost" id="mdagain">Log again</button></div>
      </div>`;
  }

  function patView() {
    if (!S.showPat) return '';
    const p = S.pat;
    if (!p) return '<div class="mdpat"><div class="hint">Looking for patterns…</div></div>';
    if (!p.ready) return `<div class="mdpat"><p>Log ${p.needed} more time${p.needed > 1 ? 's' : ''} to see your patterns — they need ${p.logs + p.needed} logs.</p>
      <div class="mdprog"><i style="width:${Math.round(p.logs / (p.logs + p.needed) * 100)}%"></i></div>
      <p class="hint">Log on different kinds of days — good and hard ones — so the comparison is fair.</p></div>`;
    return `<div class="mdpat">
      ${p.found.length ? `<ul>${p.found.map(x => `<li><span class="badge ${x.strength === 'clear' ? 'good' : ''}">${x.strength === 'clear' ? 'Clear' : 'Possible'}</span> ${esc(x.text)}</li>`).join('')}</ul>`
        : '<p>No pattern stands out yet — your mood isn’t following any one factor. Keep logging.</p>'}
      ${p.rating_check ? `<p class="mdcheck"><b>Does our day rating match you?</b> ${esc(p.rating_check.text)}</p>` : ''}
      <p class="hint">From ${p.logs} logs. “Clear” means the difference is unlikely to be chance; patterns are for reflection, not fate.</p></div>`;
  }

  function paint(keepFocus) {
    if (!EL) return;
    EL.innerHTML = `<h3>How are you feeling? <small>state of mind</small></h3>
      ${S.reply ? replyView() : form()}
      ${strip()}
      <div class="mdfoot">
        <button type="button" class="linkbtn" id="mdpat" aria-expanded="${S.showPat}">${S.showPat ? 'Hide my patterns' : 'See my patterns'}</button>
        ${patView()}
        <label class="mdshare"><input type="checkbox" id="mdshare"${S.share ? ' checked' : ''}> Let Sukh use my mood log in chat</label>
        <small class="hint">Your mood log is private to you.${S.logs.length ? ' <button type="button" class="linkbtn" id="mddel">Delete my mood log</button>' : ''}</small>
      </div>`;
    if (keepFocus) { const f = EL.querySelector('#' + keepFocus); if (f) f.focus(); }
  }

  async function loadPat() {
    S.pat = null; paint();
    try { S.pat = await (await fetch(`/profiles/${S.pid}/mood/patterns`)).json(); } catch (e) { S.pat = { ready: false, logs: S.logs.length, needed: 1 }; }
    paint();
  }

  document.addEventListener('input', e => {
    if (e.target.id === 'mdv') {
      const v = +e.target.value;
      EL.querySelector('.mdval').textContent = SCALE[v + 3];
      EL.querySelector('.mdscale .mdorb').style.background = tone(v);
    } else if (e.target.id === 'mdnote') S.note = e.target.value;
  });
  document.addEventListener('change', async e => {
    if (e.target.id === 'mdv') {
      const v = +e.target.value;
      if (S.v === null || group(S.v) !== group(v)) S.feelings = [];
      S.v = v; paint('mdv');
    } else if (e.target.id === 'mdshare') {
      const share = e.target.checked;
      try { await fetch(`/profiles/${S.pid}/mood/share`, { method: 'PUT', headers: { 'content-type': 'application/json' }, body: JSON.stringify({ share }) }); S.share = share; }
      catch (err) { e.target.checked = !share; }
    }
  });
  // A tap on the slider at its starting point counts as a choice too (no "change" fires then).
  document.addEventListener('pointerup', e => { if (e.target.id === 'mdv' && S.v === null) { S.v = +e.target.value; paint('mdv'); } });

  document.addEventListener('click', async e => {
    if (!EL || !EL.contains(e.target)) return;
    const t = e.target.closest('button');
    if (!t) return;
    if (t.dataset.scope) { S.scope = t.dataset.scope; paint(); }
    else if (t.dataset.f !== undefined) {
      const x = t.dataset.f;
      S.feelings = S.feelings.includes(x) ? S.feelings.filter(y => y !== x) : S.feelings.length < 5 ? [...S.feelings, x] : S.feelings;
      paint();
    } else if (t.dataset.c !== undefined) {
      const x = t.dataset.c;
      S.causes = S.causes.includes(x) ? S.causes.filter(y => y !== x) : S.causes.length < 5 ? [...S.causes, x] : S.causes;
      paint();
    } else if (t.id === 'mdsave') {
      S.busy = true; S.err = ''; paint();
      try {
        const here = window.SJ_LOC && window.SJ_LOC.get();
        const r = await fetch(`/profiles/${S.pid}/mood`, { method: 'POST', headers: { 'content-type': 'application/json' },
          body: JSON.stringify({ valence: S.v, feelings: S.feelings, causes: S.causes, note: S.note || null, scope: S.scope, here: here || null }) });
        const d = await r.json();
        if (!r.ok) throw new Error(Array.isArray(d.detail) ? d.detail.map(x => x.msg).join('; ') : d.detail || r.statusText);
        S.logs.unshift(d.log); S.reply = d.reply;
        Object.assign(S, { v: null, feelings: [], causes: [], note: '', scope: 'now' });
        if (S.showPat) loadPat();
      } catch (err) { S.err = 'Couldn’t save: ' + err.message; }
      S.busy = false; paint();
    } else if (t.id === 'mdagain') { S.reply = null; paint(); }
    else if (t.id === 'mdask') { window.askSukh && window.askSukh(S.reply.ask); }
    else if (t.id === 'mdpat') { S.showPat = !S.showPat; S.showPat ? loadPat() : paint(); }
    else if (t.id === 'mddel') {
      if (!confirm('Delete your whole mood log? This can’t be undone.')) return;
      await fetch(`/profiles/${S.pid}/mood`, { method: 'DELETE' });
      Object.assign(S, { logs: [], reply: null, pat: null }); S.showPat ? loadPat() : paint();
    }
  });
})();
