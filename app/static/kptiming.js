// KP Timing tab: promise and dasha windows for one life matter, with the star-lord/sub-lord reasoning.
(function () {
  const esc = s => String(s ?? '').replace(/[&<>"]/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));
  const TOPICS = [['career', 'Career'], ['marriage', 'Marriage'], ['money', 'Money'], ['property', 'Property'],
    ['foreign', 'Abroad'], ['children', 'Children'], ['education', 'Education'], ['health', 'Health'],
    ['love', 'Love'], ['litigation', 'Court case']];
  const BADGE = { strong: 'good', favourable: 'good', mixed: '', challenging: 'warn' };
  const PROMISE = { 'promised': 'good', 'promised with obstacles': '', 'not clearly promised': 'warn' };
  const fd = iso => new Date(iso + 'T12:00:00Z').toLocaleDateString([], { day: 'numeric', month: 'short', year: 'numeric', timeZone: 'UTC' });

  window.renderKpTiming = function (el, profileId) {
    if (profileId == null) { el.innerHTML = '<p class="hint">Save this chart to see KP timing.</p>'; return; }
    el.innerHTML = `<p class="sub">KP judges a matter in two steps: is it <b>promised</b> (the sub-lord of its main cusp), and
        <b>when</b> — a period lord gives the houses its star lord signifies, and its sub lord decides whether it delivers.
        Jupiter and Saturn transits act as the trigger.</p>
      <div class="kpt" role="tablist">${TOPICS.map(([k, n], i) => `<button type="button" role="tab" aria-selected="${!i}" class="${i ? '' : 'on'}" data-t="${k}">${n}</button>`).join('')}</div>
      <div id="kpbody" aria-live="polite"></div>`;
    const load = async topic => {
      const box = el.querySelector('#kpbody');
      box.innerHTML = '<p class="hint">Working out the KP timing…</p>';
      try {
        const r = await fetch(`/profiles/${profileId}/kp/${topic}?months=36`);
        const d = await r.json(); if (!r.ok) throw new Error(d.detail || r.statusText);
        const p = d.promise;
        box.innerHTML = `<div class="kpp"><div><small>Is it promised?</small><b>${esc(d.title)}</b></div>
            <span class="badge ${PROMISE[p.verdict]}">${esc(p.verdict)}</span></div>
          <p class="hint" style="margin-top:6px">${p.cusp}th cusp sub-lord <b>${esc(p.cusp_sub_lord)}</b> (star lord ${esc(p.csl_star_lord)})
            signifies houses ${p.signifies.join(', ')} — for: ${p.for.join(', ') || 'none'}; against: ${p.against.join(', ') || 'none'}.
            Houses for ${d.houses_for.join(', ')}, against ${d.houses_against.join(', ')}.</p>
          <ol class="kpw">${d.windows.map(w => `<li class="${w.verdict}"><details>
              <summary><span class="kpd">${fd(w.starts)} – ${fd(w.ends)}</span><span class="kpl">${esc(w.antar)} / ${esc(w.praty)}</span>
                <span class="badge ${BADGE[w.verdict]}">${esc(w.verdict)}</span></summary>
              <ul>${w.reasons.map(x => `<li>${esc(x)}</li>`).join('')}${w.transit.map(x => `<li class="kptr">Transit: ${esc(x)}</li>`).join('')}</ul>
            </details></li>`).join('')}</ol>
          <p class="hint">Mahadasha ${esc(d.windows[0] ? d.windows[0].maha : '')} throughout unless shown otherwise in the reasons.
            Scores weigh the antardasha most, then the pratyantar, then the mahadasha. Traditional guidance, not certainty.</p>`;
      } catch (e) { box.innerHTML = `<p class="hint err">Couldn’t load KP timing: ${esc(e.message)}</p>`; }
    };
    el.querySelector('.kpt').addEventListener('click', e => {
      const b = e.target.closest('[data-t]'); if (!b) return;
      el.querySelectorAll('.kpt button').forEach(x => { x.classList.toggle('on', x === b); x.setAttribute('aria-selected', String(x === b)); });
      load(b.dataset.t);
    });
    load('career');
  };
})();
