// "Plan & decide" tools: Muhurat Finder (Timing › Good dates), KP Prashna and Jamakkol Prashna (Studies › Prashna).
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
  const AB = { Sun: 'Su', Moon: 'Mo', Mars: 'Ma', Mercury: 'Me', Jupiter: 'Ju', Venus: 'Ve', Saturn: 'Sa', Rahu: 'Ra', Ketu: 'Ke', Snake: 'Sn', Paambu: 'Sn' };  // Paambu: questions saved before the rename
  const jkStyle = () => { try { return localStorage.getItem('sj_jk_style') || 'south'; } catch (e) { return 'south'; } };
  const herePlace = () => { try { const h = JSON.parse(localStorage.getItem('sj_here') || 'null'); return h && isFinite(h.lat) && h.tz_name ? h : null; } catch (e) { return null; } };
  // Jamakkol chart in the Jamakkol programs' layout: jama planets on an outer ring around the signs, inner planets
  // inside (retrograde in brackets), with Udayam (shaded), ARU, KAV and Md. South Indian (signs fixed) or North Indian.
  const RING = { 0: ['t', 1], 1: ['t', 2], 2: ['t', 3], 3: ['r', 1], 4: ['r', 2], 5: ['r', 3], 6: ['b', 2], 7: ['b', 1], 8: ['b', 0], 9: ['l', 2], 10: ['l', 1], 11: ['l', 0] };
  const skyLabel = (p, x) => x.retrograde && p !== 'Rahu' && p !== 'Ketu' ? `(${AB[p]})` : AB[p];
  function jkInside(r, i) {
    return Object.entries(r.transit).filter(([p, x]) => p !== 'Ketu' && x.sign_index === i).map(([p, x]) => skyLabel(p, x))
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
      <p class="jkl">Outer ring: <em>jama planets</em> with their degree · inside: the inner planets now ((Sa) = retrograde), Md = Maandi, ARU = Arudam, KAV = Kavippu</p>`;
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
      ...['Sun', 'Moon', 'Mars', 'Mercury', 'Jupiter', 'Venus', 'Saturn', 'Rahu'].filter(p => r.transit[p]).map(p => [p + (r.transit[p].retrograde && p !== 'Rahu' ? ' ℞' : ''), r.transit[p]]), ['Maandi', r.maandi]];
    return `<p class="jkh">Positions</p><table class="jktab pos"><colgroup><col><col><col></colgroup><thead><tr><th>Point</th><th>Longitude</th><th>Star</th></tr></thead><tbody>${
      rows.map(([n, x]) => `<tr><td>${esc(n)}</td><td class="n">${dms(x.lon)}</td><td>${esc(x.star)}</td></tr>`).join('')}</tbody></table>
      <p class="jkh">Prashna confirmation</p><table class="jktab cf"><colgroup><col><col></colgroup><tbody>${r.confirmation.map(([k, v]) => `<tr><td>${esc(k)}</td><td>${esc(v)}</td></tr>`).join('')}</tbody></table>
      ${jkRays(r)}`;
  }
  // Ray powers (as Divya Chakshu): each jama planet's rays, and the grid of rays × signs from each inner planet to it.
  // The planet's own cell (the Snake's is Rahu's) is marked.
  const INNER = ['Sun', 'Moon', 'Mars', 'Mercury', 'Jupiter', 'Venus', 'Saturn', 'Rahu'];
  function jkRays(r) {
    if (!r.ray_matrix || !r.rays) return '';  // casts saved before the grid existed
    const own = (j, i) => j === i || (j === 'Snake' && i === 'Rahu');
    return `<p class="jkh">Ray powers</p>
      <div class="jkrays">${Object.entries(r.rays).map(([p, v]) => `<span><small>${esc(p === 'Rahu' ? 'Rahu/Ketu' : p)}</small><b>${v}</b></span>`).join('')}</div>
      ${r.sign_rays ? `<div class="jkrays">${Object.entries(r.sign_rays).map(([s, v]) => `<span><small>${esc(s)}</small><b>${v}</b></span>`).join('')}</div>` : ''}
      <div class="scroll"><table class="jktab rays"><thead><tr><th></th>${INNER.map(i => `<th>${AB[i]}</th>`).join('')}</tr></thead><tbody>${
        r.ray_matrix.map(row => `<tr><th>${esc(row.jama)}</th>${INNER.map(i => `<td class="n${own(row.jama, i) ? ' own' : ''}">${row.cells[i]}</td>`).join('')}</tr>`).join('')}</tbody></table></div>
      <p class="jkn">Rays × signs counted from the inner planet (column) to the jama planet (row), both included.</p>`;
  }

  async function post(url, body) {
    const r = await fetch(url, { method: 'POST', headers: { 'content-type': 'application/json' }, body: JSON.stringify(body) });
    const j = await r.json();
    if (!r.ok) throw new Error(window.apiErr(j.detail) || r.statusText);
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
    const birthLabel = req.place ? 'Cast for ' + place + ' (birthplace)' : 'Cast for your birthplace';
    if (!kinds) { try { kinds = await (await fetch('/horary/kinds')).json(); } catch (e) { kinds = []; } }
    if (!jkinds) { try { jkinds = await (await fetch('/jamakkol/kinds')).json(); } catch (e) { jkinds = []; } }
    // Jamakkol is cast where the asker is now: the place typed here (remembered), else the app's "where you are"
    // setting, else the birthplace.
    const jkSaved = () => { try { const h = JSON.parse(localStorage.getItem('sj_jk_place') || 'null'); return h && isFinite(h.lat) && h.tz_name ? h : null; } catch (e) { return null; } };
    let jkHere = jkSaved() || herePlace();
    // KP Prashna is cast where the asker is too: its own remembered place, else Jamakkol's, else "where you are",
    // else the birthplace.
    const hqSaved = () => { try { const h = JSON.parse(localStorage.getItem('sj_hq_place') || 'null'); return h && isFinite(h.lat) ? h : null; } catch (e) { return null; } };
    let here = hqSaved() || jkHere;

    const finder = `<section class="card gcard tool">
        <h3>Find a good date</h3>
        <p class="gsub">Pick what you’re planning — I’ll check every day ahead against your chart.</p>
        <label class="tl-lab" for="ff-act">I’m planning</label>
        <select id="ff-act">${ACTS.map(([k, n]) => `<option value="${k}">${esc(n)}</option>`).join('')}</select>
        <div class="seg" role="radiogroup" aria-label="How far ahead">${[30, 60, 90].map((d, i) =>
          `<button type="button" role="radio" aria-checked="${!i}" class="${i ? '' : 'on'}" data-days="${d}">${d} days</button>`).join('')}</div>
        <button type="button" class="btn" id="ff-go">Find dates</button>
        <div id="ff-out" aria-live="polite"></div>
      </section>`;
    const prashna = `<section class="card gcard tool pqhow">
        <h3>How to ask a Prashna</h3>
        <ol>
          <li><b>Ask one question with a yes-or-no answer.</b> “Will I get this job?”, not “Tell me about my career.”</li>
          <li><b>Hold it in your mind and cast the chart</b>: type your number for KP Prashna, or press <i>Cast now</i> for Jamakkol. The chart is made for this moment and place.</li>
          <li><b>Ask each question once.</b> Asking again with new numbers only blurs the answer.</li>
          <li><b>After one KP Prashna and one Jamakkol</b> on the same question, consult your astrologer before you decide.</li>
        </ol>
        <div class="pqconsult" hidden></div>
      </section>
      <section class="card gcard tool">
        <h3>Yes or no? <small>KP Prashna</small></h3>
        <p class="gsub">Hold your question in mind, then type the first number from 1 to 249 that comes to you.</p>
        <label class="tl-lab" for="hq-kind">My question is about</label>
        <select id="hq-kind">${kinds.map(k => `<option value="${k.kind}">${esc(k.title)}</option>`).join('')}</select>
        <label class="tl-lab" for="hq-text">In my words <small>(optional)</small></label>
        <input id="hq-text" maxlength="160" placeholder="e.g. Will I get the job at the bank?">
        <label class="tl-lab" for="hq-place">Place <small>(where you are asking from)</small></label>
        <div class="hq-row"><input id="hq-place" maxlength="80" autocomplete="off" placeholder="Type a city, e.g. Bhopal" value="${esc(here ? (here.name || '') : (req.place || ''))}">
          <button type="button" class="btn ghost" id="hq-find">Search</button></div>
        <div class="sugg" id="hq-sugg" hidden></div>
        <div class="hq-place"><span id="hq-where">${esc(here ? (here.name ? 'Cast for ' + here.name : 'Cast for where you are') : birthLabel)}</span> · <button type="button" class="linkbtn" id="hq-loc">Use where I am now</button></div>
        <label class="tl-lab" for="hq-num">Your number</label>
        <div class="hq-row"><input id="hq-num" type="number" inputmode="numeric" min="1" max="249" placeholder="1–249" aria-label="Your number from 1 to 249">
          <button type="button" class="btn" id="hq-go">Ask</button></div>
        <div id="hq-out" aria-live="polite"></div>
      </section>
      <section class="card gcard tool">
        <h3>Ruling planets <small>KP</small></h3>
        <p class="gsub">The planets ruling this very moment, strongest first. Astrologers use them to confirm an answer and to time it.</p>
        <div id="rp-out" aria-live="polite"><p class="hint">Working out this moment…</p></div>
        <div class="hq-place"><span id="rp-where"></span> · <button type="button" class="linkbtn" id="rp-go">Refresh now</button></div>
      </section>
      <section class="card gcard tool">
        <h3>Jamakkol Prashna <small>Tamil horary</small></h3>
        <p class="gsub">Ask while the question is on your mind. The chart is cast for this very minute, where you are.</p>
        <label class="tl-lab" for="jk-kind">My question is about</label>
        <select id="jk-kind">${jkinds.map(k => `<option value="${k.kind}">${esc(k.title)}</option>`).join('')}</select>
        <label class="tl-lab" for="jk-text">In my words <small>(optional)</small></label>
        <input id="jk-text" maxlength="160" placeholder="e.g. Will the new job offer come through?">
        <label class="tl-lab" for="jk-place">Place <small>(where you are asking from)</small></label>
        <div class="hq-row"><input id="jk-place" maxlength="80" autocomplete="off" placeholder="Type a city, e.g. Bhopal" value="${esc(jkHere ? (jkHere.name || '') : (req.place || ''))}">
          <button type="button" class="btn ghost" id="jk-find">Search</button></div>
        <div class="sugg" id="jk-sugg" hidden></div>
        <div class="hq-place"><span id="jk-where">${esc(jkHere ? (jkHere.name ? 'Cast for ' + jkHere.name : 'Cast for where you are') : birthLabel)}</span> · <button type="button" class="linkbtn" id="jk-loc">Use where I am now</button></div>
        <button type="button" class="btn" id="jk-go">Cast now</button>
        <div id="jk-out" aria-live="polite"></div>
        <div id="jk-time"></div>
        <div id="jk-asks"></div>
      </section>`;
    // The date finder lives in Timing; the two Prashna tools in Studies › Prashna (or all here if no second place)
    if (ctx.prashnaEl) { el.innerHTML = finder; ctx.prashnaEl.innerHTML = prashna; } else el.innerHTML = finder + prashna;

    let days = 30;
    $('ff-go').closest('section').querySelector('.seg').addEventListener('click', e => {
      const b = e.target.closest('[data-days]'); if (!b) return;
      days = +b.dataset.days;
      $('ff-go').closest('section').querySelectorAll('.seg button').forEach(x => { x.classList.toggle('on', x === b); x.setAttribute('aria-checked', String(x === b)); });
    });

    $('ff-go').onclick = async () => {
      const out = $('ff-out'), btn = $('ff-go');
      btn.disabled = true; out.innerHTML = '<p class="hint">Checking the days ahead…</p>';
      try {
        const r = await post('/muhurat/find', { activity: $('ff-act').value, start: today(req.tz_name), days, lat: req.lat, lon: req.lon,
          tz_name: req.tz_name, birth_nakshatra: moon.nakshatra_index, birth_moon_sign: moon.sign_index });
        const t = iso => new Date(iso).toLocaleTimeString([], { hour: 'numeric', minute: '2-digit', timeZone: req.tz_name });
        const d = iso => new Date(iso + 'T12:00:00Z').toLocaleDateString([], { weekday: 'short', day: 'numeric', month: 'short', timeZone: 'UTC' });
        // Days a tradition rules out (Chaturmas, Kharmas, Ashtami…), with how many days each one closed.
        const skipped = (r.skipped || []).length ? `<div class="ffskip"><small>Days left out</small><ul>${r.skipped.map(x =>
          `<li>${esc(x.reason)} <span>· ${x.days} ${x.days === 1 ? 'day' : 'days'}</span></li>`).join('')}</ul></div>` : '';
        out.innerHTML = !r.dates.length
          ? `<p class="hint">No strong day for ${esc(r.activity.name.toLowerCase())} in the next ${days} days. Try a longer range, or ask Astropositivism what to do meanwhile.</p>${skipped}`
          : `<p class="ffsum">${r.matches} good ${r.matches === 1 ? 'day' : 'days'} in the next ${days} — the best, sorted by rating, then date:</p><ol class="ffl">${r.dates.map(x => `<li>
              <div class="ffh"><b>${d(x.date)}</b><span class="badge ${x.verdict === 'excellent' ? 'good' : ''}">${esc(x.label)}</span></div>
              ${x.windows.length ? `<div class="fft">Best time: ${[...x.windows].sort((a, b) => b.best - a.best).slice(0, 2).sort((a, b) => a.start < b.start ? -1 : 1).map(w => `${t(w.start)}–${t(w.end)}${w.name === 'Abhijit' || w.name === 'Amrit' ? ` (${w.name})` : ''}`).join(' · ')}</div>` : ''}
              <small>${esc(x.why.slice(0, 2).map(w => w.text).join('; '))}. Avoid ${t(x.rahu_kalam[0])}–${t(x.rahu_kalam[1])} (Rahu kalam).</small>
            </li>`).join('')}</ol>${r.dates[0].note ? `<p class="hint">${esc(r.dates[0].note)}</p>` : ''}
            ${skipped}<p class="hint">Times for ${esc(place)}.</p>`;
      } catch (e) { out.innerHTML = `<p class="hint err">Couldn’t search dates: ${esc(e.message)}</p>`; }
      btn.disabled = false;
    };

    // A place box for each Prashna: type a city and pick it (Open-Meteo geocoding, as for the birth details), or use
    // the device's location. The pick is remembered under its own key.
    function placeBox(k, key, set) {
      const where = $(k + '-where'), box = $(k + '-sugg'), input = $(k + '-place');
      const pick = (h, label) => { set(h); where.textContent = label; try { localStorage.setItem(key, JSON.stringify(h)); } catch (e) {} };
      $(k + '-loc').onclick = () => {
        if (!navigator.geolocation) { where.textContent = 'Location not available here: type your city above'; return; }
        where.textContent = 'Finding you…';
        navigator.geolocation.getCurrentPosition(p => {
          pick({ lat: +p.coords.latitude.toFixed(4), lon: +p.coords.longitude.toFixed(4), tz_name: Intl.DateTimeFormat().resolvedOptions().timeZone, name: 'where you are now' }, 'Cast for where you are now');
          input.value = '';
        }, () => { where.textContent = 'Location blocked: type your city above'; }, { timeout: 10000 });
      };
      async function find() {
        const q = input.value.trim(); if (q.length < 2) return;
        where.textContent = 'Searching…';
        try {
          const j = await (await fetch('https://geocoding-api.open-meteo.com/v1/search?count=6&language=en&name=' + encodeURIComponent(q))).json();
          const list = (j.results || []).filter(p => p.timezone);
          box.innerHTML = ''; box.hidden = !list.length;
          if (!list.length) { where.textContent = 'No match. Try the nearest big city.'; return; }
          list.forEach(p => {
            const name = [p.name, p.admin1, p.country].filter(Boolean).join(', '), d = document.createElement('div');
            d.textContent = name; d.setAttribute('role', 'button'); d.tabIndex = 0;
            const go = () => { input.value = name; box.hidden = true; pick({ lat: +p.latitude.toFixed(4), lon: +p.longitude.toFixed(4), tz_name: p.timezone, name }, 'Cast for ' + name); };
            d.onclick = go; d.onkeydown = e => { if (e.key === 'Enter') go(); };
            box.appendChild(d);
          });
          where.textContent = 'Pick your place:';
        } catch (e) { where.textContent = 'Place search unavailable right now.'; }
      }
      $(k + '-find').onclick = find;
      input.addEventListener('keydown', e => { if (e.key === 'Enter') { e.preventDefault(); find(); } });
      return find;
    }
    const hqFind = placeBox('hq', 'sj_hq_place', h => { here = h; rpShow(); });  // ruling planets follow the place
    const jkFind = placeBox('jk', 'sj_jk_place', h => { jkHere = h; });
    const pid = ctx.id;  // a saved chart: each question is kept (ask once for 81 days, then "did it happen?")
    const jkTitle = k => (jkinds.find(x => x.kind === k) || {}).title || k;
    const dmy = iso => new Date(iso.length > 10 ? iso : iso + 'T12:00:00Z').toLocaleDateString([], { day: 'numeric', month: 'short', year: 'numeric' });
    const OUT = { happened: 'It happened', partly: 'Partly', not: 'It didn’t happen' };
    async function call(url, opts) {
      const res = await fetch(url, opts), j = await res.json().catch(() => ({}));
      return { ok: res.ok, status: res.status, j };
    }
    // Time explorer under a cast chart (astrologers): step the day, slide the time of day, recast. It only explores:
    // the answer as asked (and any saved Jamakkol question) stays as it was.
    const zOff = (ms, tz) => {  // the zone's offset from UTC at that instant, in ms
      const p = Object.fromEntries(new Intl.DateTimeFormat('en-US', { timeZone: tz, hourCycle: 'h23', year: 'numeric', month: '2-digit', day: '2-digit',
        hour: '2-digit', minute: '2-digit', second: '2-digit' }).formatToParts(new Date(ms)).map(x => [x.type, x.value]));
      return Date.UTC(+p.year, +p.month - 1, +p.day, +p.hour, +p.minute, +p.second) - Math.floor(ms / 1000) * 1000;
    };
    const wallOf = (ms, tz) => { const l = new Date(ms + zOff(ms, tz)); return { y: l.getUTCFullYear(), m: l.getUTCMonth(), d: l.getUTCDate(), min: l.getUTCHours() * 60 + l.getUTCMinutes() }; };
    const utcOf = (w, tz) => { const g = Date.UTC(w.y, w.m, w.d, 0, w.min); return g - zOff(g - zOff(g, tz), tz); };
    // The bar sits right under its chart; take it out before the result is redrawn, so it keeps its state.
    const undock = (bar, res) => { if (bar && res && res.contains(bar)) res.after(bar); return bar; };
    function timeBar(box, askedIso, tz, recast, show) {
      if (!box) return;
      const asked = wallOf(Date.parse(askedIso), tz), key = w => `${w.y}-${w.m}-${w.d}-${w.min}`;
      let w = { ...asked }, seq = 0, timer = null;
      box.innerHTML = `<div class="tbar lv-pro" role="group" aria-label="Change the chart's time">
          <div class="tbh"><span>Time</span><b class="tbl"></b><button type="button" class="linkbtn tbr" hidden>Back to asked time</button></div>
          <input type="range" min="0" max="1439" step="1" aria-label="Time of day">
          <div class="tbrow"><button type="button" class="sbtn" data-dd="-1" aria-label="Previous day">‹ Day</button><button type="button" class="sbtn" data-dm="-1" aria-label="One minute earlier">−1 min</button><button type="button" class="sbtn" data-dm="1" aria-label="One minute later">+1 min</button><button type="button" class="sbtn" data-dd="1" aria-label="Next day">Day ›</button></div>
          <p class="tbn" aria-live="polite">Exploring only: your answer stays as asked.</p></div>`;
      const sl = box.querySelector('input'), lab = box.querySelector('.tbl'), back = box.querySelector('.tbr'), note = box.querySelector('.tbn');
      const paint = () => {
        sl.value = w.min; back.hidden = key(w) === key(asked);
        lab.textContent = new Date(utcOf(w, tz)).toLocaleString([], { weekday: 'short', day: 'numeric', month: 'short', year: 'numeric', hour: 'numeric', minute: '2-digit', timeZone: tz });
      };
      const go = () => {
        paint(); clearTimeout(timer);
        timer = setTimeout(async () => {
          const my = ++seq; note.textContent = 'Casting…';
          try { const r = await recast(new Date(utcOf(w, tz)).toISOString()); if (my === seq) { show(r, key(w) !== key(asked)); note.textContent = 'Exploring only: your answer stays as asked.'; } }
          catch (e) { if (my === seq) note.textContent = 'Couldn’t cast for that time: ' + e.message; }
        }, 220);
      };
      const set = (d, min) => { const n = new Date(Date.UTC(w.y, w.m, w.d + d, 0, min)); w = { y: n.getUTCFullYear(), m: n.getUTCMonth(), d: n.getUTCDate(), min: n.getUTCHours() * 60 + n.getUTCMinutes() }; go(); };
      sl.addEventListener('input', () => set(0, +sl.value));
      box.querySelector('.tbrow').addEventListener('click', e => { const b = e.target.closest('button'); if (!b) return;
        if (b.dataset.dd) set(+b.dataset.dd, w.min); else set(0, w.min + +b.dataset.dm); });
      back.onclick = () => { w = { ...asked }; go(); };
      paint();
    }
    function jkShow(r, q, exploring) {
      const bar = undock($('jk-time'), $('jk-out'));
      setTimeout(() => { const o = $('jk-out'); if (o && !o.querySelector('.pqline')) o.insertAdjacentHTML('beforeend', consultLine()); }, 0);
      const out = $('jk-out'), g = r.reading;
      const li = xs => xs.map(x => `<li>${esc(x)}</li>`).join('');
      const ask = `I asked a Jamakkol Prashna about ${g.question.title.toLowerCase()}${q ? `: "${q}"` : ''}. ` +
        `The Arudam is ${g.arudam_house} from the Udayam and the Kavippu is ${g.kavippu_house} from the Udayam. The result was "${g.label}". ` +
        `${[...g.obstacles, ...g.for, ...g.against].join(' ')} Please explain simply what this means for me and what I should do.`;
      const where = (r.ask && r.ask.place) || (jkHere && jkHere.name) || req.place || place;
      out.innerHTML = `<div class="hqv ${VERDICT[g.verdict]}"><span>Answer</span><b>${esc(g.label)}</b></div>
        <p class="jkn">Cast for ${esc(where)} · ${esc(new Date(r.asked_at).toLocaleString([], { day: 'numeric', month: 'short', year: 'numeric', hour: 'numeric', minute: '2-digit', timeZone: r.place.tz_name }))} (${esc(r.place.tz_name)})</p>
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
        <p class="hint">${exploring ? 'This chart is for the time picked below, not the moment you asked.' : `Jamakkol answers the question as you hold it right now, for 81 days${r.ask && r.ask.valid_until ? ` (until ${esc(dmy(r.ask.valid_until))})` : ''}. Ask each question once.`}</p>`;
      $('jk-ask').onclick = () => window.askSukh && window.askSukh(ask);
      if (exploring === undefined)  // a fresh cast or a saved answer: the time bar starts from its moment
        timeBar($('jk-time'), r.asked_at, r.place.tz_name,
          at => post('/jamakkol', { kind: g.question.kind, lat: r.place.lat, lon: r.place.lon, tz_name: r.place.tz_name, asked_at: at }),
          (x, moved) => jkShow({ ...x, ask: r.ask ? { place: r.ask.place } : undefined }, q, moved));
      if (bar) $('jk-chart').after(bar);
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
      undock($('jk-time'), out).innerHTML = ''; btn.disabled = true; out.innerHTML = '<p class="hint">Casting the Jamakkol chart for this minute…</p>';
      const typed = $('jk-place').value.trim();
      if (typed && typed !== (jkHere ? jkHere.name : (req.place || ''))) {  // typed a new place but didn't pick it yet
        btn.disabled = false; out.innerHTML = ''; return jkFind();
      }
      const at = jkHere || { lat: req.lat, lon: req.lon, tz_name: req.tz_name, name: req.place || place };
      const q = $('jk-text').value.trim(), body = { kind: $('jk-kind').value, lat: at.lat, lon: at.lon, tz_name: at.tz_name, place: at.name || null };
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

    // "Consult your astrologer on Telegram" (Admin › Settings › consult link); hidden when no link is set.
    let consultUrl = null;
    const consultLine = () => consultUrl ? `<p class="pqline">Got both answers? <a href="${esc(consultUrl)}" target="_blank" rel="noopener">Consult your astrologer on Telegram</a> before you decide.</p>`
      : '<p class="pqline">Got both answers? Consult your astrologer before you decide.</p>';
    fetch('/consult').then(r => r.ok ? r.json() : null).then(d => {
      consultUrl = d && d.telegram;
      const box = el.parentNode && (ctx.prashnaEl || el).querySelector('.pqconsult');
      if (consultUrl && box) { box.hidden = false; box.innerHTML = `<a class="btn pqtg" href="${esc(consultUrl)}" target="_blank" rel="noopener">Consult your astrologer on Telegram</a>`; }
    }).catch(() => {});

    // Ruling planets for now, cast where the KP Prashna is cast (the place chosen above, else the birthplace).
    async function rpShow() {
      const at = here && here.tz_name ? here : { lat: req.lat, lon: req.lon, tz_name: req.tz_name, name: req.place || place };
      $('rp-where').textContent = 'For ' + (at.name || 'where you are') + ', ' + new Date().toLocaleTimeString([], { hour: 'numeric', minute: '2-digit', timeZone: at.tz_name });
      try {
        const r = await post('/ruling-planets', { lat: at.lat, lon: at.lon, tz_name: at.tz_name });
        $('rp-out').innerHTML = `<table class="jktab cf"><colgroup><col><col></colgroup><tbody>${r.rows.map(x => `<tr><td>${esc(x.role)}</td><td>${esc(x.planet)}</td></tr>`).join('')}
          ${r.nodes.map(n => `<tr><td>${esc(n.planet)} (in ${esc(n.sign)}, for ${esc(n.for)})</td><td>${esc(n.planet)}</td></tr>`).join('')}</tbody></table>
          <p class="jkn">Ruling planets: <b>${r.ruling_planets.map(esc).join(', ')}</b> · Lagna ${esc(r.lagna.sign)}, ${esc(r.lagna.star)} (sub ${esc(r.lagna.sub_lord)}) · Moon ${esc(r.moon.sign)}, ${esc(r.moon.star)} (sub ${esc(r.moon.sub_lord)})</p>`;
      } catch (e) { $('rp-out').innerHTML = `<p class="hint err">Couldn’t work out the ruling planets: ${esc(e.message)}</p>`; }
    }
    $('rp-go').onclick = rpShow;
    rpShow();

    $('hq-num').addEventListener('keydown', e => { if (e.key === 'Enter') $('hq-go').click(); });
    $('hq-go').onclick = async () => {
      const n = parseInt($('hq-num').value, 10), out = $('hq-out');
      if (!(n >= 1 && n <= 249)) { out.innerHTML = '<p class="hint err">Please type a whole number from 1 to 249.</p>'; $('hq-num').focus(); return; }
      const typed = $('hq-place').value.trim();
      if (typed && typed !== (here ? here.name : (req.place || ''))) { out.innerHTML = ''; return hqFind(); }  // typed a new place but didn't pick it yet
      $('hq-go').disabled = true; out.innerHTML = '<p class="hint">Casting the Prashna chart…</p>';
      try {
        const body = { number: n, kind: $('hq-kind').value, ...(here ? { lat: here.lat, lon: here.lon } : { lat: req.lat, lon: req.lon }) };
        const tz = (here && here.tz_name) || req.tz_name, q = $('hq-text').value.trim();
        const r = await post('/horary', body);
        out.innerHTML = '<div id="hq-res"></div><div id="hq-time"></div>' + consultLine();
        hqShow(r, n, q, tz, false);
        timeBar($('hq-time'), r.asked_at, tz, at => post('/horary', { ...body, asked_at: at }), (x, moved) => hqShow(x, n, q, tz, moved));
      } catch (e) { out.innerHTML = `<p class="hint err">Couldn’t cast the chart: ${esc(e.message)}</p>`; }
      $('hq-go').disabled = false;
    };
    function hqShow(r, n, q, tz, exploring) {
      const ask = `I asked a KP Prashna (horary) question about ${r.question.title.toLowerCase()}${q ? `: "${q}"` : ''}. My number was ${n}. ` +
        `The result was "${r.label}". The reasons: ${r.reasons.join(' ')} Please explain simply what this means for me and what I should do.`;
      const bar = undock($('hq-time'), $('hq-res'));
      $('hq-res').innerHTML = `<div class="hqv ${VERDICT[r.verdict]}"><span>Answer</span><b>${esc(r.label)}</b></div>
        <div class="chart hqchart" id="hq-chart" role="img" aria-label="KP Prashna chart"></div>
        <ul class="hqr">${r.reasons.map(x => `<li>${esc(x)}</li>`).join('')}</ul>
        <p class="jkn">Cast for ${esc(here ? (here.name || 'where you are') : (req.place || place))} · ${esc(new Date(r.asked_at).toLocaleString([], { day: 'numeric', month: 'short', year: 'numeric', hour: 'numeric', minute: '2-digit', timeZone: tz }))}</p>
        <button type="button" class="btn ghost" id="hq-ask">Ask Astropositivism to explain</button>
        <p class="hint">${exploring ? 'This chart is for the time picked below, not the moment you asked.' : 'Prashna answers the question as you hold it right now. Ask each question once — repeating it with new numbers weakens the answer.'}</p>`;
      $('hq-ask').onclick = () => window.askSukh && window.askSukh(ask);
      if (window.drawNorth && r.chart) {
        const byH = {}, L = r.chart.lagna_sign;
        Object.entries(r.chart.planets).forEach(([p, x]) => { const h = (x.sign_index - L + 12) % 12;
          (byH[h] = byH[h] || []).push(AB[p] + (x.retrograde && p !== 'Rahu' && p !== 'Ketu' ? 'ᴿ' : '')); });
        window.drawNorth($('hq-chart'), L, byH, null, 'PRASHNA');
      }
      if (bar) $('hq-chart').after(bar);
    }
  };
})();
