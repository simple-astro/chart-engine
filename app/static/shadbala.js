// Shadbala and Bhava Bala (My Charts › Shadbala), from /shadbala. For study: readings don't use it.
(function () {
  const esc = s => String(s ?? '').replace(/[&<>"]/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));
  const P = ['Sun', 'Moon', 'Mars', 'Mercury', 'Jupiter', 'Venus', 'Saturn'];
  const AB = { Sun: 'Sun', Moon: 'Mon', Mars: 'Mar', Mercury: 'Mer', Jupiter: 'Jup', Venus: 'Ven', Saturn: 'Sat' };
  const ROMAN = ['I', 'II', 'III', 'IV', 'V', 'VI', 'VII', 'VIII', 'IX', 'X', 'XI', 'XII'];
  const f = (x, d = 2) => (Math.round(x * 10 ** d) / 10 ** d).toFixed(d);
  let S = { req: null, data: null };

  // One fetch serves both the graphs (My Charts › Graphs) and the tables (My Charts › Vedic › Shadbala).
  async function load(el, req) {
    if (!req) return false;
    if (S.req === req && S.data) return true;
    S = { req, data: null };
    el.innerHTML = '<div class="hint">Working out the six strengths…</div>';
    try {
      const r = await fetch('/shadbala', { method: 'POST', headers: { 'content-type': 'application/json' }, body: JSON.stringify(req) });
      const d = await r.json();
      if (!r.ok) throw new Error(window.apiErr(d.detail) || r.statusText);
      if (S.req !== req) return false;
      S.data = d; return true;
    } catch (e) { el.innerHTML = `<p class="err">Couldn’t work out Shadbala: ${esc(e.message)}</p>`; return false; }
  }
  window.renderShadbala = async function (el, req) { if (await load(el, req)) paint(el); };
  window.renderShadbalaGraphs = async function (el, req) { if (await load(el, req)) paintGraphs(el); };

  function bars(items, max, mark) {
    return `<div class="sbb">${items.map(it => `<div class="sbb-c" title="${esc(it.title)}">
        <b>${esc(it.value)}</b><div class="sbb-t"><i class="${it.cls || ''}" style="height:${Math.max(2, Math.round(it.n / max * 100))}%"></i>
        ${mark ? `<span class="sbb-m" style="bottom:${Math.round(it.need / max * 100)}%"></span>` : ''}</div><small>${esc(it.label)}</small></div>`).join('')}</div>`;
  }
  const row = (label, vals, cls) => `<tr class="${cls || ''}"><th scope="row">${label}</th>${vals.map(v => `<td>${v}</td>`).join('')}</tr>`;

  function paintGraphs(el) {
    const d = S.data, pl = d.planets;
    const maxP = Math.max(...P.map(p => pl[p].rupas), ...P.map(p => pl[p].required)) * 1.08;
    const pbars = bars(P.map(p => ({ n: pl[p].rupas, need: pl[p].required, value: f(pl[p].rupas), label: AB[p],
      cls: pl[p].ratio >= 1 ? 'ok' : 'low', title: `${p}: ${f(pl[p].rupas)} rupas, needs ${pl[p].required} (${f(pl[p].ratio)}×), rank ${pl[p].rank}` })), maxP, true);
    const maxB = Math.max(...d.bhavas.map(b => b.rupas)) * 1.08;
    const bbars = bars(d.bhavas.map(b => ({ n: b.rupas, value: f(b.rupas, 1), label: String(b.house), cls: b.rank <= 3 ? 'ok' : b.rank >= 10 ? 'low' : '',
      title: `House ${b.house} (lord ${b.lord}): ${f(b.rupas, 1)} rupas, rank ${b.rank}` })), maxB, false);
    const strongest = [...P].sort((a, b) => pl[a].rank - pl[b].rank);
    const below = P.filter(p => pl[p].ratio < 1);
    el.innerHTML = `<section class="card gcard sbal">
      <h3>Planet strength <small>Shadbala</small> <span class="badge">For study only</span></h3>
      <p class="sbal-sum">Strongest: <b>${strongest.slice(0, 2).join(' and ')}</b>. ${below.length ? `Below the minimum: <b>${below.join(', ')}</b>.` : 'Every planet meets its minimum.'}</p>
      ${pbars}
      <p class="hint">Rupas (60 virupas = 1 rupa). The dashed line on each bar is the classical minimum the planet needs to give its results with ease.</p>
      <button type="button" class="linkbtn" data-goto="shadbala">See every component →</button>
    </section>
    <section class="card gcard sbal">
      <h3>House strength <small>Bhava Bala</small></h3>
      ${bbars}
      <p class="hint">Houses 1 to 12, in rupas. The three strongest are green, the three weakest red.</p>
    </section>`;
  }

  function paint(el) {
    const d = S.data, pl = d.planets;
    const v = (fn, dd) => P.map(p => f(fn(pl[p]), dd));
    const st = k => v(x => x.sthana[k]), kl = k => v(x => x.kala[k]);
    el.innerHTML = `<section class="card gcard sbal">
      <h3>Shadbala <small>six-fold planet strength</small> <span class="badge">For study only</span></h3>
      <button type="button" class="linkbtn" data-goto="graphs">See the graphs →</button>
      <details class="sbal-det" open><summary>All components (virupas)</summary><div class="scroll"><table class="sbal-t">
        <thead><tr><th></th>${P.map(p => `<th>${AB[p]}</th>`).join('')}</tr></thead><tbody>
        ${row('Uchcha', st('uchcha'))}${row('Saptavarga', st('saptavarga'))}${row('Ojayugma', st('ojayugma'))}${row('Kendra', st('kendra'))}${row('Drekkana', st('drekkana'))}
        ${row('1. Sthana Bala', st('total'), 'tot')}${row('2. Dig Bala', v(x => x.dig), 'tot')}
        ${row('Nathonnatha', kl('nathonnatha'))}${row('Paksha', kl('paksha'))}${row('Tribhaga', kl('tribhaga'))}${row('Abda', kl('abda'))}${row('Masa', kl('masa'))}
        ${row('Vara', kl('vara'))}${row('Hora', kl('hora'))}${row('Ayana', kl('ayana'))}${row('Yuddha', kl('yuddha'))}
        ${row('3. Kala Bala', kl('total'), 'tot')}${row('4. Cheshta Bala', v(x => x.cheshta), 'tot')}${row('5. Naisargika Bala', v(x => x.naisargika), 'tot')}${row('6. Drik Bala', v(x => x.drik), 'tot')}
        ${row('Total Shadbala', v(x => x.total), 'grand')}${row('In rupas', v(x => x.rupas))}${row('Minimum (rupas)', v(x => x.required))}${row('Ratio', v(x => x.ratio))}
        ${row('Rank', P.map(p => pl[p].rank))}${row('Ishta Phala', v(x => x.ishta))}${row('Kashta Phala', v(x => x.kashta))}
      </tbody></table></div></details>
    </section>
    <section class="card gcard sbal">
      <h3>Bhava Bala <small>house strength</small></h3>
      <details class="sbal-det" open><summary>All components (virupas)</summary><div class="scroll"><table class="sbal-t">
        <thead><tr><th></th>${d.bhavas.map(b => `<th>${ROMAN[b.house - 1]}</th>`).join('')}</tr></thead><tbody>
        ${row('Lord', d.bhavas.map(b => AB[b.lord]))}${row('Adhipati', d.bhavas.map(b => f(b.adhipati, 1)))}${row('Dig', d.bhavas.map(b => f(b.dig, 1)))}
        ${row('Drishti', d.bhavas.map(b => f(b.drishti, 1)))}${row('Total', d.bhavas.map(b => f(b.total, 1)), 'grand')}
        ${row('In rupas', d.bhavas.map(b => f(b.rupas, 1)))}${row('Rank', d.bhavas.map(b => b.rank))}
      </tbody></table></div></details>
      ${d.wars.length ? `<p class="hint"><b>Planetary war:</b> ${d.wars.map(w => `${esc(w.planets.join(' and '))} — ${esc(w.winner)} wins (${f(w.bala)} virupas)`).join('; ')}.</p>` : ''}
      <details class="chrules"><summary>How we work this out</summary>
        <p>Brihat Parashara Hora Shastra ch. 27–28, with the KP ayanamsha and Sripati (Porphyry) house cusps, checked against a desktop program’s printouts. Where that program differs from the text we follow the text; for a birth after midnight but before sunrise we keep the calendar weekday, as that program does.</p>
        <p>Shown for study: our tests on dated life events found planet self-strength did not improve timing, so readings don’t use it yet.</p></details>
    </section>`;
  }
})();
