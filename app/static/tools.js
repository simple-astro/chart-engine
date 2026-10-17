// "Plan & decide" tools on the guidance page: Muhurat Finder, KP Prashna (yes/no by number) and Jamakkol Prashna.
(function () {
  const $ = id => document.getElementById(id);
  const esc = s => String(s ?? '').replace(/[&<>"]/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));
  const ACTS = [['vehicle', 'Buying a vehicle'], ['property', 'Property or land'], ['gold', 'Gold, jewellery & clothes'],
    ['start', 'New work or business'], ['travel', 'Travel'], ['marriage', 'Marriage or engagement'],
    ['griha', 'Griha pravesh (housewarming)'], ['study', 'Studies or a new course'], ['meeting', 'Interview or key meeting']];
  const VERDICT = { yes: 'good', likely: 'good', mixed: '', no: 'warn' };
  let kinds = null, jkinds = null;
  // Jamakkol chart: South Indian layout (signs fixed), index = sign 0..11 → [row, col]
  const SOUTH = { 11: [0, 0], 0: [0, 1], 1: [0, 2], 2: [0, 3], 10: [1, 0], 3: [1, 3], 9: [2, 0], 4: [2, 3], 8: [3, 0], 7: [3, 1], 6: [3, 2], 5: [3, 3] };
  const SHORT = ['Ari', 'Tau', 'Gem', 'Can', 'Leo', 'Vir', 'Lib', 'Sco', 'Sag', 'Cap', 'Aqu', 'Pis'];
  const AB = { Sun: 'Su', Moon: 'Mo', Mars: 'Ma', Mercury: 'Me', Jupiter: 'Ju', Venus: 'Ve', Saturn: 'Sa', Rahu: 'Ra', Ketu: 'Ke', Paambu: 'Pb' };
  const jkStyle = () => { try { return localStorage.getItem('sj_jk_style') || 'south'; } catch (e) { return 'south'; } };
  const herePlace = () => { try { const h = JSON.parse(localStorage.getItem('sj_here') || 'null'); return h && isFinite(h.lat) && h.tz_name ? h : null; } catch (e) { return null; } };
  // Jamakkol chart in the Jamakkol programs' layout: jama planets on an outer ring around the signs, sky planets
  // inside (retrograde in brackets), with Udayam (shaded), ARU, KAV and Md. South Indian (signs fixed) or North Indian.
  const RING = { 0: ['t', 1], 1: ['t', 2], 2: ['t', 3], 3: ['r', 1], 4: ['r', 2], 5: ['r', 3], 6: ['b', 2], 7: ['b', 1], 8: ['b', 0], 9: ['l', 2], 10: ['l', 1], 11: ['l', 0] };
  const skyLabel = (p, x) => x.retrograde && p !== 'Rahu' && p !== 'Ketu' ? `(${AB[p]})` : AB[p];
  function jkInside(r, i) {
    return Object.entries(r.transit).filter(([, x]) => x.sign_index === i).map(([p, x]) => skyLabel(p, x))
      .concat(r.maandi.sign_index === i ? ['Md'] : [], r.arudam.sign_index === i ? ['ARU'] : [], r.kavippu.sign_index === i ? ['KAV'] : []);
  }
  function jkChart(r, style) {
    const U = r.udayam.sign_index, K = r.kavippu.sign_index;
    const ring = { t: [[], [], [], []], b: [[], [], [], []], l: [[], [], [], []], r: [[], [], [], []] };
    Object.entries(r.jama.planets).forEach(([p, x]) => { const [side, k] = RING[x.sign_index]; ring[side][k].push(`<span class="jkp">${AB[p]}<small>${Math.floor(x.lon)}°</small></span>`); });
    const band = (side, cls) => `<div class="${cls} ${side}">${ring[side].map(xs => `<div class="jko2">${xs.join('')}</div>`).join('')}</div>`;
    const t = new Date(r.asked_at).toLocaleTimeString([], { hour: 'numeric', minute: '2-digit', timeZone: r.place.tz_name });
    const wd = new Date(r.asked_at).toLocaleDateString('en-US', { weekday: 'long', timeZone: r.place.tz_name });
    const jam = `Jamam ${r.jama.number} · ${esc(r.jama.ruler)}` + (wd !== r.jama.weekday ? ` (${esc(r.jama.weekday)}’s)` : '');
    let inner;
    if (style === 'north') {
      inner = `<div class="jkin chart" id="jk-north"></div>`;
    } else {
      inner = `<div class="jkin"><div class="jkg">${Array.from({ length: 12 }, (_, i) => {
        const [row, col] = SOUTH[i], tags = i === U ? '<i class="jku">Udayam</i>' : '', inside = jkInside(r, i);
        return `<div class="jkc${i === U ? ' u' : ''}${i === K ? ' k' : ''}" style="grid-row:${row + 1};grid-column:${col + 1}">
          <small>${SHORT[i]}</small>${tags}${inside.length ? `<b>${inside.map(x => x === 'ARU' ? '<i class="jka">ARU</i>' : x === 'KAV' ? '<i class="jkk">KAV</i>' : x).join(' ')}</b>` : ''}</div>`;
      }).join('')}<div class="jkm"><b>Jamakkol</b><span>${esc(wd)} ${esc(t)}</span><span>${jam}</span><span>Hora ${esc(r.hora)}</span></div></div></div>`;
    }
    return `<div class="jkseg" role="group" aria-label="Chart style"><button type="button" data-style="south" aria-pressed="${style !== 'north'}">South</button><button type="button" data-style="north" aria-pressed="${style === 'north'}">North</button></div>
      <div class="jkwrap" role="img" aria-label="Jamakkol chart: Udayam ${esc(r.udayam.sign)}, Arudam ${esc(r.arudam.sign)}, Kavippu ${esc(r.kavippu.sign)}">
        ${band('t', 'jkrow')}${band('l', 'jkcol')}${inner}${band('r', 'jkcol')}${band('b', 'jkrow')}</div>
      ${style === 'north' ? `<p class="jkn">${esc(wd)} ${esc(t)} · ${jam} · Hora ${esc(r.hora)}</p>` : ''}
      <p class="jkl">Outer ring: <em>jama planets</em> with their degree · inside: planets in the sky now ((Sa) = retrograde), Md = Maandi, ARU = Arudam, KAV = Kavippu</p>`;
  }
  function jkDrawNorth(r) {
    const el = document.getElementById('jk-north'); if (!el || !window.drawNorth) return;
    const byH = {}, U = r.udayam.sign_index;
    for (let i = 0; i < 12; i++) byH[(i - U + 12) % 12] = jkInside(r, i);
    window.drawNorth(el, U, byH, null, 'UDAYAM');
  }
  const dms = lon => { const s = Math.floor(lon / 30), d = lon - s * 30, D = Math.floor(d), m = (d - D) * 60, M = Math.floor(m), S = Math.floor((m - M) * 60);
    return `${String(s).padStart(2, '0')}s ${String(D).padStart(2, '0')}° ${String(M).padStart(2, '0')}′ ${String(S).padStart(2, '0')}″`; };
  function jkTables(r) {
    const rows = [['Udayam', r.udayam], ['Arudam', r.arudam], ['Kavippu (Chatra)', r.kavippu],
      ...['Sun', 'Moon', 'Mars', 'Mercury', 'Jupiter', 'Venus', 'Saturn', 'Rahu', 'Ketu'].map(p => [p + (r.transit[p].retrograde && p !== 'Rahu' && p !== 'Ketu' ? ' ℞' : ''), r.transit[p]]), ['Maandi', r.maandi]];
    return `<p class="jkh">Positions</p><table class="jktab pos"><colgroup><col><col><col></colgroup><thead><tr><th>Point</th><th>Longitude</th><th>Star</th></tr></thead><tbody>${
      rows.map(([n, x]) => `<tr><td>${esc(n)}</td><td class="n">${dms(x.lon)}</td><td>${esc(x.star)}</td></tr>`).join('')}</tbody></table>
      <p class="jkh">Prashna confirmation</p><table class="jktab cf"><colgroup><col><col></colgroup><tbody>${r.confirmation.map(([k, v]) => `<tr><td>${esc(k)}</td><td>${esc(v)}</td></tr>`).join('')}</tbody></table>`;
  }

  async function post(url, body) {
    const r = await fetch(url, { method: 'POST', headers: { 'content-type': 'application/json' }, body: JSON.stringify(body) });
    const j = await r.json();
    if (!r.ok) throw new Error(typeof j.detail === 'string' ? j.detail : r.statusText);
    return j;
  }
  const today = tz => new Intl.DateTimeFormat('en-CA', { timeZone: tz, year: 'numeric', month: '2-digit', day: '2-digit' }).format(new Date());

  // "Show the working": how each point was found, and the 16 jamams of the day.
  function jkWorking(r) {
    const tz = r.place.tz_name, hm = iso => new Date(iso).toLocaleTimeString([], { hour: 'numeric', minute: '2-digit', timeZone: tz });
    const k = r.kavippu, m = new Intl.DateTimeFormat('en-US', { minute: 'numeric', timeZone: tz }).format(new Date(r.asked_at));
    const row = j => `<li class="${j.n === r.jama.number ? 'on' : ''}"><b>${j.n}</b> ${j.start}–${j.end} <span>${esc(j.ruler)}</span></li>`;
    return `<details class="jkw"><summary>Show the working</summary>
      <ul class="hqr">
        <li><b>Udayam</b> ${esc(r.udayam.sign)} ${r.udayam.deg.toFixed(1)}°: ${r.period === 'day' ? 'daytime' : 'night'} chart (${hm(r.period_start)}–${hm(r.period_end)}). It starts at the Sun's degree at ${r.period === 'day' ? 'sunrise' : 'sunset'} and runs all 12 signs by ${r.period === 'day' ? 'sunset' : 'sunrise'}.</li>
        <li><b>Arudam</b> ${esc(r.arudam.sign)}: from the minute hand (minute ${esc(m)}), 5 minutes per sign from Aries.</li>
        <li><b>Kavippu</b> ${esc(k.sign)}: the Sun is in ${esc(k.sun_sign)} (Tamil month ${esc(k.tamil_month)}), so the veedhi is ${esc(k.veedhi)}. From the Arudam to the veedhi is ${k.count}; the same ${k.count} from the Udayam gives ${esc(k.sign)}.</li>
        <li><b>Jama planets</b>: ${esc(r.jama.weekday)}'s lord ${esc(r.jama.lord)} stands at the end of Pisces at 6:00; all eight turn back 45° every 1½ hours.</li>
      </ul>
      <div class="jkt"><div><p>Day</p><ol>${r.jama.timeline.slice(0, 8).map(row).join('')}</ol></div><div><p>Night</p><ol>${r.jama.timeline.slice(8).map(row).join('')}</ol></div></div>
    </details>`;
  }

  window.renderTools = async function (el, ctx) {
    const req = ctx.req, moon = ctx.chart.grahas.Moon;
    const place = (req.place || '').split(',')[0] || 'your birthplace';
    let here = null;  // current location for Prashna, if the user shares it
    if (!kinds) { try { kinds = await (await fetch('/horary/kinds')).json(); } catch (e) { kinds = []; } }
    if (!jkinds) { try { jkinds = await (await fetch('/jamakkol/kinds')).json(); } catch (e) { jkinds = []; } }
    let jkHere = herePlace();  // Jamakkol is cast where the asker is now (the app's "where you are" setting)

    el.innerHTML = `<section class="card gcard tool">
        <h3>Find a good date</h3>
        <p class="gsub">Pick what you’re planning — I’ll check every day ahead against your chart.</p>
        <label class="tl-lab" for="ff-act">I’m planning</label>
        <select id="ff-act">${ACTS.map(([k, n]) => `<option value="${k}">${esc(n)}</option>`).join('')}</select>
        <div class="seg" role="radiogroup" aria-label="How far ahead">${[30, 60, 90].map((d, i) =>
          `<button type="button" role="radio" aria-checked="${!i}" class="${i ? '' : 'on'}" data-days="${d}">${d} days</button>`).join('')}</div>
        <button type="button" class="btn" id="ff-go">Find dates</button>
        <div id="ff-out" aria-live="polite"></div>
      </section>
      <section class="card gcard tool">
        <h3>Yes or no? <small>KP Prashna</small></h3>
        <p class="gsub">Hold your question in mind, then type the first number from 1 to 249 that comes to you.</p>
        <label class="tl-lab" for="hq-kind">My question is about</label>
        <select id="hq-kind">${kinds.map(k => `<option value="${k.kind}">${esc(k.title)}</option>`).join('')}</select>
        <label class="tl-lab" for="hq-text">In my words <small>(optional)</small></label>
        <input id="hq-text" maxlength="160" placeholder="e.g. Will I get the job at the bank?">
        <div class="hq-row"><input id="hq-num" type="number" inputmode="numeric" min="1" max="249" placeholder="1–249" aria-label="Your number from 1 to 249">
          <button type="button" class="btn" id="hq-go">Ask</button></div>
        <div class="hq-place">Cast for <b id="hq-where">${esc(place)}</b> · <button type="button" class="linkbtn" id="hq-loc">Use where I am now</button></div>
        <div id="hq-out" aria-live="polite"></div>
      </section>
      <section class="card gcard tool">
        <h3>Jamakkol Prashna <small>Tamil horary</small></h3>
        <p class="gsub">Ask while the question is on your mind. The chart is cast for this very minute, where you are.</p>
        <label class="tl-lab" for="jk-kind">My question is about</label>
        <select id="jk-kind">${jkinds.map(k => `<option value="${k.kind}">${esc(k.title)}</option>`).join('')}</select>
        <label class="tl-lab" for="jk-text">In my words <small>(optional)</small></label>
        <input id="jk-text" maxlength="160" placeholder="e.g. Will the new job offer come through?">
        <button type="button" class="btn" id="jk-go">Cast now</button>
        <div class="hq-place">Cast for <b id="jk-where">${esc(jkHere ? (jkHere.name || 'where you are') : place)}</b> · <button type="button" class="linkbtn" id="jk-loc">Use where I am now</button></div>
        <div id="jk-out" aria-live="polite"></div>
        <div id="jk-asks"></div>
      </section>`;

    let days = 30;
    el.querySelector('.seg').addEventListener('click', e => {
      const b = e.target.closest('[data-days]'); if (!b) return;
      days = +b.dataset.days;
      el.querySelectorAll('.seg button').forEach(x => { x.classList.toggle('on', x === b); x.setAttribute('aria-checked', String(x === b)); });
    });

    $('ff-go').onclick = async () => {
      const out = $('ff-out'), btn = $('ff-go');
      btn.disabled = true; out.innerHTML = '<p class="hint">Checking the days ahead…</p>';
      try {
        const r = await post('/muhurat/find', { activity: $('ff-act').value, start: today(req.tz_name), days, lat: req.lat, lon: req.lon,
          tz_name: req.tz_name, birth_nakshatra: moon.nakshatra_index, birth_moon_sign: moon.sign_index });
        const t = iso => new Date(iso).toLocaleTimeString([], { hour: 'numeric', minute: '2-digit', timeZone: req.tz_name });
        const d = iso => new Date(iso + 'T12:00:00Z').toLocaleDateString([], { weekday: 'short', day: 'numeric', month: 'short', timeZone: 'UTC' });
        out.innerHTML = !r.dates.length
          ? `<p class="hint">No strong day for ${esc(r.activity.name.toLowerCase())} in the next ${days} days. Try a longer range, or ask Astropositivism what to do meanwhile.</p>`
          : `<p class="ffsum">${r.matches} good ${r.matches === 1 ? 'day' : 'days'} in the next ${days} — the best:</p><ol class="ffl">${r.dates.map(x => `<li>
              <div class="ffh"><b>${d(x.date)}</b><span class="badge ${x.verdict === 'excellent' ? 'good' : ''}">${esc(x.label)}</span></div>
              ${x.windows.length ? `<div class="fft">Best time: ${[...x.windows].sort((a, b) => b.best - a.best).slice(0, 2).sort((a, b) => a.start < b.start ? -1 : 1).map(w => `${t(w.start)}–${t(w.end)}${w.name === 'Abhijit' || w.name === 'Amrit' ? ` (${w.name})` : ''}`).join(' · ')}</div>` : ''}
              <small>${esc(x.why.slice(0, 2).map(w => w.text).join('; '))}. Avoid ${t(x.rahu_kalam[0])}–${t(x.rahu_kalam[1])} (Rahu kalam).</small>
            </li>`).join('')}</ol>${r.dates[0].note ? `<p class="hint">${esc(r.dates[0].note)}</p>` : ''}
            <p class="hint">Times for ${esc(place)}.</p>`;
      } catch (e) { out.innerHTML = `<p class="hint err">Couldn’t search dates: ${esc(e.message)}</p>`; }
      btn.disabled = false;
    };

    $('hq-loc').onclick = () => {
      if (!navigator.geolocation) { $('hq-where').textContent = 'your birthplace (location not available)'; return; }
      $('hq-where').textContent = 'finding you…';
      navigator.geolocation.getCurrentPosition(p => { here = { lat: +p.coords.latitude.toFixed(4), lon: +p.coords.longitude.toFixed(4) }; $('hq-where').textContent = 'where you are now'; },
        () => { $('hq-where').textContent = place + ' (location blocked)'; }, { timeout: 10000 });
    };

    $('jk-loc').onclick = () => {
      if (!navigator.geolocation) { $('jk-where').textContent = 'your birthplace (location not available)'; return; }
      $('jk-where').textContent = 'finding you…';
      navigator.geolocation.getCurrentPosition(p => {
        jkHere = { lat: +p.coords.latitude.toFixed(4), lon: +p.coords.longitude.toFixed(4), tz_name: Intl.DateTimeFormat().resolvedOptions().timeZone };
        $('jk-where').textContent = 'where you are now';
      }, () => { $('jk-where').textContent = place + ' (location blocked)'; }, { timeout: 10000 });
    };
    const pid = ctx.id;  // a saved chart: each question is kept (ask once for 81 days, then "did it happen?")
    const jkTitle = k => (jkinds.find(x => x.kind === k) || {}).title || k;
    const dmy = iso => new Date(iso.length > 10 ? iso : iso + 'T12:00:00Z').toLocaleDateString([], { day: 'numeric', month: 'short', year: 'numeric' });
    const OUT = { happened: 'It happened', partly: 'Partly', not: 'It didn’t happen' };
    async function call(url, opts) {
      const res = await fetch(url, opts), j = await res.json().catch(() => ({}));
      return { ok: res.ok, status: res.status, j };
    }
    function jkShow(r, q) {
      const out = $('jk-out'), g = r.reading;
      const li = xs => xs.map(x => `<li>${esc(x)}</li>`).join('');
      const ask = `I asked a Jamakkol Prashna about ${g.question.title.toLowerCase()}${q ? `: "${q}"` : ''}. ` +
        `The Arudam is ${g.arudam_house} from the Udayam and the Kavippu is ${g.kavippu_house} from the Udayam. The result was "${g.label}". ` +
        `${[...g.obstacles, ...g.for, ...g.against].join(' ')} Please explain simply what this means for me and what I should do.`;
      out.innerHTML = `<div class="hqv ${VERDICT[g.verdict]}"><span>Answer${r.ask && r.ask.asked_at ? ` · asked ${esc(dmy(r.ask.asked_at))}` : ''}</span><b>${esc(g.label)}</b></div>
        <div id="jk-chart">${jkChart(r, jkStyle())}</div>
        ${jkTables(r)}
        <p class="jkh">Reading</p>
        <ul class="hqr">${li([g.about, ...g.focus, `Next to reach the Udayam: ${g.approaching.planet} (${g.approaching.about}).`, ...g.confirm])}</ul>
        <p class="jkh warn">Hidden obstacle (Kavippu)</p><ul class="hqr">${li([...g.obstacles, ...g.kavippu_notes])}</ul>
        ${g.for.length ? `<p class="jkh good">In favour</p><ul class="hqr">${li(g.for)}</ul>` : ''}
        ${g.against.length ? `<p class="jkh">Against</p><ul class="hqr">${li(g.against)}</ul>` : ''}
        ${g.strengths.length ? `<p class="jkh">Planet strengths now</p><ul class="hqr">${li(g.strengths)}</ul>` : ''}
        <p class="hint">${esc(g.lords.text)}</p>
        ${g.timing ? `<p class="hint">${esc(g.timing.text)}</p>` : ''}
        ${jkWorking(r)}
        <button type="button" class="btn ghost" id="jk-ask">Ask Astropositivism to explain</button>
        <p class="hint">Jamakkol answers the question as you hold it right now, for 81 days${r.ask ? ` (until ${esc(dmy(r.ask.valid_until))})` : ''}. Ask each question once.</p>`;
      $('jk-ask').onclick = () => window.askSukh && window.askSukh(ask);
      const paint = () => { $('jk-chart').innerHTML = jkChart(r, jkStyle()); jkDrawNorth(r); };
      jkDrawNorth(r);
      $('jk-chart').addEventListener('click', e => {
        const b = e.target.closest('[data-style]'); if (!b) return;
        try { localStorage.setItem('sj_jk_style', b.dataset.style); } catch (err) {}
        paint();
      });
    }
    async function jkList() {
      const box = $('jk-asks'); if (!pid || !box) return;
      const r = await call(`/profiles/${pid}/jamakkol`); if (!r.ok) return;
      box.innerHTML = r.j.length ? `<p class="jkh">Your Jamakkol questions</p><ul class="jkq">${r.j.slice(0, 12).map(a => `<li data-id="${a.id}">
          <div><b>${esc(jkTitle(a.kind))}</b>${a.question ? ` · “${esc(a.question)}”` : ''}<small>${esc(dmy(a.asked_at))} · ${esc(a.label)}</small></div>
          ${a.outcome ? `<small class="jko">${OUT[a.outcome]} · <button type="button" class="linkbtn" data-act="redo">change</button></small>`
            : a.due ? `<div class="jkd"><span>81 days are up. Did it happen?</span>${Object.entries(OUT).map(([k, v]) => `<button type="button" class="sbtn" data-out="${k}">${v.replace('It ', '').replace('didn’t happen', 'No').replace('happened', 'Yes')}</button>`).join('')}</div>`
            : `<small>Answer stands until ${esc(dmy(a.valid_until))} · <button type="button" class="linkbtn" data-act="see">see it</button> · <button type="button" class="linkbtn" data-act="early">it already happened?</button></small>`}
        </li>`).join('')}</ul>` : '';
    }
    $('jk-asks') && $('jk-asks').addEventListener('click', async e => {
      const li = e.target.closest('li[data-id]'); if (!li) return;
      const id = li.dataset.id, o = e.target.closest('[data-out]'), act = e.target.closest('[data-act]');
      if (o) { await call(`/profiles/${pid}/jamakkol/${id}/outcome`, { method: 'PUT', headers: { 'content-type': 'application/json' }, body: JSON.stringify({ outcome: o.dataset.out }) }); return jkList(); }
      if (act && act.dataset.act === 'see') { const r = await call(`/profiles/${pid}/jamakkol/${id}`); if (r.ok) { jkShow(r.j, r.j.ask.question); $('jk-out').scrollIntoView({ block: 'start' }); } return; }
      if (act && (act.dataset.act === 'early' || act.dataset.act === 'redo')) {
        const d = li.querySelector('.jkd, .jko, small:last-child');
        d.outerHTML = `<div class="jkd"><span>Did it happen?</span>${Object.entries(OUT).map(([k, v]) => `<button type="button" class="sbtn" data-out="${k}">${v.replace('It ', '').replace('didn’t happen', 'No').replace('happened', 'Yes')}</button>`).join('')}</div>`;
      }
    });
    async function jkCast(again) {
      const out = $('jk-out'), btn = $('jk-go');
      btn.disabled = true; out.innerHTML = '<p class="hint">Casting the Jamakkol chart for this minute…</p>';
      const at = jkHere || { lat: req.lat, lon: req.lon, tz_name: req.tz_name };
      const q = $('jk-text').value.trim(), body = { kind: $('jk-kind').value, lat: at.lat, lon: at.lon, tz_name: at.tz_name };
      try {
        if (!pid) { jkShow(await post('/jamakkol', body), q); }
        else {
          const r = await call(`/profiles/${pid}/jamakkol`, { method: 'POST', headers: { 'content-type': 'application/json' }, body: JSON.stringify({ ...body, question: q || null, again: !!again }) });
          if (r.status === 409 && r.j.detail && r.j.detail.code === 'asked') {
            const a = r.j.detail.ask;
            out.innerHTML = `<div class="qagate jkonce"><b>You asked about ${esc(jkTitle(a.kind).toLowerCase())} on ${esc(dmy(a.asked_at))}.</b>
              <span>Jamakkol answers a question once. That answer (“${esc(a.label)}”) stands until ${esc(dmy(a.valid_until))}; asking again only blurs it.</span>
              <div class="pgacts"><button type="button" class="btn" id="jk-see">See that answer</button><button type="button" class="btn ghost" id="jk-new">It’s a different question</button></div></div>`;
            $('jk-see').onclick = async () => { const x = await call(`/profiles/${pid}/jamakkol/${a.id}`); if (x.ok) jkShow(x.j, a.question); };
            $('jk-new').onclick = () => jkCast(true);
          } else if (!r.ok) throw new Error(typeof r.j.detail === 'string' ? r.j.detail : 'Something went wrong');
          else { jkShow(r.j, q); jkList(); }
        }
      } catch (e) { out.innerHTML = `<p class="hint err">Couldn’t cast the chart: ${esc(e.message)}</p>`; }
      btn.disabled = false;
    }
    $('jk-go').onclick = () => jkCast(false);
    jkList();

    $('hq-num').addEventListener('keydown', e => { if (e.key === 'Enter') $('hq-go').click(); });
    $('hq-go').onclick = async () => {
      const n = parseInt($('hq-num').value, 10), out = $('hq-out');
      if (!(n >= 1 && n <= 249)) { out.innerHTML = '<p class="hint err">Please type a whole number from 1 to 249.</p>'; $('hq-num').focus(); return; }
      $('hq-go').disabled = true; out.innerHTML = '<p class="hint">Casting the Prashna chart…</p>';
      try {
        const r = await post('/horary', { number: n, kind: $('hq-kind').value, ...(here || { lat: req.lat, lon: req.lon }) });
        const q = $('hq-text').value.trim();
        const ask = `I asked a KP Prashna (horary) question about ${r.question.title.toLowerCase()}${q ? `: "${q}"` : ''}. My number was ${n}. ` +
          `The result was "${r.label}". The reasons: ${r.reasons.join(' ')} Please explain simply what this means for me and what I should do.`;
        out.innerHTML = `<div class="hqv ${VERDICT[r.verdict]}"><span>Answer</span><b>${esc(r.label)}</b></div>
          <ul class="hqr">${r.reasons.map(x => `<li>${esc(x)}</li>`).join('')}</ul>
          <button type="button" class="btn ghost" id="hq-ask">Ask Astropositivism to explain</button>
          <p class="hint">Prashna answers the question as you hold it right now. Ask each question once — repeating it with new numbers weakens the answer.</p>`;
        $('hq-ask').onclick = () => window.askSukh && window.askSukh(ask);
      } catch (e) { out.innerHTML = `<p class="hint err">Couldn’t cast the chart: ${esc(e.message)}</p>`; }
      $('hq-go').disabled = false;
    };
  };
})();
