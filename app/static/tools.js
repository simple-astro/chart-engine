// "Plan & decide" tools on the guidance page: Muhurat Finder and KP Prashna (yes/no by number).
(function () {
  const $ = id => document.getElementById(id);
  const esc = s => String(s ?? '').replace(/[&<>"]/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));
  const ACTS = [['vehicle', 'Buying a vehicle'], ['property', 'Property or land'], ['gold', 'Gold, jewellery & clothes'],
    ['start', 'New work or business'], ['travel', 'Travel'], ['marriage', 'Marriage or engagement'],
    ['griha', 'Griha pravesh (housewarming)'], ['study', 'Studies or a new course'], ['meeting', 'Interview or key meeting']];
  const VERDICT = { yes: 'good', likely: 'good', mixed: '', no: 'warn' };
  let kinds = null;

  async function post(url, body) {
    const r = await fetch(url, { method: 'POST', headers: { 'content-type': 'application/json' }, body: JSON.stringify(body) });
    const j = await r.json();
    if (!r.ok) throw new Error(typeof j.detail === 'string' ? j.detail : r.statusText);
    return j;
  }
  const today = tz => new Intl.DateTimeFormat('en-CA', { timeZone: tz, year: 'numeric', month: '2-digit', day: '2-digit' }).format(new Date());

  window.renderTools = async function (el, ctx) {
    const req = ctx.req, moon = ctx.chart.grahas.Moon;
    const place = (req.place || '').split(',')[0] || 'your birthplace';
    let here = null;  // current location for Prashna, if the user shares it
    if (!kinds) { try { kinds = await (await fetch('/horary/kinds')).json(); } catch (e) { kinds = []; } }

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
          ? `<p class="hint">No strong day for ${esc(r.activity.name.toLowerCase())} in the next ${days} days. Try a longer range, or ask Sukh what to do meanwhile.</p>`
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
          <button type="button" class="btn ghost" id="hq-ask">Ask Sukh to explain</button>
          <p class="hint">Prashna answers the question as you hold it right now. Ask each question once — repeating it with new numbers weakens the answer.</p>`;
        $('hq-ask').onclick = () => window.askSukh && window.askSukh(ask);
      } catch (e) { out.innerHTML = `<p class="hint err">Couldn’t cast the chart: ${esc(e.message)}</p>`; }
      $('hq-go').disabled = false;
    };
  };
})();
