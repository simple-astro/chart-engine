// Match making: arrows between the two charts (core/match_links.py). Green supports, yellow is mixed, red needs care.
// Wide screens show every link with tap-to-focus; phones keep the charts side by side and step through one at a time.
(function () {
  const esc = s => String(s ?? '').replace(/[&<>"]/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));
  const NORTH = [[200, 95], [100, 45], [45, 100], [95, 200], [45, 300], [100, 355], [200, 305], [300, 355], [355, 300], [305, 200], [355, 100], [300, 45]];
  const SOUTH = [[1, 0], [2, 0], [3, 0], [3, 1], [3, 2], [3, 3], [2, 3], [1, 3], [0, 3], [0, 2], [0, 1], [0, 0]];  // by sign
  const KIND = { green: ['g', 'Supportive'], yellow: ['y', 'Mixed'], red: ['r', 'Needs care'] };
  const PH = 640;  // narrower than this: one link at a time
  let S = { data: null, view: 'd1', all: true, i: 0, show: { green: true, yellow: true, red: true }, phone: null };

  window.paintMatchLinks = function (data, view) {
    S.data = data; S.view = view;
    const grid = document.querySelector('.mmcgrid'), box = document.getElementById('mlinks');
    if (!grid || !box) return;
    // The match page draws the charts before it unhides the results: measure only once they are on screen.
    if (!grid.clientWidth) { if ((S.wait = (S.wait || 0) + 1) < 60) requestAnimationFrame(() => window.paintMatchLinks(data, view)); return; }
    S.wait = 0;
    const phone = grid.clientWidth < PH;
    if (phone !== S.phone) { S.phone = phone; S.all = !phone; S.i = 0; }
    paint();
  };

  function links() { const L = S.data && S.data.links && S.data.links[S.view]; return L ? L.links : []; }

  // The centre of a house in a drawn chart, in the grid's pixels.
  function point(who, house, grid) {
    const el = document.getElementById('mch-' + who), svg = el && el.querySelector('svg');
    if (!svg) return null;
    const g = grid.getBoundingClientRect(), r = svg.getBoundingClientRect(), k = r.width / 404;
    const lagna = S.data.charts[who][S.view].lagna;
    const [x, y] = svg.classList.contains('south') ? SOUTH[(lagna + house - 1) % 12].map(v => v * 100 + 50) : NORTH[house - 1];
    return { x: r.left - g.left + (x + 2) * k, y: r.top - g.top + (y + 2) * k, top: r.top - g.top, bottom: r.bottom - g.top, mid: r.top - g.top + r.height / 2 };
  }

  function curve(a, z, n) {
    const lo = Math.min(a.top, z.top), hi = Math.max(a.bottom, z.bottom), q = (hi - lo) / 4, mid = (a.mid + z.mid) / 2;
    const dx = z.x - a.x, dip = 26 + (n % 4) * 10;
    if (a.y > mid + q * .4 && z.y > mid + q * .4) {        // both low: swing below the charts
      const cy = Math.max(a.y, z.y) + dip + 30;
      return [a, { x: a.x + dx * .2, y: cy }, { x: a.x + dx * .8, y: cy }, z];
    }
    if (a.y < mid - q * .4 && z.y < mid - q * .4) {        // both high: over the top
      const cy = Math.max(-36, Math.min(a.y, z.y) - dip - 30);  // the grid keeps room above the charts
      return [a, { x: a.x + dx * .2, y: cy }, { x: a.x + dx * .8, y: cy }, z];
    }
    return [a, { x: a.x + dx * .45, y: a.y - dip }, { x: a.x + dx * .55, y: z.y - dip }, z];
  }
  const at = (c, t) => { const u = 1 - t; return { x: u * u * u * c[0].x + 3 * u * u * t * c[1].x + 3 * u * t * t * c[2].x + t * t * t * c[3].x,
    y: u * u * u * c[0].y + 3 * u * u * t * c[1].y + 3 * u * t * t * c[2].y + t * t * t * c[3].y }; };
  const d = c => `M${c[0].x.toFixed(1)} ${c[0].y.toFixed(1)} C ${c[1].x.toFixed(1)} ${c[1].y.toFixed(1)} ${c[2].x.toFixed(1)} ${c[2].y.toFixed(1)} ${c[3].x.toFixed(1)} ${c[3].y.toFixed(1)}`;

  function paint() {
    const grid = document.querySelector('.mmcgrid'), box = document.getElementById('mlinks');
    const L = links(), sum = S.data.links && S.data.links[S.view] && S.data.links[S.view].summary;
    grid.querySelector('.mlsvg')?.remove();
    if (!L.length) { box.innerHTML = '<p class="hint">No direct links between the two charts in this view.</p>'; grid.classList.remove('mlon'); return; }
    grid.classList.add('mlon');
    const sel = S.all ? null : L[Math.min(S.i, L.length - 1)];
    // arrows
    const W = grid.clientWidth, H = grid.clientHeight;
    let paths = '', badges = '', glow = '';
    L.forEach((l, k) => {
      const a = point(l.from.who, l.from.house, grid), z = point(l.to.who, l.to.house, grid);
      if (!a || !z) return;
      const c = curve(a, z, k), m = at(c, .5), K = KIND[l.kind][0], on = sel === l;
      const hidden = S.all ? !S.show[l.kind] : !on;
      if (hidden) return;
      const w = S.all ? (S.phone ? 1.6 : 2.6) : 3.6;
      paths += `<path class="mlp ml-${K}" d="${d(c)}" stroke-width="${w}" marker-end="url(#mlh-${K})"${l.from.planet === 'Moon' && l.to.planet === 'Moon' ? ` marker-start="url(#mlh-${K})"` : ''}/>` +
        `<path class="mlhit" d="${d(c)}" data-ml="${k}"><title>${esc(l.title)}</title></path>`;
      if (S.all) badges += `<g class="mlb ml-${K}" data-ml="${k}"><circle cx="${m.x.toFixed(1)}" cy="${m.y.toFixed(1)}" r="${S.phone ? 8 : 10}"/><text x="${m.x.toFixed(1)}" y="${(m.y + (S.phone ? 3 : 4)).toFixed(1)}">${l.n}</text></g>`;
      if (on) glow = `<circle class="mlg ml-${K}" cx="${a.x.toFixed(1)}" cy="${a.y.toFixed(1)}" r="${S.phone ? 16 : 24}"/><circle class="mlg ml-${K}" cx="${z.x.toFixed(1)}" cy="${z.y.toFixed(1)}" r="${S.phone ? 16 : 24}"/>`;
    });
    grid.insertAdjacentHTML('beforeend', `<svg class="mlsvg" width="${W}" height="${H}" viewBox="0 0 ${W} ${H}" aria-hidden="true">
      <defs>${['g', 'y', 'r'].map(K => `<marker id="mlh-${K}" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse"><path class="mlm ml-${K}" d="M0 0L10 5L0 10z"/></marker>`).join('')}</defs>
      ${glow}${paths}${badges}</svg>`);
    // the panel under the charts
    const c = sum ? sum.counts : { green: 0, yellow: 0, red: 0 };
    const chip = k => `<button type="button" class="mlchip" data-mlk="${k}" aria-pressed="${S.show[k]}"><i class="ml-${KIND[k][0]}"></i>${KIND[k][1]} · ${c[k]}</button>`;
    const card = sel ? `<section class="mlcard ml-${KIND[sel.kind][0]}"><span class="mln">${sel.n}</span><div><small>${KIND[sel.kind][1]}</small><b>${esc(sel.title)}</b><p>${esc(sel.text)}</p><small class="mlwhy">${esc(sel.why)}</small></div></section>` : '';
    const step = S.phone || sel ? `<div class="mlstep"><button type="button" class="mlnav" data-mlgo="-1" aria-label="Previous link">‹</button>
        <div><span>${sel ? `${L.indexOf(sel) + 1} of ${L.length}` : `All ${L.length} links`}</span><span class="mldots">${L.map((l, k) => `<i class="ml-${KIND[l.kind][0]}${sel === l ? ' on' : ''}"></i>`).join('')}</span></div>
        <button type="button" class="mlnav" data-mlgo="1" aria-label="Next link">›</button>
        <button type="button" class="mlall" data-mlall aria-pressed="${!sel}">All</button></div>` : '';
    box.innerHTML = (sum ? `<p class="mlsum">${esc(sum.text)}</p>` : '') +
      (S.all ? `<div class="mlchips" role="group" aria-label="Show">${chip('green')}${chip('yellow')}${chip('red')}</div>` : '') + step + card +
      `<ol class="mllist">${L.map((l, k) => `<li><button type="button" data-ml="${k}" aria-pressed="${sel === l}" class="ml-${KIND[l.kind][0]}${S.all && !S.show[l.kind] ? ' off' : ''}">
        <span class="mln ml-${KIND[l.kind][0]}">${l.n}</span><span><b>${esc(l.title)}</b><small>${esc(l.text)}</small></span></button></li>`).join('')}</ol>
      <p class="hint">Lines join a planet in one chart to the house or planet it touches in the other: solid green helps, dashed yellow is mixed, dotted red needs care. Tendencies, not verdicts.</p>`;
  }

  document.addEventListener('click', e => {
    if (!S.data || !e.target.closest('.mmcharts')) return;
    const L = links();
    const m = e.target.closest('[data-ml]');
    if (m) { const k = +m.dataset.ml; if (!S.all && S.i === k && !S.phone) S.all = true; else { S.all = false; S.i = k; } paint(); return; }
    const g = e.target.closest('[data-mlgo]');
    if (g) { S.i = S.all ? 0 : (S.i + +g.dataset.mlgo + L.length) % L.length; S.all = false; paint(); return; }
    if (e.target.closest('[data-mlall]')) { S.all = !S.all; paint(); return; }
    const k = e.target.closest('[data-mlk]');
    if (k) { S.show[k.dataset.mlk] = !S.show[k.dataset.mlk]; paint(); }
  });
  let rz; addEventListener('resize', () => { clearTimeout(rz); rz = setTimeout(() => { if (S.data && document.querySelector('.mmcgrid')) window.paintMatchLinks(S.data, S.view); }, 150); });
})();
