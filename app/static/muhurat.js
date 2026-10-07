// Muhurat tab: renders /muhurat results — a 7-day strip, the chosen day's verdict per
// activity with reasons, a sunrise-to-sunset timeline, and a week-at-a-glance grid.
(function () {
  const ICON = {
    plane: '<path d="M3 11l18-8-8 18-2-8z"/>',
    rocket: '<path d="M5 21V4h12l-2 4 2 4H5"/>',
    home: '<path d="M3 11l9-7 9 7M5 10v10h14V10M10 20v-5h4v5"/>',
    car: '<path d="M3 16v-4l2.5-5h13L21 12v4zM3 16v2M21 16v2M7 12h.01M17 12h.01"/>',
    gem: '<path d="M7 3h10l4 6-9 12L3 9zM3 9h18M10 3l-2 6 4 12 4-12-2-6"/>',
    rings: '<circle cx="9" cy="14" r="5"/><circle cx="15" cy="14" r="5"/><path d="M10 5l2-2 2 2"/>',
    door: '<path d="M6 21V3h12v18M3 21h18M14 12h.01"/>',
    book: '<path d="M4 4h6a2 2 0 0 1 2 2v14a2 2 0 0 0-2-2H4zM20 4h-6a2 2 0 0 0-2 2v14a2 2 0 0 1 2-2h6z"/>',
    handshake: '<path d="M3 8h18v12H3zM8 8V5h8v3M3 13h18"/>',
  };
  const esc = s => String(s ?? '').replace(/[&<>"]/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));
  const BADGE = { excellent: 'good', good: 'good', fair: '', avoid: 'warn' };
  const CHOG = { best: 'Best', good: 'Good', neutral: 'Neutral', avoid: 'Avoid' };
  const icon = k => `<svg class="mi-ic" viewBox="0 0 24 24" aria-hidden="true">${ICON[k] || ''}</svg>`;

  window.renderMuhurat = function (el, data, state) {
    const tz = data.tz_name, days = data.days, day = days[state.sel] || days[0];
    const t = iso => new Date(iso).toLocaleTimeString([], { hour: 'numeric', minute: '2-digit', timeZone: tz });
    const span = w => w ? `${t(w[0])} – ${t(w[1])}` : '';
    const dShort = iso => new Date(iso + 'T12:00:00Z').toLocaleDateString([], { day: 'numeric', month: 'short', timeZone: 'UTC' });
    const dLong = iso => new Date(iso + 'T12:00:00Z').toLocaleDateString([], { weekday: 'long', day: 'numeric', month: 'long', timeZone: 'UTC' });

    const strip = days.map((d, i) => `<button type="button" class="mday${i === state.sel ? ' on' : ''}" data-i="${i}" aria-pressed="${i === state.sel}">
        <small>${i === 0 && state.today ? 'Today' : esc(d.weekday.slice(0, 3))}</small><b>${esc(dShort(d.date))}</b>
        <span class="mdot ${d.overall.verdict}" title="${esc(d.overall.label)}"></span></button>`).join('');

    const personal = [];
    if (day.tara) personal.push(`Your star today: <b>${esc(day.tara.name)}</b> <span class="${day.tara.score > 0 ? 'ok' : day.tara.score < 0 ? 'bad' : ''}">(${day.tara.score > 0 ? 'supportive' : day.tara.score < 0 ? 'challenging' : 'neutral'})</span>`);
    if (day.chandra) personal.push(`Moon from your Moon: <b>${day.chandra.house}${['th', 'st', 'nd', 'rd'][day.chandra.house % 10 > 3 || [11, 12, 13].includes(day.chandra.house) ? 0 : day.chandra.house % 10]}</b> <span class="${day.chandra.score > 0 ? 'ok' : day.chandra.score < 0 ? 'bad' : ''}">(${day.chandra.house === 8 ? 'Chandrashtama — be careful' : day.chandra.score > 0 ? 'good' : day.chandra.score < 0 ? 'weak' : 'neutral'})</span>`);

    const acts = day.activities.map(a => `<details class="mact">
        <summary>${icon(a.icon)}<span class="mn">${esc(a.name)}</span><span class="badge ${BADGE[a.verdict]}">${esc(a.label)}</span></summary>
        <ul>${a.why.map(w => `<li class="${w.good ? 'ok' : w.bad ? 'bad' : ''}"><i>${w.good ? '✓' : w.bad ? '✕' : '•'}</i>${esc(w.text)}</li>`).join('')}</ul>
        ${a.note ? `<p class="mnote">${esc(a.note)}</p>` : ''}</details>`).join('');

    const w = day.windows, rise = +new Date(w.sunrise), set = +new Date(w.sunset), len = set - rise;
    const pct = iso => Math.max(0, Math.min(100, (+new Date(iso) - rise) / len * 100));
    const bars = w.choghadiya.map(c => `<span class="cg ${c.quality}" title="${esc(c.name)} · ${esc(CHOG[c.quality])} · ${span([c.start, c.end])}"></span>`).join('');
    const over = (win, cls, label) => win ? `<span class="ov ${cls}" style="left:${pct(win[0])}%;width:${pct(win[1]) - pct(win[0])}%" title="${label} · ${span(win)}"></span>` : '';
    const now = Date.now(), nowMark = state.sel === 0 && state.today && now > rise && now < set ? `<span class="now" style="left:${pct(new Date(now).toISOString())}%" title="Now"></span>` : '';
    const bad = [w.rahu_kalam, w.yamaganda, w.gulika].map(x => x.map(v => +new Date(v)));
    const clash = c => bad.some(([a, b]) => +new Date(c.start) < b && +new Date(c.end) > a);
    const best = w.choghadiya.filter(c => (c.quality === 'best' || c.quality === 'good') && !clash(c));
    const timeline = `<div class="tl" role="img" aria-label="Day timeline from sunrise to sunset">${bars}${over(w.rahu_kalam, 'rk', 'Rahu kalam')}${over(w.yamaganda, 'yg', 'Yamaganda')}${over(w.abhijit, 'ab', 'Abhijit')}${nowMark}</div>
      <div class="tl-ends"><span>Sunrise ${t(w.sunrise)}</span><span>Sunset ${t(w.sunset)}</span></div>
      <div class="tl-legend"><span><i class="cg best"></i>Amrit (best)</span><span><i class="cg good"></i>Shubh / Labh</span><span><i class="cg neutral"></i>Chal</span><span><i class="cg avoid"></i>Avoid</span><span><i class="ov rk"></i>Rahu kalam</span>${w.abhijit ? '<span><i class="ov ab"></i>Abhijit</span>' : ''}</div>
      <div class="twocol mtimes">
        <div><h4 class="ok">Good times</h4><ul>
          ${w.abhijit ? `<li><b>Abhijit muhurat</b> ${span(w.abhijit)} <small>— the strongest midday window</small></li>` : '<li><small>No Abhijit muhurat on Wednesdays.</small></li>'}
          ${best.map(c => `<li><b>${esc(c.name)}</b> ${span([c.start, c.end])}</li>`).join('')}
          ${w.choghadiya.some(c => (c.quality === 'best' || c.quality === 'good') && clash(c)) ? '<li><small>Other good Choghadiyas today overlap a period to avoid, so they are left out.</small></li>' : ''}
          <li><b>Brahma muhurat</b> ${span(w.brahma)} <small>— for prayer and study</small></li></ul></div>
        <div><h4 class="bad">Avoid starting new things</h4><ul>
          <li><b>Rahu kalam</b> ${span(w.rahu_kalam)}</li>
          <li><b>Yamaganda</b> ${span(w.yamaganda)}</li>
          <li><b>Gulika kalam</b> ${span(w.gulika)}</li></ul></div>
      </div>`;

    const grid = `<div class="scroll"><table class="mgrid"><thead><tr><th>Activity</th>${days.map((d, i) =>
        `<th class="${i === state.sel ? 'on' : ''}"><button type="button" class="mpick" data-i="${i}">${esc(d.weekday.slice(0, 3))}<small>${esc(dShort(d.date))}</small></button></th>`).join('')}</tr></thead>
      <tbody>${days[0].activities.map((a, k) => `<tr><td>${icon(a.icon)} ${esc(a.name)}</td>${days.map((d, i) => {
        const x = d.activities[k];
        return `<td class="${i === state.sel ? 'on' : ''}"><span class="mdot ${x.verdict}" title="${esc(d.weekday)}: ${esc(x.label)}" aria-label="${esc(x.label)}"></span></td>`;
      }).join('')}</tr>`).join('')}</tbody></table></div>
      <div class="tl-legend"><span><i class="mdot excellent"></i>Very good</span><span><i class="mdot good"></i>Good</span><span><i class="mdot fair"></i>Okay with care</span><span><i class="mdot avoid"></i>Better to avoid</span></div>`;

    el.innerHTML = `<div class="mstrip" role="group" aria-label="Choose a day">${strip}</div>
      <div class="mplace">Times for <b>${esc(state.placeName)}</b> · <button type="button" class="linkbtn" id="mloc">${state.here ? 'Use birthplace instead' : 'Use my current location'}</button></div>
      <section class="msum">
        <div class="msum-h"><h3>${esc(dLong(day.date))}</h3><span class="badge ${BADGE[day.overall.verdict]}">Overall: ${esc(day.overall.label)}</span></div>
        <div class="mpan"><span>Tithi <b>${esc(day.tithi.name)}</b></span><span>Nakshatra <b>${esc(day.nakshatra)}</b></span><span>Yoga <b>${esc(day.yoga)}</b></span><span>Karana <b>${esc(day.karana)}</b></span></div>
        ${personal.length ? `<div class="mpers">${personal.join('<span class="sepdot">·</span>')}</div>` : ''}
      </section>
      <h3 class="mh3">${state.sel === 0 && state.today ? 'Is today' : 'Is this day'} good for…</h3><div class="macts">${acts}</div>
      <h3 class="mh3">Best and worst times of the day</h3>${timeline}
      <h3 class="mh3">Find a good day this week</h3>${grid}`;
  };
})();
