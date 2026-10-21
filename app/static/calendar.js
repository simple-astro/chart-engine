// Calendar (Today): the Hindu month by tithi and nakshatra, and the Nanakshahi layer, from /calendar.
(function () {
  const esc = s => String(s ?? '').replace(/[&<>"]/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));
  const post = (u, b) => fetch(u, { method: 'POST', headers: { 'content-type': 'application/json' }, body: JSON.stringify(b) })
    .then(async r => { const d = await r.json(); if (!r.ok) throw new Error(window.apiErr(d.detail) || r.statusText); return d; });
  const tzToday = tz => new Intl.DateTimeFormat('en-CA', { timeZone: tz, year: 'numeric', month: '2-digit', day: '2-digit' }).format(new Date());
  const pref = (k, d) => { try { return localStorage.getItem(k) || d; } catch (e) { return d; } };
  const save = (k, v) => { try { localStorage.setItem(k, v); } catch (e) {} };
  // "2026-11-24T06:56+05:30" → "6:56 am" (already local to the place)
  const hm = iso => { const [h, m] = iso.slice(11, 16).split(':').map(Number); return `${h % 12 || 12}:${String(m).padStart(2, '0')} ${h < 12 ? 'am' : 'pm'}`; };
  const MONTHS = ['January', 'February', 'March', 'April', 'May', 'June', 'July', 'August', 'September', 'October', 'November', 'December'];
  const WD = ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat'];
  const NAK_SHORT = { 'Purva Phalguni': 'P.Phal', 'Uttara Phalguni': 'U.Phal', 'Purva Ashadha': 'P.Asha', 'Uttara Ashadha': 'U.Asha',
    'Purva Bhadrapada': 'P.Bhad', 'Uttara Bhadrapada': 'U.Bhad', Shatabhisha: 'Shatab', Dhanishta: 'Dhanish', Mrigashira: 'Mriga', Punarvasu: 'Punarv' };
  const TARA_LINE = { good: 'a good star for you', hard: 'go gently with new starts', janma: 'your birth star returns: keep it simple' };
  let S = { el: null, o: null, y: 0, m: 0, sel: null, data: null };

  window.renderCalendar = function (el, o) {
    const same = S.o && S.o.birth === o.birth && S.o.loc.tz_name === o.loc.tz_name && S.o.loc.lat === o.loc.lat;
    S = same ? { ...S, el, o } : { el, o, y: 0, m: 0, sel: null, data: null };
    el.hidden = false;
    if (!S.y) { const t = tzToday(o.loc.tz_name); S.y = +t.slice(0, 4); S.m = +t.slice(5, 7); }
    load();
  };

  async function load() {
    const { el, o } = S, key = `${S.y}-${S.m}`;
    if (!S.data) el.innerHTML = '<h3>Calendar</h3><div class="hint">Laying out the month…</div>';
    try {
      const d = await post('/calendar', { year: S.y, month: S.m, lat: o.loc.lat, lon: o.loc.lon, tz_name: o.loc.tz_name,
        style: pref('sj_calstyle', 'purnimanta'), nanakshahi: pref('sj_nsv', 'sgpc'),
        birth_nakshatra: o.moon.nakshatra_index, birth_moon_sign: o.moon.sign_index });
      if (S.el !== el || `${S.y}-${S.m}` !== key) return;
      S.data = d; paint();
    } catch (e) { el.innerHTML = `<h3>Calendar</h3><div class="hint err">Couldn’t load the calendar: ${esc(e.message)}</div>`; }
  }

  const tithiShort = d => d.tithi === 15 ? 'Purnima' : d.tithi === 30 ? 'Amavas' : `${d.paksha[0]} ${d.tithi > 15 ? d.tithi - 15 : d.tithi}`;
  const marks = (d, view) => view === 'hindu' ? d.hindu : view === 'sikh' ? d.sikh.filter(x => !/^(Pooranmashi|Masya)$/.test(x)) : [...d.hindu, ...d.sikh.filter(x => !/^(Pooranmashi|Masya)$/.test(x))];

  function paint() {
    const d = S.data, view = pref('sj_calview', 'hindu'), today = tzToday(d.tz_name);
    const days = d.days, first = new Date(days[0].date + 'T12:00').getDay();
    if (!S.sel || !days.some(x => x.date === S.sel)) S.sel = days.some(x => x.date === today) ? today : days[0].date;
    const sel = days.find(x => x.date === S.sel);
    const lunar = [...new Set(days.map(x => x.lunar_month))].join(' → ');
    const ns = [...new Set(days.map(x => x.nanakshahi.month))].join(' → ');
    const sub = view === 'sikh' ? `${ns} · Nanakshahi ${d.nanakshahi_year}` : view === 'both' ? `${lunar} · ${ns} ${d.nanakshahi_year}`
      : `${lunar} · Vikram Samvat ${d.vikram_samvat} · ${d.samvatsara}`;
    const seg = (k, label) => `<button type="button" data-calview="${k}" aria-pressed="${view === k}"${view === k ? ' class="on"' : ''}>${label}</button>`;
    const cell = x => {
      const fest = marks(x, view).length, n = +x.date.slice(8);
      const top = view === 'sikh' ? `${x.nanakshahi.day} ${x.nanakshahi.month.slice(0, 3)}` : tithiShort(x);
      const low = view === 'hindu' ? (NAK_SHORT[x.nakshatra] || x.nakshatra) : view === 'both' ? `${x.nanakshahi.day} ${x.nanakshahi.month.slice(0, 3)}` : (x.tithi === 15 ? 'Pooranmashi' : x.tithi === 30 ? 'Masya' : '');
      const cls = ['cal-d', fest ? 'cal-fest' : '', x.date === today ? 'cal-now' : '', x.date === S.sel ? 'cal-sel' : ''].filter(Boolean).join(' ');
      return `<button type="button" class="${cls}" data-cald="${x.date}" aria-pressed="${x.date === S.sel}" aria-label="${n} ${MONTHS[S.m - 1]}, ${esc(x.tithi_name)}, ${esc(x.nakshatra)}${fest ? ', ' + esc(marks(x, view).join(', ')) : ''}">
        <b>${n}</b><small class="cal-t">${esc(top)}</small><small>${esc(low)}</small>
        ${x.tithi === 15 ? '<i class="cal-moon full" aria-hidden="true"></i>' : x.tithi === 30 ? '<i class="cal-moon new" aria-hidden="true"></i>' : ''}
        ${x.tara ? `<i class="cal-tara ${x.tara.kind}" aria-hidden="true"></i>` : ''}${x.chandrashtama ? '<i class="cal-ch" aria-hidden="true"></i>' : ''}</button>`;
    };
    const list = days.filter(x => marks(x, view).length).map(x => `<li><button type="button" data-cald="${x.date}">
        <span class="cal-ld"><b>${+x.date.slice(8)}</b><small>${WD[new Date(x.date + 'T12:00').getDay()]}</small></span>
        <span>${esc(marks(x, view).join(' · '))}</span></button></li>`).join('');
    S.el.innerHTML = `<h3>Calendar <small>${esc(S.o.place)}</small></h3>
      <div class="seg cal-seg" role="group" aria-label="Calendar">${seg('hindu', 'Hindu')}${seg('sikh', 'Nanakshahi')}${seg('both', 'Both')}</div>
      <div class="cal-head"><button type="button" class="cal-nav" data-calmove="-1" aria-label="Previous month">‹</button>
        <div><b>${MONTHS[S.m - 1]} ${S.y}</b><small>${esc(sub)}</small></div>
        <button type="button" class="cal-nav" data-calmove="1" aria-label="Next month">›</button></div>
      <div class="cal-grid" role="group" aria-label="${MONTHS[S.m - 1]} ${S.y}">${WD.map(w => `<span class="cal-wd">${w}</span>`).join('')}
        ${'<span></span>'.repeat(first)}${days.map(cell).join('')}</div>
      <div class="cal-key"><span><i class="cal-tara good"></i>Good star for you</span><span><i class="cal-tara hard"></i>Go gently</span>
        <span><i class="cal-ch"></i>Chandrashtama</span><span><i class="cal-fk"></i>Festival</span></div>
      ${daySheet(sel, view)}
      ${list ? `<h4 class="cal-h">This month</h4><ul class="cal-list">${list}</ul>` : ''}
      <details class="chrules"><summary>Calendar settings</summary>
        <div class="cal-set"><span>Month ends at</span>
          <button type="button" data-calstyle="purnimanta" aria-pressed="${d.style === 'purnimanta'}">Purnima</button>
          <button type="button" data-calstyle="amanta" aria-pressed="${d.style === 'amanta'}">Amavasya</button></div>
        <div class="cal-set"><span>Gurpurab dates</span>
          <button type="button" data-nsv="sgpc" aria-pressed="${d.nanakshahi === 'sgpc'}">SGPC jantri</button>
          <button type="button" data-nsv="original" aria-pressed="${d.nanakshahi === 'original'}">Original 2003</button></div>
        <p class="hint">The 2003 Nanakshahi calendar fixed most Gurpurabs to solar dates; the SGPC jantri keeps several on lunar dates, so they move each year. Pick the one your Gurdwara follows.</p></details>
      <p class="hint">Tithi and nakshatra at sunrise for ${esc(S.o.place)}. Festival dates follow the common North Indian rules; check the exact day with your temple or Gurdwara.</p>`;
  }

  function daySheet(x, view) {
    const n = +x.date.slice(8), wd = new Date(x.date + 'T12:00').toLocaleDateString(undefined, { weekday: 'long' });
    const fest = [...(view !== 'sikh' ? x.hindu : []), ...(view !== 'hindu' ? x.sikh : [])];
    const you = [x.tara ? `<li><i class="cal-tara ${x.tara.kind}"></i><span><b>${esc(x.tara.name)} tara</b>: ${TARA_LINE[x.tara.kind]}.</span></li>` : '',
      x.chandrashtama ? '<li><i class="cal-ch"></i><span><b>Chandrashtama</b>: the Moon is 8th from yours. Keep big decisions light.</span></li>' : '',
      /Vishti/.test(x.karana) ? '<li><i class="cal-tara hard"></i><span><b>Bhadra</b> (Vishti karana) at sunrise: start new things after it ends.</span></li>' : ''].join('');
    const row = (k, v) => `<div><span>${k}</span><b>${v}</b></div>`;
    return `<section class="cal-sheet" aria-label="${n} ${MONTHS[S.m - 1]}">
      <h4>${esc(wd)} ${n} ${MONTHS[S.m - 1]}</h4>
      <p class="cal-sub">${esc(x.lunar_month)} · ${esc(x.tithi_name)}${view !== 'hindu' ? ` · ${x.nanakshahi.day} ${esc(x.nanakshahi.month)} ${x.nanakshahi.year}` : ''}</p>
      ${fest.length ? `<ul class="cal-fests">${fest.map(f => `<li>${esc(f)}</li>`).join('')}</ul>` : ''}
      ${you ? `<ul class="cal-you">${you}</ul>` : ''}
      <div class="cal-rows">${row('Sunrise · Sunset', `${hm(x.sunrise)} · ${hm(x.sunset)}`)}${row('Nakshatra', esc(x.nakshatra))}
        ${row('Yoga · Karana', `${esc(x.yoga)} · ${esc(x.karana)}`)}${row('Rahu Kalam', `${hm(x.rahu_kalam[0])} – ${hm(x.rahu_kalam[1])}`)}
        ${x.sankranti ? row('Sankranti', `${esc(x.sankranti.name)}, ${hm(x.sankranti.at)}`) : ''}</div>
      <button type="button" class="linkbtn" data-ask="What does ${n} ${MONTHS[S.m - 1]} ${S.y} hold for me? (${esc(x.tithi_name)}, ${esc(x.nakshatra)}${fest.length ? ', ' + esc(fest.join(', ')) : ''})">Ask Astro about this day →</button>
    </section>`;
  }

  document.addEventListener('click', e => {
    if (!S.el || !S.el.contains(e.target)) return;
    const t = e.target.closest('[data-cald],[data-calmove],[data-calview],[data-calstyle],[data-nsv]'); if (!t) return;
    if (t.dataset.cald) { S.sel = t.dataset.cald; paint(); S.el.querySelector('.cal-sheet').scrollIntoView({ block: 'nearest' }); return; }
    if (t.dataset.calview) { save('sj_calview', t.dataset.calview); paint(); return; }
    if (t.dataset.calmove) { S.m += +t.dataset.calmove; if (S.m < 1) { S.m = 12; S.y--; } if (S.m > 12) { S.m = 1; S.y++; } S.sel = null; }
    if (t.dataset.calstyle) save('sj_calstyle', t.dataset.calstyle);
    if (t.dataset.nsv) save('sj_nsv', t.dataset.nsv);
    load();
  });
})();
