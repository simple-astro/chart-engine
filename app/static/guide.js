// Guidance-first results page: Sukh's summary, today, remedies and life areas.
(function () {
  const esc = s => String(s ?? '').replace(/[&<>"]/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));
  const ICON = {
    career: '<path d="M4 8h16v11H4zM9 8V5h6v3M4 13h16"/>',
    money: '<circle cx="12" cy="12" r="8"/><path d="M15 9.5c-.5-1-1.6-1.5-3-1.5-1.7 0-3 .8-3 2s1.3 1.7 3 2 3 .9 3 2-1.3 2-3 2c-1.4 0-2.5-.5-3-1.5M12 6.5v11"/>',
    love: '<path d="M12 20s-7-4.4-7-10a4 4 0 0 1 7-2.6A4 4 0 0 1 19 10c0 5.6-7 10-7 10z"/>',
    health: '<path d="M3 12h4l2-5 4 10 2-5h6"/>',
    home: '<path d="M3 11l9-7 9 7M5 10v10h14V10M10 20v-5h4v5"/>',
  };
  const ASK = {
    career: 'How is my career looking, and what should I do next?',
    money: 'How can I improve my finances? What should I avoid?',
    love: 'What does my chart say about love and marriage?',
    health: 'What health precautions should I take?',
    home: 'How is my home and family life looking?',
  };
  const ic = k => `<svg class="gico" viewBox="0 0 24 24" aria-hidden="true">${ICON[k]}</svg>`;

  window.renderGuide = function (el, g, who) {
    const first = esc((who || '').trim().split(' ')[0] || 'friend');
    const p = g.period;
    const hero = `<section class="card sukh">
        <div class="sukh-id"><img src="/static/sun.svg" alt="" width="52" height="52"><div><b>Sukh</b><span class="ai">AI Jyotishi</span>
          <small>Built on Sukhdeep Singh’s Nadi method</small></div></div>
        <h2>Namaste, ${first}.</h2>
        ${p ? `<p class="lead">You are in your <b>${p.md} period</b> until ${p.until} <span class="badge ${p.verdict.cls}">${p.verdict.label}</span></p>
          <p>${esc(p.text)} ${esc(p.now)}</p>
          ${p.focus.length ? `<div class="focusrow"><span>In focus now</span>${p.focus.map(f => `<span class="fchip">${esc(f)}</span>`).join('')}</div>` : ''}`
        : '<p class="lead">Here is what your chart says, and what you can do about it.</p>'}
        <div class="cta"><button type="button" class="btn" data-ask="">Ask Sukh anything</button>
          <button type="button" class="btn ghost" data-goto="muhurat">Good days this week</button></div>
      </section>`;

    const today = `<section class="card gcard" id="gtoday"><h3>Today for you</h3><div class="hint">Checking today’s panchang…</div></section>`;

    const rem = `<section class="card gcard"><h3>Your remedies <small>upay</small></h3>
        <ol class="grem">${g.remedies.map(r => `<li><b>${esc(r.title)}</b><p>${esc(r.text)}</p><small>${esc(r.why)}</small></li>`).join('')}</ol>
        <div class="glucky"><span><small>Lucky day</small><b>${esc(g.lucky.day)}</b></span><span><small>Colour</small><b>${esc(g.lucky.color)}</b></span><span><small>Number</small><b>${g.lucky.num}</b></span></div>
      </section>`;

    const areas = g.areas.map((a, i) => `<article class="card garea${i ? ' shut' : ''}">
        <div class="gmain"><header>${ic(a.key)}<h4>${esc(a.name)}</h4><span class="badge ${a.level.cls}">${a.level.label}</span></header>
          ${a.focus ? '<span class="fnow">Active in your current period</span>' : ''}
          <p class="gout">${esc(a.outlook)}</p>
          <button type="button" class="gmore" aria-expanded="${!i}"><span class="op">Hide</span><span class="cl">See Do’s, Don’ts &amp; upay</span></button>
          <button type="button" class="linkbtn" data-ask="${esc(ASK[a.key])}">Ask Sukh about this →</button></div>
        <div class="gdo"><h5 class="ok">Do</h5><ul>${a.dos.map(d => `<li>${esc(d)}</li>`).join('')}</ul></div>
        <div class="gdont"><h5 class="bad">Avoid</h5><ul>${a.donts.map(d => `<li>${esc(d)}</li>`).join('')}</ul></div>
        <div class="gup"><b>Upay</b><p>${esc(a.remedy.text)}</p><small>Why: ${esc(a.remedy.why)}.</small></div>
      </article>`).join('');

    el.innerHTML = hero + `<div class="g2">${today}${rem}</div>
      <h3 class="gh">Plan &amp; decide</h3><div class="g2" id="gtools"></div><h3 class="gh">Your life areas</h3><div class="ggrid">${areas}</div>`;
  };

  window.renderToday = function (el, d, place, week) {
    const t = iso => new Date(iso).toLocaleTimeString([], { hour: 'numeric', minute: '2-digit', timeZone: d.tz });
    const good = d.activities.filter(a => a.verdict === 'excellent' || a.verdict === 'good');
    const bad = d.activities.filter(a => a.verdict === 'avoid');
    const fair = d.activities.filter(a => a.verdict === 'fair');
    const w = d.windows;
    el.innerHTML = `<h3>Today for you <span class="badge ${{ excellent: 'good', good: 'good', fair: '', avoid: 'warn' }[d.overall.verdict]}">${esc(d.overall.label)}</span></h3>
      <p class="gsub">${esc(d.weekday)} · ${esc(d.tithi.name)} · ${esc(d.nakshatra)}${d.tara ? ` · your star: ${esc(d.tara.name)}` : ''}</p>
      <div class="dd"><div><h5 class="ok">Good for</h5><ul>${good.length ? good.map(a => `<li>${esc(a.name)}</li>`).join('') : '<li>Routine work — keep big starts for a better day</li>'}</ul></div>
        <div><h5 class="bad">Better to avoid</h5><ul>${bad.length ? bad.map(a => `<li>${esc(a.name)}</li>`).join('') : '<li>Nothing major today</li>'}</ul></div></div>
      ${fair.length ? `<div class="dd one"><div><h5 class="mid">Fine with care</h5><p class="gfair">${fair.map(a => esc(a.name)).join(' · ')}</p></div></div>` : ''}
      <div class="gtimes">${w.abhijit ? `<span><small>Best time</small><b>${t(w.abhijit[0])} – ${t(w.abhijit[1])}</b></span>` : ''}
        <span><small>Avoid starting at</small><b>${t(w.rahu_kalam[0])} – ${t(w.rahu_kalam[1])}</b></span></div>
      <small class="hint">Times for ${esc(place)}.</small>
      ${week && week.length > 1 ? `<div class="gweek"><h5>This week</h5><div class="gwd">${week.map((w, i) => `<button type="button" data-goto="muhurat" title="${esc(w.weekday)}: ${esc(w.overall.label)}">
        <span>${i ? esc(w.weekday.slice(0, 3)) : 'Today'}</span><b>${+w.date.slice(8)}</b><span class="mdot ${w.overall.verdict}"></span></button>`).join('')}</div>
        <button type="button" class="linkbtn" data-goto="muhurat">See the best days for travel, property, marriage…</button></div>` : ''}`;
  };
})();
