// Coming up for you (Today): the next period changes and the sky changes that matter to this chart.
(function () {
  const esc = s => String(s ?? '').replace(/[&<>"]/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));
  const MON = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
  const LABEL = { period: ['Period change', 'good'], sky: ['Sky change', ''] };
  let S = {}, EL = null;

  window.renderUpcoming = async function (el, pid) {
    EL = el; S = { pid, data: null, all: false };
    if (pid == null) { el.hidden = true; return; }
    el.hidden = false;
    el.innerHTML = '<h3>Coming up for you</h3><div class="hint">Looking ahead…</div>';
    const loc = window.SJ_LOC && window.SJ_LOC.get();
    const tz = (loc && loc.tz_name) || (window.SJ_LOC && window.SJ_LOC.birthTz && window.SJ_LOC.birthTz()) || '';
    try {
      const r = await fetch(`/profiles/${pid}/upcoming` + (tz ? '?tz=' + encodeURIComponent(tz) : '')), d = await r.json();
      if (!r.ok) throw new Error(d.detail || r.statusText);
      if (S.pid === pid) { S.data = d; paint(); }
    } catch (e) { el.innerHTML = `<h3>Coming up for you</h3><p class="hint err">Couldn’t look ahead: ${esc(e.message)}</p>`; }
  };

  const day = iso => { const [y, m, d] = iso.split('-').map(Number); return { d, m: MON[m - 1], y }; };
  const inDays = iso => Math.round((new Date(iso + 'T00:00') - new Date(S.data.today + 'T00:00')) / 864e5);

  function item(it, i) {
    const w = day(it.date), n = inDays(it.date), u = it.until && day(it.until), lab = LABEL[it.kind];
    return `<li class="upi">
      <div class="update"><b>${w.d}</b><small>${w.m}</small></div>
      <div class="upbody">
        <div class="upmeta"><span class="badge ${lab[1]}">${lab[0]}</span><span class="upconf">${it.confidence === 'strong' ? 'Strong' : 'Hint'}</span>
          <small>${n === 1 ? 'tomorrow' : n < 60 ? `in ${n} days` : `in ${Math.round(n / 30.4)} months`}${u ? ` · until ${u.m} ${u.y}` : ''}</small></div>
        <b class="uptitle">${esc(it.title)}</b>
        <p>${esc(it.meaning)}</p>
        <p class="upprep"><span>Prepare</span>${esc(it.prepare)}</p>
        <div class="upact"><button type="button" class="linkbtn" data-ask="${i}">Ask Sukh →</button>
          <button type="button" class="linkbtn" data-ics="${i}">Add to calendar</button></div>
      </div></li>`;
  }

  function paint() {
    const items = S.data.items, shown = S.all ? items : items.slice(0, 3);
    EL.innerHTML = `<h3>Coming up for you</h3>
      ${items.length ? `<ul class="uplist">${shown.map(item).join('')}</ul>
        ${items.length > 3 ? `<button type="button" class="linkbtn upmore" id="upmore">${S.all ? 'Show less' : `Show all ${items.length}`}</button>` : ''}`
        : '<p class="gsub">No big changes in the next three months — a steady stretch. Use the good days below.</p>'}
      <p class="hint">${esc(S.data.note)}</p>`;
  }

  // An all-day calendar entry, so the date sits in the person's own calendar app.
  function ics(it) {
    const d = it.date.replace(/-/g, ''), next = new Date(it.date + 'T00:00');
    next.setDate(next.getDate() + 1);
    const e = next.getFullYear() + String(next.getMonth() + 1).padStart(2, '0') + String(next.getDate()).padStart(2, '0');
    const txt = s => s.replace(/[\\,;]/g, m => '\\' + m).replace(/\n/g, '\\n');
    const body = ['BEGIN:VCALENDAR', 'VERSION:2.0', 'PRODID:-//SimpleJyotish//Coming up//EN', 'BEGIN:VEVENT',
      `UID:${d}-${Math.random().toString(36).slice(2)}@simplejyotish`, `DTSTAMP:${new Date().toISOString().replace(/[-:]/g, '').slice(0, 15)}Z`,
      `DTSTART;VALUE=DATE:${d}`, `DTEND;VALUE=DATE:${e}`, `SUMMARY:${txt(it.title)}`,
      `DESCRIPTION:${txt(it.meaning + '\nPrepare: ' + it.prepare + '\n— SimpleJyotish')}`, 'END:VEVENT', 'END:VCALENDAR'].join('\r\n');
    const a = document.createElement('a');
    a.href = URL.createObjectURL(new Blob([body], { type: 'text/calendar' }));
    a.download = `simplejyotish-${it.date}.ics`;
    document.body.appendChild(a); a.click(); a.remove();
    setTimeout(() => URL.revokeObjectURL(a.href), 2000);
  }

  document.addEventListener('click', e => {
    if (!EL || !EL.contains(e.target) || !S.data) return;
    const t = e.target.closest('button');
    if (!t) return;
    if (t.id === 'upmore') { S.all = !S.all; paint(); }
    else if (t.dataset.ask !== undefined) { window.askSukh && window.askSukh(S.data.items[+t.dataset.ask].ask); }
    else if (t.dataset.ics !== undefined) { ics(S.data.items[+t.dataset.ics]); }
  });
  // Dates follow where the person is (the shared location setting).
  window.addEventListener('sj-loc', () => { if (S.pid != null) window.renderUpcoming(EL, S.pid); });
})();
