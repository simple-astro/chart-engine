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
    let day = today, ctrl = null;
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
        <div class="trmain">
          <div><h4 class="trh">Transits over your chart</h4><div class="chart trchart" id="trchart"></div>
            <p class="hint">Houses counted from your ${esc(d.lagna_sign)} lagna. Highlighted planets run your daśā. R = retrograde.</p></div>
          <div><h4 class="trh">How it lines up with your chart</h4><ul class="trnotes">${notes}</ul></div>
        </div>
        <h4 class="trh">Planetary transits</h4>
        <div class="scroll"><table class="trtable"><thead><tr><th>Planet</th><th>Sign</th><th>Nakshatra · star/sub</th>
          <th class="c" title="House from your lagna">Lagna</th><th class="c" title="House from your Moon">Moon</th><th class="c" title="Nirayana Bhava Chalit house">Chalit</th>
          <th class="c" title="Ashtakavarga score of that sign (28+ strong)">SAV</th><th>Natal contact</th></tr></thead><tbody>${rows}</tbody></table></div>
        <p class="hint">Positions at ${esc(d.time)} (${esc(d.tz)}). House columns: from your lagna, from your Moon, and in the Bhava Chalit (cusp) chart.</p>`;
      window.drawNorth(body.querySelector('#trchart'), d.lagna_index, byH);
    }

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
