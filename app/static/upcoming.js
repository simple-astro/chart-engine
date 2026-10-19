// Coming up for you (Today): the next period changes and the sky changes that matter to this chart.
(function () {
  const esc = s => String(s ?? '').replace(/[&<>"]/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));
  const MON = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
  const LABEL = { period: ['Dasha change', 'good'], sky: ['Transit', 'tr'] };
  let S = {}, EL = null;

  window.renderUpcoming = async function (el, pid) {
    EL = el; S = { pid, data: null, all: false, kind: 'all', open: new Set(), days: {} };
    if (pid == null) { el.hidden = true; return; }
    el.hidden = false;
    el.innerHTML = '<h3>Coming up for you</h3><div class="hint">Looking ahead…</div>';
    const loc = window.SJ_LOC && window.SJ_LOC.get();
    const tz = (loc && loc.tz_name) || (window.SJ_LOC && window.SJ_LOC.birthTz && window.SJ_LOC.birthTz()) || '';
    try {
      const r = await fetch(`/profiles/${pid}/upcoming` + (tz ? '?tz=' + encodeURIComponent(tz) : '')), d = await r.json();
      if (!r.ok) throw new Error(window.apiErr(d.detail) || r.statusText);
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
        ${ready(it, i)}
        <div class="upact"><button type="button" class="linkbtn" data-ask="${i}">Ask Astropositivism →</button>
          <button type="button" class="linkbtn" data-ics="${i}">Add to calendar</button></div>
      </div></li>`;
  }

  // The "get ready" checklist: practical, no-regret steps before it starts, on the day, and during it.
  function ready(it, i) {
    const lists = it.checklists || [];
    if (!lists.length) return '';
    const steps = lists.flatMap(l => [...l.before, ...l.during]), done = steps.filter(x => x.done).length;
    const open = S.open.has(i);
    const box = x => `<label class="upstep"><input type="checkbox" data-step="${esc(x.id)}" data-i="${i}"${x.done ? ' checked' : ''}><span>${esc(x.text)}</span></label>`;
    const days = S.days[i];
    const dayList = !days ? '' : days.loading ? '<p class="hint">Finding the best days…</p>' : days.err ? `<p class="hint err">${esc(days.err)}</p>`
      : days.dates.length ? `<div class="updays">${days.dates.map(d => { const w = day(d.date); return `<span><b>${d.weekday.slice(0, 3)} ${w.d} ${w.m}</b>${esc(d.label)}</span>`; }).join('')}</div>`
      : '<p class="hint">No especially good day in the first three weeks — any ordinary day outside Rahu Kaal is fine.</p>';
    return `<div class="upready">
      <button type="button" class="upreadybtn" data-ready="${i}" aria-expanded="${open}"><span>Get ready</span><small>${done} of ${steps.length} done</small><i class="chev" aria-hidden="true"></i></button>
      ${open ? lists.map((l, k) => `<div class="uplistc">${lists.length > 1 || k ? `<b>${esc(l.title)}</b>` : ''}
          <h6>Before it starts</h6>${l.before.map(box).join('')}
          ${l.on_the_day ? `<h6>On the day</h6><p class="upday">${esc(l.on_the_day)}.</p>
            ${k === 0 && it.activity ? (days ? dayList : `<button type="button" class="linkbtn" data-days="${i}">Find the best days to act →</button>`) : ''}` : ''}
          ${l.during.length ? `<h6>During</h6>${l.during.map(box).join('')}` : ''}</div>`).join('') : ''}
    </div>`;
  }

  async function findDays(i) {
    const it = S.data.items[i], loc = window.SJ_LOC && window.SJ_LOC.get();
    S.days[i] = { loading: true }; paint();
    const q = new URLSearchParams({ activity: it.activity, start: it.date, days: '21' });
    if (loc) { q.set('lat', loc.lat); q.set('lon', loc.lon); q.set('tz', loc.tz_name); }
    try {
      const r = await fetch(`/profiles/${S.pid}/upcoming/days?` + q), d = await r.json();
      if (!r.ok) throw new Error(window.apiErr(d.detail) || r.statusText);
      S.days[i] = { dates: d.dates };
    } catch (e) { S.days[i] = { err: 'Couldn’t find days: ' + e.message }; }
    paint();
  }

  // Telegram reminders: on the day of each change, and 3 days before a Dasha change (app/telegram_bot.py).
  function tgLine() {
    const t = S.data.telegram || {};
    if (t.linked && t.reminders !== 'off')
      return `<p class="uptg">🔔 Telegram reminders are on${t.reminders === 'dasha' ? ' for Dasha changes' : ''}: on the day of each change, and 3 days before a Dasha change. Change this in the bot’s /settings.</p>`;
    if (t.linked) return '<p class="uptg">🔕 Telegram reminders are off. Turn them on in the bot’s /settings.</p>';
    return '<p class="uptg"><button type="button" class="linkbtn" id="uptg">Get these as Telegram reminders →</button></p>';
  }

  function paint() {
    // One list in date order; the chips narrow it to Dasha changes or transits. Indexes stay those of S.data.items.
    const all = S.data.items.map((it, i) => [it, i]), kinds = new Set(S.data.items.map(it => it.kind));
    const items = all.filter(([it]) => S.kind === 'all' || it.kind === S.kind), shown = S.all ? items : items.slice(0, 5);
    const chip = (k, t) => `<button type="button" data-upk="${k}" aria-pressed="${S.kind === k}">${t}</button>`;
    EL.innerHTML = `<h3>Coming up for you</h3>
      ${kinds.size > 1 ? `<div class="upchips" role="group" aria-label="Show">${chip('all', 'All')}${chip('period', 'Dasha')}${chip('sky', 'Transit')}</div>` : ''}
      ${items.length ? `<ul class="uplist">${shown.map(([it, i]) => item(it, i)).join('')}</ul>
        ${items.length > 5 ? `<button type="button" class="linkbtn upmore" id="upmore">${S.all ? 'Show less' : `Show all ${items.length}`}</button>` : ''}`
        : '<p class="gsub">No big changes in the next three months — a steady stretch. Use the good days below.</p>'}
      ${tgLine()}
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
    if (t.id === 'uptg') { const b = document.getElementById('tgbtn'); if (b) b.click(); return; }
    if (t.dataset.upk) { S.kind = t.dataset.upk; S.all = false; paint(); }
    else if (t.id === 'upmore') { S.all = !S.all; paint(); }
    else if (t.dataset.ready !== undefined) { const i = +t.dataset.ready; S.open.has(i) ? S.open.delete(i) : S.open.add(i); paint(); }
    else if (t.dataset.days !== undefined) { findDays(+t.dataset.days); }
    else if (t.dataset.ask !== undefined) { window.askSukh && window.askSukh(S.data.items[+t.dataset.ask].ask); }
    else if (t.dataset.ics !== undefined) { ics(S.data.items[+t.dataset.ics]); }
  });
  document.addEventListener('change', async e => {
    const b = e.target;
    if (!EL || !EL.contains(b) || !b.dataset.step) return;
    const it = S.data.items[+b.dataset.i], step = it.checklists.flatMap(l => [...l.before, ...l.during]).find(x => x.id === b.dataset.step);
    try {
      const r = await fetch(`/profiles/${S.pid}/prep`, { method: 'PUT', headers: { 'content-type': 'application/json' }, body: JSON.stringify({ step: step.id, done: b.checked }) });
      if (!r.ok) throw new Error();
      step.done = b.checked;
    } catch (err) { b.checked = !b.checked; }
    paint();
  });
  // Dates follow where the person is (the shared location setting).
  window.addEventListener('sj-loc', () => { if (S.pid != null) window.renderUpcoming(EL, S.pid); });
})();
