// Lord Exchange and Ashtakavarga tabs, built from the extras on the /chart response.
(function () {
  const SIGNS = ['Aries', 'Taurus', 'Gemini', 'Cancer', 'Leo', 'Virgo', 'Libra', 'Scorpio', 'Sagittarius', 'Capricorn', 'Aquarius', 'Pisces'];
  const SAB = ['Ari', 'Tau', 'Gem', 'Can', 'Leo', 'Vir', 'Lib', 'Sco', 'Sag', 'Cap', 'Aqu', 'Pis'];
  const THEME = ['', 'self & health', 'wealth & family', 'courage & siblings', 'home & mother', 'children & intellect',
    'health, debts & rivals', 'marriage & partners', 'sudden change & longevity', 'luck & dharma', 'career & status',
    'gains & friends', 'expenses & foreign lands'];
  const PL = ['Sun', 'Moon', 'Mars', 'Mercury', 'Jupiter', 'Venus', 'Saturn'];
  const esc = s => String(s ?? '').replace(/[&<>"]/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));
  const ord = n => n + (n % 100 >= 11 && n % 100 <= 13 ? 'th' : { 1: 'st', 2: 'nd', 3: 'rd' }[n % 10] || 'th');
  const GOOD = [1, 4, 5, 7, 9, 10], DUS = [6, 8, 12];

  const TYPE = {
    Maha: ['good', 'Maha parivartana', 'A strong, helpful exchange. Each house protects the other, and both areas of life tend to grow together.'],
    Khala: ['', 'Khala parivartana', 'A mixed exchange through the 3rd house. Results come through your own effort and courage, sometimes in fits and starts.'],
    Dainya: ['warn', 'Dainya parivartana', 'An exchange with a 6th, 8th or 12th house. These areas can bring struggle at first, but the link often turns a difficulty into strength later.'],
  };

  function exchangeCard(x, chartName) {
    const [a, b] = x.planets, [ha, hb] = x.houses, t = TYPE[x.type];
    return `<div class="xcard"><div class="xhead"><span class="xpl">${a}</span><span class="xarrow" aria-hidden="true">⇄</span><span class="xpl">${b}</span>
        <span class="badge ${t[0]}">${t[1]}</span></div>
      <p><b>${a}</b> sits in ${b}’s sign (${SIGNS[x.signs[0]]}, your ${ord(ha)} house) and <b>${b}</b> sits in ${a}’s sign (${SIGNS[x.signs[1]]}, your ${ord(hb)} house).
        This ties your <b>${THEME[ha]}</b> (${ord(ha)}) to your <b>${THEME[hb]}</b> (${ord(hb)}) — what happens in one shows up in the other.</p>
      <p class="hint" style="margin:0">${t[2]}${chartName === 'D9' ? ' In the Navamsa it shows mainly in marriage and in how the planets mature after about age 35.' : ''}</p></div>`;
  }

  window.renderExchange = function (el, c) {
    const ex = c.exchanges || {}, d1 = ex.D1 || [], d9 = ex.D9 || [];
    const lords = c.lords || [];
    const vip = lords.filter(r => DUS.includes(r.house) && DUS.includes(r.lord_in) && r.house !== r.lord_in);
    const rows = lords.map(r => {
      const own = r.house === r.lord_in, v = vip.includes(r);
      const tag = own ? '<span class="badge good">In own house</span>'
        : v ? '<span class="badge good">Viparita</span>'
          : DUS.includes(r.lord_in) && !DUS.includes(r.house) ? '<span class="badge warn">Needs care</span>'
            : GOOD.includes(r.lord_in) ? '<span class="badge good">Supportive</span>' : '';
      const swap = d1.find(x => x.planets.includes(r.lord));
      return [`<b>${ord(r.house)}</b> <small>${esc(THEME[r.house])}</small>`, SIGNS[r.sign_index], r.lord,
        `<span class="xflow">H${r.house} → <b>H${r.lord_in}</b></span>${swap ? ' <span class="xarrow sm" title="Part of a lord exchange">⇄</span>' : ''}`,
        own ? 'Strong hold over its own house.' : `${esc(THEME[r.house])} is shaped by ${esc(THEME[r.lord_in])}.`, tag];
    });
    el.innerHTML = `<p class="sub">A <b>lord exchange</b> (Parivartana yoga) happens when two planets sit in each other’s signs — like two people swapping homes.
        The houses they rule become tightly linked, and each planet acts almost as if it were in its own sign.</p>
      <h3 class="mh3">Rasi chart (D1)</h3>
      ${d1.length ? d1.map(x => exchangeCard(x, 'D1')).join('') : `<div class="xcard xnone"><b>No lord exchange in your birth chart.</b>
        <p class="hint" style="margin:6px 0 0">That is normal — most charts don’t have one. Your houses work through where each lord sits, shown below.</p></div>`}
      <h3 class="mh3">Navamsa (D9)</h3>
      ${d9.length ? d9.map(x => exchangeCard(x, 'D9')).join('') : '<p class="hint">No lord exchange in the Navamsa.</p>'}
      ${vip.length ? `<div class="callout"><b>Viparita Raja yoga:</b> ${vip.map(r => `the ${ord(r.house)} lord ${r.lord} sits in the ${ord(r.lord_in)}`).join('; ')}.
        When lords of difficult houses fall in other difficult houses, troubles tend to cancel out — often bringing success after a setback.</div>` : ''}
      <h3 class="mh3">Where your house lords sit</h3>
      <div class="scroll"><table class="xtable" id="xtable"></table></div>
      <p class="hint">Lords in the 1st, 4th, 5th, 7th, 9th or 10th support their house. A lord in the 6th, 8th or 12th asks for more care with that area — unless it is itself a 6th, 8th or 12th lord.</p>`;
    window.table($('xtable'), ['House', 'Sign', 'Lord', 'Lord sits in', 'What it means', ''], rows);
  };

  const level = v => v >= 28 ? ['strong', 'Strong'] : v >= 25 ? ['avg', 'Average'] : ['weak', 'Needs support'];
  const pstrength = v => v >= 5 ? ['good', 'Strong'] : v === 4 ? ['', 'Average'] : ['warn', 'Weak'];

  window.renderAshtakavarga = function (el, c) {
    const a = c.ashtakavarga; if (!a) { el.innerHTML = '<div class="hint">Ashtakavarga is not available for this chart.</div>'; return; }
    const L = c.lagna.sign_index, sgn = h => (L + h - 1) % 12;
    const byH = Array.from({ length: 12 }, (_, i) => a.sav[sgn(i + 1)]);
    const max = Math.max(40, ...byH) * 1.12, best = byH.indexOf(Math.max(...byH)) + 1, worst = byH.indexOf(Math.min(...byH)) + 1;
    const strong = byH.map((v, i) => [i + 1, v]).filter(([, v]) => v >= 28), weak = byH.map((v, i) => [i + 1, v]).filter(([, v]) => v < 25);
    const pHouse = p => (c.grahas[p].sign_index - L + 12) % 12 + 1;

    const bars = byH.map((v, i) => {
      const [k, lab] = level(v), h = i + 1;
      return `<div class="akb" tabindex="0" data-tip="<b>${ord(h)} house · ${SIGNS[sgn(h)]}</b><small>${esc(THEME[h])}</small><small>${v} bindus — ${lab}</small>">
        <span class="akv">${v}</span><i class="${k}" style="height:${v / max * 100}%"></i></div>`;
    }).join('');
    const labels = byH.map((_, i) => `<span>H${i + 1}<small>${SAB[sgn(i + 1)]}</small></span>`).join('');

    const heat = v => `background:color-mix(in srgb,var(--acc) ${Math.round(v / 8 * 52)}%,transparent)`;
    const head = '<thead><tr><th>Planet</th>' + Array.from({ length: 12 }, (_, i) => `<th>H${i + 1}<small>${SAB[sgn(i + 1)]}</small></th>`).join('') + '<th>Total</th></tr></thead>';
    const body = PL.map(p => '<tr><td><b>' + p + '</b></td>' + Array.from({ length: 12 }, (_, i) => {
      const s = sgn(i + 1), v = a.bav[p][s], here = c.grahas[p].sign_index === s;
      return `<td class="${here ? 'here' : ''}" style="${heat(v)}" title="${p}: ${v} of 8 in the ${ord(i + 1)} house${here ? ' (where it sits)' : ''}">${v}</td>`;
    }).join('') + `<td><b>${a.bav_totals[p]}</b></td></tr>`).join('') +
      '<tr class="sav"><td><b>Total (SAV)</b></td>' + byH.map(v => `<td class="${level(v)[0]}"><b>${v}</b></td>`).join('') + `<td><b>${a.sav_total}</b></td></tr>`;

    const chips = PL.map(p => {
      const v = a.own_bindus[p], [k, lab] = pstrength(v);
      return `<div class="akp"><b>${p}</b><span class="akd">${'●'.repeat(v)}<span>${'●'.repeat(8 - v)}</span></span><small>${v}/8 in ${ord(pHouse(p))} house</small><span class="badge ${k}">${lab}</span></div>`;
    }).join('');

    el.innerHTML = `<p class="sub"><b>Ashtakavarga</b> gives each house a score from eight sources — the seven planets and your lagna.
        Above <b>28</b> a house is strong and gives good results easily; below <b>25</b> it needs more effort.</p>
      <div class="stats" style="margin-bottom:6px"><div class="stat"><small>Strongest house</small><b>${ord(best)} · ${byH[best - 1]}</b><em>${esc(THEME[best])}</em></div>
        <div class="stat"><small>Weakest house</small><b>${ord(worst)} · ${byH[worst - 1]}</b><em>${esc(THEME[worst])}</em></div>
        <div class="stat"><small>Strong houses</small><b>${strong.length} of 12</b><em>28 or more</em></div></div>
      <h3 class="mh3">House scores (Sarvashtakavarga)</h3>
      <div class="akchart" aria-label="Sarvashtakavarga score for each house">
        <div class="akplot"><div class="akref" style="bottom:${28 / max * 100}%"><span>28</span></div>${bars}</div>
        <div class="aklabels">${labels}</div></div>
      <div class="tl-legend"><span><i class="aksw strong"></i>Strong (28+)</span><span><i class="aksw avg"></i>Average (25–27)</span><span><i class="aksw weak"></i>Needs support (under 25)</span></div>
      <div class="twocol mtimes">
        <div><h4 class="ok">Strong houses</h4><ul>${strong.length ? strong.map(([h, v]) => `<li><b>${ord(h)}</b> (${v}) — ${esc(THEME[h])}</li>`).join('') : '<li><small>None above 28.</small></li>'}</ul></div>
        <div><h4 class="bad">Houses that need support</h4><ul>${weak.length ? weak.map(([h, v]) => `<li><b>${ord(h)}</b> (${v}) — ${esc(THEME[h])}</li>`).join('') : '<li><small>None below 25.</small></li>'}</ul></div>
      </div>
      <p class="hint">Timing tip: when Saturn or Jupiter move through a strong house, that area of life usually improves; through a weak one, go slower.</p>
      <h3 class="mh3">Planet strength (bindus where each planet sits)</h3>
      <div class="akps">${chips}</div>
      <p class="hint">5 or more of 8 means the planet gives its results well in its daśā and transits; 3 or fewer means it needs support.</p>
      <h3 class="mh3">Full table (Bhinnashtakavarga)</h3>
      <div class="scroll"><table class="aktable">${head}<tbody>${body}</tbody></table></div>
      <p class="hint">Each planet’s row scores the houses out of 8. The outlined cell is where that planet sits.</p>`;

    const box = el.querySelector('.akchart'), tip = document.createElement('div');
    tip.className = 'ctip'; tip.hidden = true; box.appendChild(tip);
    const show = b => {
      if (!b) { tip.hidden = true; return; }
      tip.innerHTML = b.dataset.tip; tip.hidden = false; tip.classList.remove('below');
      const r = b.getBoundingClientRect(), cr = box.getBoundingClientRect(), bar = b.querySelector('i').getBoundingClientRect();
      tip.style.left = Math.min(Math.max(r.left + r.width / 2 - cr.left, 90), cr.width - 90) + 'px';
      tip.style.top = (bar.top - cr.top) + 'px';
    };
    box.addEventListener('pointerover', e => show(e.target.closest('.akb')));
    box.addEventListener('pointerleave', () => show(null));
    box.addEventListener('focusin', e => show(e.target.closest('.akb')));
    box.addEventListener('focusout', () => show(null));
  };
})();
