// Transits tab: the sky on a chosen date over the natal chart, the running daśā, and how they line up.
(function () {
  const esc = s => String(s ?? '').replace(/[&<>"]/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));
  const ABBR = { Sun: 'Su', Moon: 'Mo', Mars: 'Ma', Mercury: 'Me', Jupiter: 'Ju', Venus: 'Ve', Saturn: 'Sa', Rahu: 'Ra', Ketu: 'Ke' };
  const LV = { maha: 'Mahadasha', antar: 'Antardasha', praty: 'Pratyantar' };
  const fd = iso => new Date(iso + 'T12:00:00Z').toLocaleDateString([], { day: 'numeric', month: 'short', year: 'numeric', timeZone: 'UTC' });
  const ord = n => n + (n % 100 >= 11 && n % 100 <= 13 ? 'th' : { 1: 'st', 2: 'nd', 3: 'rd' }[n % 10] || 'th');
  const shift = (iso, days, months) => {
    const d = new Date(iso + 'T12:00:00Z');
    if (months) d.setUTCMonth(d.getUTCMonth() + months);
    d.setUTCDate(d.getUTCDate() + (days || 0));
    return d.toISOString().slice(0, 10);
  };

  window.renderTransit = function (el, profileId, tz) {
    if (profileId == null) { el.innerHTML = '<p class="hint">Save this chart to see transits over it.</p>'; return; }
    const today = new Intl.DateTimeFormat('en-CA', { timeZone: tz || undefined, year: 'numeric', month: '2-digit', day: '2-digit' }).format(new Date());
    let day = today, ctrl = null, evTopic = null, lastEv = null;
    el.innerHTML = `<div class="trbar" role="group" aria-label="Choose the transit date">
        <button type="button" class="trb" data-m="-1" title="Back one month">−1M</button>
        <button type="button" class="trb" data-d="-1" title="Back one day" aria-label="Previous day">‹</button>
        <input type="date" id="trdate" value="${day}" min="1900-01-01" max="2100-12-31" aria-label="Transit date">
        <button type="button" class="trb" data-d="1" title="Forward one day" aria-label="Next day">›</button>
        <button type="button" class="trb" data-m="1" title="Forward one month">+1M</button>
        <button type="button" class="trb trtoday" data-today="1">Today</button>
      </div>
      <div id="trbody" aria-live="polite"><p class="hint">Loading the sky…</p></div>`;
    const body = el.querySelector('#trbody'), input = el.querySelector('#trdate');

    async function load() {
      input.value = day;
      el.querySelector('.trtoday').classList.toggle('on', day === today);
      if (ctrl) ctrl.abort();
      ctrl = new AbortController();
      body.classList.add('loading');
      try {
        const r = await fetch(`/profiles/${profileId}/transit?date=${day}`, { signal: ctrl.signal });
        const d = await r.json(); if (!r.ok) throw new Error(d.detail || r.statusText);
        paint(d);
        const re = await fetch(`/profiles/${profileId}/transit/events?date=${day}`, { signal: ctrl.signal });
        const ev = await re.json(); if (!re.ok) throw new Error(ev.detail || re.statusText);
        lastEv = ev; paintEvents(ev);
      } catch (e) { if (e.name !== 'AbortError') body.innerHTML = `<p class="hint err">Couldn’t load transits: ${esc(e.message)}</p>`; }
      body.classList.remove('loading');
    }

    function paint(d) {
      const byH = {};
      d.planets.forEach(p => {
        const b = [p.retrograde ? 'R' : null].filter(Boolean);
        (byH[p.h_lagna - 1] = byH[p.h_lagna - 1] || []).push({ t: ABBR[p.planet], d: Math.floor(p.deg) + '°', p: p.planet, b, cls: p.dasha ? 'trd' : '' });
      });
      const m = d.moon_today;
      const dasha = d.dasha.map(x => `<div class="trda"><small>${LV[x.level]}</small><b>${esc(x.lord)}</b><span>${fd(x.start)} – ${fd(x.end)}</span></div>`).join('');
      const notes = d.notes.map(n => `<li class="${n.kind}">${esc(n.text)}</li>`).join('');
      const rows = d.planets.map(p => `<tr class="${p.dasha ? 'trdr' : ''}">
          <td><b>${p.planet}</b>${p.retrograde ? ' <span class="bd rt" title="Retrograde">R</span>' : ''}${p.dasha ? `<small>${esc(p.dasha)} lord</small>` : ''}</td>
          <td>${p.sign} ${Math.floor(p.deg)}°${String(Math.floor((p.deg % 1) * 60)).padStart(2, '0')}′</td>
          <td>${esc(p.nakshatra)} ${p.pada}<small>${p.star_lord} / ${p.sub_lord}</small></td>
          <td class="c">${p.h_lagna}</td><td class="c">${p.h_moon}</td><td class="c">${p.h_bhava}</td>
          <td class="c"><span class="${p.sav >= 28 ? 'ok' : p.sav < 25 ? 'bad' : ''}">${p.sav}</span></td>
          <td>${p.over_natal.length ? 'over natal ' + p.over_natal.join(', ') : ''}</td></tr>`).join('');
      body.innerHTML = `
        <div class="trtop">
          <section class="trcard"><h4>Running daśā on ${fd(d.date)}</h4><div class="trdas">${dasha}</div></section>
          <section class="trcard"><h4>Moon that day</h4><p class="trmoon"><b>${esc(m.nakshatra)}</b> in ${esc(m.sign)} · ${ord(m.h_moon)} from your Moon</p>
            <p class="hint" style="margin:2px 0 0">Your star (Tara): <b class="${m.tara_score > 0 ? 'ok' : m.tara_score < 0 ? 'bad' : ''}">${esc(m.tara)}</b> — ${esc(m.tara_note)}</p></section>
        </div>
        <section id="trev" class="trev" aria-live="polite"><p class="hint">Reading life events…</p></section>
        <div class="trmain">
          <div><h4 class="trh">Transits over your chart</h4><div class="chart trchart" id="trchart"></div>
            <p class="hint">Houses counted from your ${esc(d.lagna_sign)} lagna. Highlighted planets run your daśā. R = retrograde.</p></div>
          <div><h4 class="trh">How it lines up with your chart</h4><ul class="trnotes">${notes}</ul></div>
        </div>
        <h4 class="trh">Planetary transits</h4>
        <div class="scroll"><table class="trtable"><thead><tr><th>Planet</th><th>Sign</th><th>Nakshatra · star/sub</th>
          <th class="c" title="House from your lagna">Lagna</th><th class="c" title="House from your Moon">Moon</th><th class="c" title="Nirayana Bhava Chalit house">Chalit</th>
          <th class="c" title="Ashtakavarga score of that sign (28+ strong)">SAV</th><th>Natal contact</th></tr></thead><tbody>${rows}</tbody></table></div>
        <p class="hint">Positions at ${esc(d.time)} (${esc(d.tz)}). House columns: from your lagna, from your Moon, and in the Bhava Chalit (cusp) chart.</p>
        <section id="trsig"></section>`;
      window.drawNorth(body.querySelector('#trchart'), d.lagna_index, byH);
    }

    const STATUS = { strong: 'good', open: 'good', not_now: 'mute', not_promised: 'warn' };
    const step = (ok, txt) => `<span class="evs ${ok ? 'ok' : 'no'}">${ok ? '✓' : '·'} ${txt}</span>`;
    const hl = (hs, t) => hs.map(h => `<i class="${t.houses_for.includes(h) ? 'hf' : t.houses_against.includes(h) ? 'ha' : ''}">${h}</i>`).join('') || '<i>—</i>';

    function paintEvents(e) {
      const box = body.querySelector('#trev'); if (!box) return;
      const live = e.ladder.filter(x => x.status === 'strong' || x.status === 'open');
      const rest = e.ladder.filter(x => x.status === 'not_now' || x.status === 'not_promised');
      const card = x => `<li class="ev ${x.status}"><details><summary>
          <span class="evt"><b>${esc(x.title)}</b><span class="badge ${STATUS[x.status]}">${esc(x.label)}</span></span>
          <span class="evsteps">${step(x.promise.ok, 'Promised')}${step(x.dasha.ok, x.dasha.verdict === 'strong' ? 'Strong dasha' : 'Dasha')}${x.trigger.ok ? '<span class="evs hint">Transit hint</span>' : ''}</span>
          <span class="evsum">${esc(x.summary)}</span>
          ${x.nature.length ? `<span class="evnat">${x.nature.map(esc).join(' ')}</span>` : ''}</summary>
          <ul class="evw">
            <li><b>Promise:</b> ${x.promise.cusp}th cusp sub lord ${esc(x.promise.sub_lord)} signifies houses ${x.promise.signifies.join(', ') || 'none'} → ${esc(x.promise.verdict)}. Needs ${x.houses_for.join(', ')}; against ${x.houses_against.join(', ')}.</li>
            <li><b>Dasha:</b> ${esc(x.dasha.lords || '—')} → ${esc(x.dasha.verdict || '—')}${x.dasha.until ? ` until ${fd(x.dasha.until)}` : ''}.</li>
            ${x.trigger.planets.map(t => `<li><b>Transit hint:</b> ${esc(t.planet)} ${esc(t.why)} — the classical KP trigger.</li>`).join('')}
            ${x.trigger.resting.map(pl => `<li class="evsup">${esc(pl)} would count, but it is retrograde or stationary — no trigger value until it moves direct (Taneja).</li>`).join('')}
            ${x.trigger.supporting.map(t => `<li class="evsup">Supporting: ${esc(t.planet)} ${esc(t.why)}.</li>`).join('')}
            ${x.trigger.sun ? '<li class="evsup">Sun: in a sign and star of your dasha lords — points to this month.</li>' : ''}
          </ul></details></li>`;
      box.innerHTML = `<h4 class="trh">Life events on ${fd(e.date)} <small>Promise → Dasha · transit hints</small></h4>
        ${live.length ? `<ol class="evl">${live.map(card).join('')}</ol>` : '<p class="hint">No life matter has a supportive dasha on this date.</p>'}
        ${rest.length ? `<p class="evrest"><b>Not now:</b> ${rest.map(x => `${esc(x.title)}${x.status === 'not_promised' ? ' (not clearly promised)' : x.next_window ? ` <span>(next ${fd(x.next_window.starts)} – ${fd(x.next_window.ends)})</span>` : ''}`).join(' · ')}</p>` : ''}
        <p class="hint">Nadi timing: the chart must promise it and the Dasa–Bhukti–Antar must support it — that is what decides the window. Transit hints (a slow planet in a sign, star and sub of your dasha lords) are classical, but in our tests on dated events they did not pin down dates, so treat them as hints. Tap a matter to see the working. Traditional guidance, not certainty.</p>`;
      if (!evTopic || !e.topics.includes(evTopic)) evTopic = (live[0] || e.ladder[0]).topic;
      paintSig(e);
    }

    function paintSig(e) {
      const box = body.querySelector('#trsig'); if (!box) return;
      const t = e.ladder.find(x => x.topic === evTopic);
      const V = { supports: ['ok', '✓ yes'], against: ['bad', '✗ no'], mixed: ['', 'mixed'], neutral: ['mute', '—'] };
      box.innerHTML = `<h4 class="trh">Transit significators <small>planet · star lord · sub lord</small></h4>
        <div class="kpt evchips" role="tablist">${e.topics.map(k => `<button type="button" role="tab" aria-selected="${k === evTopic}" class="${k === evTopic ? 'on' : ''}" data-ev="${k}">${esc(e.titles[k])}</button>`).join('')}</div>
        <div class="scroll"><table class="trtable evtable"><thead><tr><th>Transit</th><th>Star lord → houses</th><th>Sub lord → houses</th><th title="${esc(t.title)}">Gives?</th></tr></thead>
        <tbody>${e.rows.map(r => { const v = V[r.topics[evTopic]]; return `<tr><td><b>${r.planet}</b>${r.retrograde ? ' <span class="bd rt">R</span>' : ''}<small>in your ${ord(r.house)} · sign of ${r.sign_lord}</small><small>own ${hl(r.planet_houses, t)}</small></td>
          <td>${r.star_lord}<small>${hl(r.star_houses, t)}</small></td>
          <td>${r.sub_lord}<small>${hl(r.sub_houses, t)}</small></td><td><span class="${v[0]}">${v[1]}</span></td></tr>`; }).join('')}</tbody></table></div>
        <p class="hint">${esc(t.full_title)} needs houses <span class="hf">${t.houses_for.join(', ')}</span>; against <span class="ha">${t.houses_against.join(', ')}</span>. Each lord counts the natal houses it occupies and owns (Rahu/Ketu act for their sign lord and conjunctions). The star lord shows what a transit brings, the sub lord decides whether it delivers. A transit alone is not a prediction — it matters only inside a supportive dasha.</p>`;
    }
    body.addEventListener('click', ev => {
      const b = ev.target.closest('[data-ev]'); if (!b || !lastEv) return;
      evTopic = b.dataset.ev; paintSig(lastEv);
    });

    el.querySelector('.trbar').addEventListener('click', e => {
      const b = e.target.closest('.trb'); if (!b) return;
      day = b.dataset.today ? today : shift(day, +(b.dataset.d || 0), +(b.dataset.m || 0));
      load();
    });
    input.addEventListener('change', () => { if (input.value) { day = input.value; load(); } });
    el.addEventListener('keydown', e => {
      if (e.target === input) return;
      if (e.key === 'ArrowLeft' || e.key === 'ArrowRight') { day = shift(day, e.key === 'ArrowLeft' ? -1 : 1, 0); load(); }
    });
    load();
  };
})();
