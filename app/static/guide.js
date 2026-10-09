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

    el.innerHTML = hero + `${today}${rem}
      <h3 class="gh">Plan &amp; decide</h3><div class="g2" id="gtools"></div><h3 class="gh">Your life areas</h3><div class="ggrid">${areas}</div>`;
  };

  window.renderToday = function (el, d, opt) {
    const t = iso => new Date(iso).toLocaleTimeString([], { hour: 'numeric', minute: '2-digit', timeZone: d.tz });
    const day0 = opt.week && opt.week[0], cap = s => s.charAt(0).toUpperCase() + s.slice(1);
    const li = xs => xs.map(x => `<li>${esc(x.text)}<small>${esc(cap(x.why))}</small></li>`).join('');
    const c = d.colour, u = d.upay;
    const best = d.best_times.length ? d.best_times.map(w => `<span><small>${esc(w.label)}</small><b>${t(w.start)} – ${t(w.end)}</b></span>`).join('')
      : '<span><small>Best time</small><b>Keep it routine today</b></span>';
    el.innerHTML = `<h3>Today for you <span class="badge ${{ excellent: 'good', good: 'good', fair: '', avoid: 'warn' }[d.rating.verdict]}">${esc(d.rating.label)}</span></h3>
      <p class="gsub">${esc(d.weekday)}${day0 ? ` · ${esc(day0.tithi.name)}` : ''} · ${esc(d.nakshatra)}${d.tara ? ` · your star: ${esc(d.tara.name)}` : ''}</p>
      <div class="tgrid"><div class="tcol">
        <p class="twhy">${esc(cap(d.rating.why))}.</p>
        ${d.sukh ? `<p class="tsukh"><img src="/static/sun.svg" alt="" width="22" height="22"><span>${esc(d.sukh)}</span></p>` : ''}
        <div class="dd tdd"><div><h5 class="ok">Do today</h5><ul>${li(d.do)}</ul></div><div><h5 class="bad">Avoid today</h5><ul>${li(d.avoid)}</ul></div></div>
      </div><div class="tcol">
        <div class="gtimes">${best}<span class="tbad"><small>Rahu Kaal — avoid</small><b>${t(d.rahu_kalam[0])} – ${t(d.rahu_kalam[1])}</b></span></div>
        <div class="tchips">
          <div title="${esc(c.why)}"><small>Wear</small><b><i class="tsw" style="background:${c.hex}"></i>${esc(cap(c.name))}</b>${c.avoid ? `<em>avoid ${esc(c.avoid)}</em>` : ''}</div>
          <div title="Traditional number of ${esc(d.number.planet)}"><small>Number</small><b>${d.number.value}</b><em>${esc(d.number.planet)}</em></div>
          <div><small>Travel</small><b>Not ${esc(d.direction.avoid)}</b><em>if you must: ${esc(d.direction.fix)}</em></div>
        </div>
        <div class="tup"><small>Today’s upay</small><p>Chant <b>${esc(u.mantra)}</b> 108 times, or donate ${esc(u.daan)}.</p><em>${esc(u.why)}.</em></div>
      </div></div>
      <div class="tfoot"><small class="hint">Times for ${esc(opt.place)}. Colour, number and direction are traditional associations, not promises.</small>
        <button type="button" class="linkbtn" id="tloc">${opt.here ? 'Use birthplace times' : 'Use my current location'}</button></div>
      ${opt.week && opt.week.length > 1 ? `<div class="gweek"><h5>This week</h5><div class="gwd">${opt.week.map((w, i) => `<button type="button" data-goto="muhurat" title="${esc(w.weekday)}: ${esc(w.overall.label)}">
        <span>${i ? esc(w.weekday.slice(0, 3)) : 'Today'}</span><b>${+w.date.slice(8)}</b><span class="mdot ${w.overall.verdict}"></span></button>`).join('')}</div>
        <button type="button" class="linkbtn" data-goto="muhurat">See the best days for travel, property, marriage…</button></div>` : ''}`;
  };
})();
