// Chart image for Reddit: one dense image to post on r/vedicastrology and similar groups. D1 with every degree, the D9,
// key lords, a chart key, the planet table and the Vimshottari tables, drawn on a canvas (North or South Indian, tall
// or wide). Birth details are hidden unless the person turns them on. "Copy for Reddit" gives a title and a text post
// with Markdown tables, which Reddit shows as real tables.
(function () {
  const SIGNS = ['Aries', 'Taurus', 'Gemini', 'Cancer', 'Leo', 'Virgo', 'Libra', 'Scorpio', 'Sagittarius', 'Capricorn', 'Aquarius', 'Pisces'];
  const SAB = ['Ari', 'Tau', 'Gem', 'Can', 'Leo', 'Vir', 'Lib', 'Sco', 'Sag', 'Cap', 'Aqu', 'Pis'];
  const LORD = ['Mars', 'Venus', 'Mercury', 'Moon', 'Sun', 'Mercury', 'Venus', 'Mars', 'Jupiter', 'Saturn', 'Saturn', 'Jupiter'];
  const P9 = ['Sun', 'Moon', 'Mars', 'Mercury', 'Jupiter', 'Venus', 'Saturn', 'Rahu', 'Ketu'];
  const AB = {Sun: 'Su', Moon: 'Mo', Mars: 'Ma', Mercury: 'Me', Jupiter: 'Ju', Venus: 'Ve', Saturn: 'Sa', Rahu: 'Ra', Ketu: 'Ke'};
  const COL = {Sun: '#b85600', Moon: '#5b6675', Mars: '#c0271b', Mercury: '#17803f', Jupiter: '#8f6a00', Venus: '#b8307f',
    Saturn: '#2f5bd3', Rahu: '#4f5560', Ketu: '#8a5a32'};
  const NAK = ['Ashwini', 'Bharani', 'Krittika', 'Rohini', 'Mrigashira', 'Ardra', 'Punarvasu', 'Pushya', 'Ashlesha', 'Magha',
    'P. Phalguni', 'U. Phalguni', 'Hasta', 'Chitra', 'Swati', 'Vishakha', 'Anuradha', 'Jyeshtha', 'Mula', 'P. Ashadha',
    'U. Ashadha', 'Shravana', 'Dhanishta', 'Shatabhisha', 'P. Bhadrapada', 'U. Bhadrapada', 'Revati'];
  const short = n => (n || '').replace('Purva ', 'P. ').replace('Uttara ', 'U. ');
  // dignity by sign: the same rules as insights.js and core/dignity.py
  const EXALT = {Sun: 0, Moon: 1, Mars: 9, Mercury: 5, Jupiter: 3, Venus: 11, Saturn: 6};
  const FRIENDS = {Sun: ['Moon', 'Mars', 'Jupiter'], Moon: ['Sun', 'Mercury'], Mars: ['Sun', 'Moon', 'Jupiter'], Mercury: ['Sun', 'Venus'],
    Jupiter: ['Sun', 'Moon', 'Mars'], Venus: ['Mercury', 'Saturn'], Saturn: ['Mercury', 'Venus']};
  const ENEMIES = {Sun: ['Venus', 'Saturn'], Moon: [], Mars: ['Mercury'], Mercury: ['Moon'], Jupiter: ['Mercury', 'Venus'],
    Venus: ['Sun', 'Moon'], Saturn: ['Sun', 'Moon', 'Mars']};
  const DAY_LORD = {Sunday: 'Sun', Monday: 'Moon', Tuesday: 'Mars', Wednesday: 'Mercury', Thursday: 'Jupiter', Friday: 'Venus', Saturday: 'Saturn'};
  const AYS = {krishnamurti: 'KP', lahiri: 'Lahiri', pushya: 'Pushya', raman: 'Raman', fagan: 'Fagan-Bradley', tropical: 'Tropical'};
  function dignity(p, s) {
    if (!(p in EXALT)) return '';
    if (EXALT[p] === s) return 'Exalted';
    if ((EXALT[p] + 6) % 12 === s) return 'Debilitated';
    const l = LORD[s];
    return l === p ? 'Own' : FRIENDS[p].includes(l) ? 'Friend' : ENEMIES[p].includes(l) ? 'Enemy' : 'Neutral';
  }
  const DIG_COL = {Exalted: '#17803f', Own: '#17803f', Debilitated: '#c0271b', Enemy: '#9a4a12'};
  const dm = x => { let d = Math.floor(x), m = Math.round((x - d) * 60); if (m === 60) { d++; m = 0 } return String(d).padStart(2, '0') + '°' + String(m).padStart(2, '0') + '′' };
  const MON = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
  const my = iso => { const d = new Date(iso); return MON[d.getMonth()] + ' ' + d.getFullYear() };
  const isNow = (d, now) => now >= new Date(d.start) && now < new Date(d.end);
  const ordinal = n => n + (n === 1 ? 'st' : n === 2 ? 'nd' : n === 3 ? 'rd' : 'th');

  // Everything the image and the post show, worked out once from the /chart response.
  function facts(c, req, bx) {
    const l = c.lagna, L = l.sign_index, now = Date.now(), house = s => (s - L + 12) % 12 + 1;
    const kar = {};
    ((c.jaimini && c.jaimini.karakas) || []).forEach(k => { kar[k.planet] = k.short });
    const D9 = c.vargas && c.vargas.D9, L9 = c.varga_lagna && c.varga_lagna.D9;
    const lagNak = Math.floor(l.ascendant / (360 / 27)) % 27, lagPada = Math.floor((l.ascendant % (360 / 27)) / (360 / 108)) + 1;
    const planets = P9.map(p => {
      const g = c.grahas[p], dg = dignity(p, g.sign_index), node = p === 'Rahu' || p === 'Ketu';
      const marks = (dg === 'Exalted' ? '↑' : dg === 'Debilitated' ? '↓' : '') + (g.retrograde && !node ? 'ᴿ' : '') + (g.combust ? 'ᶜ' : '');
      return {p, g, dg, marks, house: house(g.sign_index), nl: g.nakshatra_lord, d9: D9 && D9[p] ? D9[p].sign_index : null, kar: kar[p] || ''};
    });
    const md = (c.dasha || []).find(d => isNow(d, now)), ad = md && (md.children || []).find(d => isNow(d, now));
    const day = bx && bx.avakhada ? ((bx.avakhada.rows.find(r => r.label === 'Birth day (Vedic)') || {}).value || '').split(' ')[0] : '';
    const lordOf = h => LORD[(L + h - 1) % 12], where = p => house(c.grahas[p].sign_index);
    const keyLords = [['Lagna', 1], ['7th', 7], ['9th', 9], ['10th', 10], ['12th', 12]].map(([of, h]) => [of, lordOf(h), where(lordOf(h))]);
    const ml = LORD[c.grahas.Moon.sign_index];
    keyLords.splice(4, 0, ['Moon sign', ml, where(ml)]);
    return {c, req, l, L, planets, md, ad, D9, L9, day, keyLords, lagNak: NAK[lagNak] + ' ' + lagPada,
      ay: AYS[c.meta.ayanamsha] || c.meta.ayanamsha};
  }

  // ---------- drawing ----------
  const BG = '#fbf7ef', CARD = '#fffdf9', INK = '#1f1a14', MUT = '#6b5a43', ACC = '#a8701f', GOLD = '#c9a868', LINE = '#dccba8',
    HEAD = '#ead8b2', ZEB = '#f6eedd', NOW = '#f2d58e', BAR = '#c98f2e', NUM = '#9c8a6c', SOFT = '#f6ecd6';
  const SANS = 'system-ui,-apple-system,"Segoe UI",Roboto,sans-serif', SER = 'Georgia,"Times New Roman",serif';
  function pen(x) {
    const T = (t, X, Y, o = {}) => {
      x.font = o.f || ('400 24px ' + SANS); x.fillStyle = o.c || INK; x.textAlign = o.a || 'left'; x.textBaseline = o.b || 'alphabetic';
      let s = String(t);
      if (o.mw) { while (s.length > 1 && x.measureText(s).width > o.mw) s = s.slice(0, -1); if (s !== String(t)) s = s.slice(0, -1) + '…' }
      x.fillText(s, X, Y);
    };
    const R = (X, Y, w, h, f) => { x.fillStyle = f; x.fillRect(X, Y, w, h) };
    const Ln = (a, b, c2, d, col, w) => { x.strokeStyle = col; x.lineWidth = w; x.beginPath(); x.moveTo(a, b); x.lineTo(c2, d); x.stroke() };
    return {T, R, Ln};
  }

  // A bordered table: optional gold title bar, a header row, zebra rows. Returns the y below it.
  function table(x, X, Y, widths, head, rows, o) {
    const {T, R, Ln} = pen(x), W = widths.reduce((a, b) => a + b, 0), rh = o.rh, fs = o.fs, pad = Math.round(fs * 0.45);
    let y = Y;
    if (o.title) { R(X, y, W, rh, BAR); T(o.title, X + pad, y + rh / 2, {f: '700 ' + Math.round(fs * 0.86) + 'px ' + SANS, c: '#fffdf9', b: 'middle', mw: W - 2 * pad}); y += rh }
    const top = y;
    if (head) {
      R(X, y, W, rh, HEAD);
      let cx = X;
      head.forEach((h, i) => { T(h, cx + pad, y + rh / 2, {f: '700 ' + Math.round(fs * 0.8) + 'px ' + SANS, c: '#5a4524', b: 'middle', mw: widths[i] - 2 * pad}); cx += widths[i] });
      y += rh;
    }
    rows.forEach((r, ri) => {
      R(X, y, W, rh, r.bg || (ri % 2 ? ZEB : CARD));
      let cx2 = X;
      r.cells.forEach((cl, i) => {
        if (cl && cl.t !== '') {
          const al = cl.al || 'left', tx = al === 'center' ? cx2 + widths[i] / 2 : cx2 + pad;
          T(cl.t, tx, y + rh / 2 + 1, {f: (cl.w || (r.bold ? 700 : 400)) + ' ' + fs + 'px ' + SANS, c: cl.c || INK, a: al, b: 'middle', mw: widths[i] - 2 * pad});
        }
        cx2 += widths[i];
      });
      y += rh;
    });
    for (let yy = top + rh; yy < y; yy += rh) Ln(X, yy, X + W, yy, LINE, 1);
    let vx = X;
    widths.slice(0, -1).forEach(w => { vx += w; Ln(vx, top, vx, y, LINE, 1) });
    x.strokeStyle = GOLD; x.lineWidth = 1.5; x.strokeRect(X, o.title ? Y : top, W, y - (o.title ? Y : top));
    if (head) Ln(X, top + rh, X + W, top + rh, GOLD, 1.5);
    return y;
  }

  // North or South Indian chart. items[h] = [{t, c}] for house h (0 = lagna); small = no degrees (the D9).
  const NP = [[200, 95], [100, 38], [40, 100], [95, 200], [40, 300], [100, 362], [200, 305], [300, 362], [360, 300], [305, 200], [360, 100], [300, 38]];
  const NN = [[200, 178], [100, 92], [93, 100], [178, 200], [93, 300], [100, 306], [200, 222], [300, 306], [307, 300], [222, 200], [307, 100], [300, 92]];
  const SC = [[1, 0], [2, 0], [3, 0], [3, 1], [3, 2], [3, 3], [2, 3], [1, 3], [0, 3], [0, 2], [0, 1], [0, 0]];
  function kundli(x, X, Y, S, lag, items, style, small) {
    const {T, R, Ln} = pen(x), k = S / 400;
    x.save(); x.translate(X, Y);
    R(0, 0, S, S, CARD);
    const put = (cx, cy, list, tri, cell) => {
      const n = list.length; if (!n) return;
      let cols = 1, fs;
      if (style === 'south') { cols = n > 4 ? 2 : 1; fs = small ? (n > 4 ? 22 : 30) : n > 4 ? 13 : n > 3 ? 16 : n > 2 ? 18 : 20 }
      else if (tri === 'tb') { cols = n > 2 ? 2 : 1; fs = small ? (n > 2 ? 26 : 32) : n > 2 ? 15 : 19 }
      else if (tri === 'side') { cols = n > 4 ? 2 : 1; fs = small ? (n > 3 ? 26 : 32) : n > 4 ? 14 : n > 3 ? 17 : n > 2 ? 19 : 21 }
      else { cols = n > 4 ? 2 : 1; fs = small ? (n > 3 ? 26 : 32) : n > 4 ? 15 : n > 3 ? 19 : 21 }
      if (small && cols === 1 && n > 1 && style !== 'south' && tri !== 'side') cols = 2;
      const rows = Math.ceil(n / cols), lh = fs * 1.18, colW = small ? fs * 1.6 : fs * 4.1;
      list.forEach((it, i) => {
        const r = Math.floor(i / cols), ci = i % cols, ncol = Math.min(cols, n - r * cols);
        const px = cx + (ci - (ncol - 1) / 2) * colW, py = cy + (r - (rows - 1) / 2) * lh;
        T(it.t, px * k, py * k, {f: (it.asc ? 600 : 700) + ' ' + Math.round((it.asc ? fs * 0.9 : fs) * k) + 'px ' + SANS, c: it.c, a: 'center', b: 'middle'});
      });
    };
    if (style === 'south') {
      R(100 * k, 100 * k, 200 * k, 200 * k, SOFT);
      x.strokeStyle = GOLD; x.lineWidth = Math.max(1, 2 * k); x.beginPath();
      [100, 200, 300].forEach(v => { x.moveTo(0, v * k); x.lineTo(v === 200 ? 100 * k : S, v * k); x.moveTo(v * k, 0); x.lineTo(v * k, v === 200 ? 100 * k : S) });
      x.moveTo(300 * k, 200 * k); x.lineTo(S, 200 * k); x.moveTo(200 * k, 300 * k); x.lineTo(200 * k, S); x.stroke();
      for (let s = 0; s < 12; s++) {
        const [ci, cj] = SC[s], h = (s - lag + 12) % 12, ox = ci * 100, oy = cj * 100;
        if (h === 0) Ln(ox * k, (oy + 26) * k, (ox + 26) * k, oy * k, ACC, Math.max(1.5, 3 * k));
        T(SAB[s], (ox + 94) * k, (oy + 16) * k, {f: '400 ' + Math.round((small ? 20 : 14) * k) + 'px ' + SANS, c: NUM, a: 'right'});
        put(ox + 50, oy + 56, items[h] || [], 'sq');
      }
    } else {
      x.fillStyle = SOFT; x.beginPath(); x.moveTo(200 * k, 0); x.lineTo(300 * k, 100 * k); x.lineTo(200 * k, 200 * k); x.lineTo(100 * k, 100 * k); x.closePath(); x.fill();
      x.strokeStyle = GOLD; x.lineWidth = Math.max(1, 2 * k); x.beginPath();
      x.moveTo(0, 0); x.lineTo(S, S); x.moveTo(S, 0); x.lineTo(0, S);
      x.moveTo(200 * k, 0); x.lineTo(S, 200 * k); x.lineTo(200 * k, S); x.lineTo(0, 200 * k); x.closePath(); x.stroke();
      NP.forEach(([px, py], h) => {
        if (!small) T((lag + h) % 12 + 1, NN[h][0] * k, NN[h][1] * k + 5 * k, {f: '400 ' + Math.round(15 * k) + 'px ' + SANS, c: NUM, a: 'center'});
        const tri = [1, 5, 7, 11].includes(h) ? 'tb' : [2, 4, 8, 10].includes(h) ? 'side' : 'dia';
        put(px, py, items[h] || [], tri);
      });
    }
    x.strokeStyle = ACC; x.lineWidth = Math.max(1.5, 3 * k); x.strokeRect(0, 0, S, S);
    x.restore();
  }

  function d1Items(F) {
    const items = {0: [{t: 'Asc ' + Math.floor(F.l.ascendant % 30) + '°', c: ACC, asc: true}]};
    F.planets.forEach(q => { (items[q.house - 1] = items[q.house - 1] || []).push({t: AB[q.p] + ' ' + Math.floor(q.g.degrees_in_sign) + '°' + q.marks, c: COL[q.p]}) });
    return items;
  }
  function d9Items(F) {
    const items = {0: [{t: 'Asc', c: ACC, asc: true}]};
    F.planets.forEach(q => { if (q.d9 == null) return; const h = (q.d9 - F.L9 + 12) % 12; (items[h] = items[h] || []).push({t: AB[q.p], c: COL[q.p]}) });
    return items;
  }

  function header(x, F, X, Y, W, s, hide) {
    const {T, Ln} = pen(x), mo = F.c.grahas.Moon;
    T(F.l.sign + ' lagna ' + dm(F.l.ascendant % 30).replace(/^0/, ''), X, Y + 46 * s, {f: '700 ' + Math.round(46 * s) + 'px ' + SER, mw: W * 0.62});
    const bits = [F.lagNak, 'Rasi ' + mo.sign, 'Janma ' + short(mo.nakshatra) + ' ' + mo.pada].concat(F.day && DAY_LORD[F.day] ? ['Day lord ' + DAY_LORD[F.day]] : []);
    T(bits.join(' · '), X, Y + 82 * s, {f: '500 ' + Math.round(21 * s) + 'px ' + SANS, c: '#3d3224', mw: W * 0.66});
    const r = F.req, who = hide ? 'Birth details hidden' :
      [r.name, new Date(r.dob + 'T12:00:00Z').toLocaleDateString('en-GB', {day: 'numeric', month: 'short', year: 'numeric', timeZone: 'UTC'}) +
        (r.tob_unknown ? '' : ', ' + r.tob.slice(0, 5)), (r.place || '').split(',')[0]].filter(Boolean).join(' · ');
    [who, F.ay + ' ayanamsa · Whole-sign houses', 'Vimshottari · Swiss Ephemeris'].forEach((t, i) =>
      T(t, X + W, Y + (30 + i * 26) * s, {f: (i ? 400 : 600) + ' ' + Math.round(19 * s) + 'px ' + SANS, c: MUT, a: 'right', mw: W * 0.36}));
    Ln(X, Y + 100 * s, X + W, Y + 100 * s, BAR, 3 * s);
    return Y + 100 * s;
  }
  function chartKey(x, F, X, Y, W, s) {
    const list = m => F.planets.filter(q => q.marks.includes(m)).map(q => AB[q.p]).join(' ') || 'none';
    const cells = [['↑ Exalted', list('↑')], ['↓ Debilitated', list('↓')], ['ᴿ Retrograde', list('ᴿ')], ['ᶜ Combust', list('ᶜ')]];
    return table(x, X, Y, [W * 0.26, W * 0.24, W * 0.26, W * 0.24], null,
      [{cells: [{t: cells[0][0], w: 600}, {t: cells[0][1], c: MUT}, {t: cells[1][0], w: 600}, {t: cells[1][1], c: MUT}]},
        {cells: [{t: cells[2][0], w: 600}, {t: cells[2][1], c: MUT}, {t: cells[3][0], w: 600}, {t: cells[3][1], c: MUT}]}],
      {rh: 34 * s, fs: Math.round(19 * s), title: 'CHART KEY'});
  }
  function keyLords(x, F, X, Y, W, s) {
    return table(x, X, Y, [W * 0.46, W * 0.36, W * 0.18], ['OF', 'LORD', 'IN'],
      F.keyLords.map(([of, lord, h]) => ({cells: [{t: of}, {t: lord, c: COL[lord], w: 700}, {t: String(h), al: 'center'}]})),
      {rh: 32 * s, fs: Math.round(19 * s), title: 'KEY LORDS'});
  }
  function planetTable(x, F, X, Y, W, s) {
    const f = [0.14, 0.08, 0.12, 0.2, 0.06, 0.05, 0.08, 0.16, 0.11].map(v => v * W);
    const rows = [{cells: [{t: 'Lagna', c: ACC, w: 700}, {t: SAB[F.L]}, {t: dm(F.l.ascendant % 30)}, {t: F.lagNak}, {t: AB[(F.l.kp || {}).star_lord] || ''},
      {t: '1', al: 'center'}, {t: F.L9 != null ? SAB[F.L9] : ''}, {t: ''}, {t: ''}]}]
      .concat(F.planets.map(q => ({cells: [{t: q.p + (q.g.retrograde && q.p !== 'Rahu' && q.p !== 'Ketu' ? ' ᴿ' : ''), c: COL[q.p], w: 700},
        {t: SAB[q.g.sign_index]}, {t: dm(q.g.degrees_in_sign)}, {t: short(q.g.nakshatra) + ' ' + q.g.pada}, {t: AB[q.nl] || ''},
        {t: String(q.house), al: 'center'}, {t: q.d9 != null ? SAB[q.d9] : ''},
        {t: q.dg ? (q.dg === 'Debilitated' ? 'Debil.' : q.dg) + (q.g.combust ? ' · c' : '') : q.g.combust ? 'c' : '', c: DIG_COL[q.dg]},
        {t: q.kar, c: '#8a5e14', w: 700}]})));
    return table(x, X, Y, f, ['PLANET', 'SIGN', 'DEGREE', 'NAKSHATRA', 'NL', 'H', 'D9', 'DIGNITY', 'KARAKA'], rows, {rh: 38 * s, fs: Math.round(21 * s)});
  }
  function dashaTables(x, F, X, Y, W, s, gap) {
    const now = Date.now(), birth = new Date(F.req.dob + 'T00:00:00Z'), w = (W - gap) / 2;
    const rows = list => list.map(d => { const on = isNow(d, now); return {bg: on ? NOW : null, bold: on,
      cells: [{t: d.lord + (on ? ' ◀' : ''), c: COL[d.lord], w: 700}, {t: new Date(d.start) <= birth ? 'Birth' : my(d.start)}, {t: my(d.end)}]} });
    const cw = [w * 0.4, w * 0.3, w * 0.3], o = {rh: 34 * s, fs: Math.round(20 * s)};
    const a = table(x, X, Y, cw, ['LORD', 'FROM', 'TO'], rows(F.c.dasha || []), {...o, title: 'VIMSHOTTARI MAHADASHA'});
    const b = F.md ? table(x, X + w + gap, Y, cw, ['LORD', 'FROM', 'TO'], rows(F.md.children || []), {...o, title: F.md.lord.toUpperCase() + ' ANTARDASHAS'}) : Y;
    return Math.max(a, b);
  }
  function footer(x, X, Y, W, s) {
    const {T, R} = pen(x), h = 52 * s;
    R(X, Y, W, h, INK);
    x.font = '400 ' + Math.round(23 * s) + 'px ' + SANS;
    const a = 'Generate your free chart at ', b = 'simplejyotish.com', wa = x.measureText(a).width;
    x.font = '700 ' + Math.round(23 * s) + 'px ' + SANS;
    const tot = wa + x.measureText(b).width + 34 * s, sx = X + (W - tot) / 2;
    x.fillStyle = '#f2c66b'; x.beginPath(); x.arc(sx + 11 * s, Y + h / 2, 11 * s, 0, 7); x.fill();
    T(a, sx + 34 * s, Y + h / 2, {f: '400 ' + Math.round(23 * s) + 'px ' + SANS, c: '#f3e7cf', b: 'middle'});
    T(b, sx + 34 * s + wa, Y + h / 2, {f: '700 ' + Math.round(23 * s) + 'px ' + SANS, c: '#f2c66b', b: 'middle'});
    return Y + h;
  }

  // Tall (1080 wide, for phones) or wide (1920 × 1080, for computers).
  function draw(F, o) {
    const wide = o.shape === 'wide', W = wide ? 1920 : 1080, P = 40, cv = document.createElement('canvas');
    cv.width = W; cv.height = wide ? 1080 : 2400;
    const x = cv.getContext('2d'), s = 1, IW = W - 2 * P;
    x.fillStyle = BG; x.fillRect(0, 0, W, cv.height);
    let y = header(x, F, P, P - 6, IW, s, o.hide) + 22;
    const label = (t, X, Y) => pen(x).T(t, X, Y, {f: '600 20px ' + SANS, c: MUT});
    if (wide) {
      const S = 700, rx = P + S + 24, rw = 320, tx = P + S + 24 + rw + 32, tw = W - P - tx;
      kundli(x, P, y, S, F.L, d1Items(F), o.style);
      chartKey(x, F, P, y + S + 14, S, s);
      label('D9 · Navamsa · ' + (F.L9 != null ? SIGNS[F.L9] : ''), rx, y + 18);
      if (F.D9) kundli(x, rx, y + 30, rw, F.L9, d9Items(F), o.style, true);
      keyLords(x, F, rx, y + 30 + rw + 18, rw, s);
      const t2 = planetTable(x, F, tx, y, tw, 0.94);
      dashaTables(x, F, tx, t2 + 22, tw, 1, 20);
      footer(x, P, cv.height - P - 52, IW, s);
      return cv;
    }
    const S = 620, rx = P + S + 24, rw = IW - S - 24;
    kundli(x, P, y, S, F.L, d1Items(F), o.style);
    const k1 = chartKey(x, F, P, y + S + 14, S, s);
    label('D9 · Navamsa · ' + (F.L9 != null ? SIGNS[F.L9] : ''), rx, y + 18);
    const d9 = Math.min(rw, 330);
    if (F.D9) kundli(x, rx + (rw - d9) / 2, y + 30, d9, F.L9, d9Items(F), o.style, true);
    const k2 = keyLords(x, F, rx, y + 30 + d9 + 18, rw, s);
    y = Math.max(k1, k2) + 24;
    y = planetTable(x, F, P, y, IW, s) + 24;
    y = dashaTables(x, F, P, y, IW, s, 24) + 24;
    y = footer(x, P, y, IW, s) + P;
    const out = document.createElement('canvas'); out.width = W; out.height = Math.ceil(y);
    out.getContext('2d').drawImage(cv, 0, 0);
    return out;
  }

  // ---------- the text post ----------
  function post(F) {
    const md = F.md, ad = F.ad;
    const title = '[Chart] ' + F.l.sign + ' lagna' + (md ? ' · ' + md.lord + (ad ? '–' + ad.lord : '') + ' dasha' : '') + ' · ';
    const rows = [['Lagna', F.l.sign, dm(F.l.ascendant % 30), F.lagNak, '1', '']].concat(F.planets.map(q =>
      [q.p + (q.marks.includes('ᴿ') ? ' (R)' : ''), q.g.sign, dm(q.g.degrees_in_sign), short(q.g.nakshatra) + ' ' + q.g.pada, String(q.house),
        [q.dg, q.g.combust ? 'combust' : ''].filter(Boolean).join(', ')]));
    const t = (head, list) => '| ' + head.join(' | ') + ' |\n|' + head.map(() => '---').join('|') + '|\n' + list.map(r => '| ' + r.join(' | ') + ' |').join('\n');
    const dasha = [md && ['Mahadasha', md.lord, my(md.start), my(md.end)], ad && ['Antardasha', ad.lord, my(ad.start), my(ad.end)]].filter(Boolean);
    const body = '**My question:** _write it here_\n\n' + t(['Planet', 'Sign', 'Degree', 'Nakshatra', 'House', 'Dignity'], rows) + '\n\n' +
      (dasha.length ? t(['Dasha', 'Lord', 'From', 'To'], dasha) + '\n\n' : '') +
      '**D9 lagna:** ' + (F.L9 != null ? SIGNS[F.L9] : '–') + ' · ' + F.ay + ' ayanamsa · whole-sign houses\n\n_Chart from simplejyotish.com_';
    return {title, body};
  }

  // ---------- the dialog ----------
  const esc = s => String(s).replace(/[&<>"]/g, ch => ({'&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;'})[ch]);
  async function open(c, req, chartStyle) {
    if (!c || !req) return;
    let bx = null;
    try { const r = await fetch('/birth-extras', {method: 'POST', headers: {'content-type': 'application/json'}, body: JSON.stringify(req)}); bx = r.ok ? await r.json() : null } catch (e) {}
    const F = facts(c, req, bx), o = {hide: true, style: chartStyle === 'south' ? 'south' : 'north', shape: 'tall'};
    const d = document.createElement('div');
    d.className = 'rdlg'; d.setAttribute('role', 'dialog'); d.setAttribute('aria-modal', 'true'); d.setAttribute('aria-label', 'Chart image for Reddit');
    const seg = (k, opts) => '<div class="rseg" role="group">' + opts.map(([v, t]) => '<button type="button" data-k="' + k + '" data-v="' + v + '">' + t + '</button>').join('') + '</div>';
    d.innerHTML = '<div class="rbox"><div class="rtop"><b>Chart image for Reddit</b><button type="button" class="rx" data-close aria-label="Close">✕</button></div>' +
      '<div class="rimg"><img alt="Your chart image"></div>' +
      '<div class="ropts"><div class="rrow"><span id="rhidelbl"><b>Hide my birth details</b><small>No name, date, time or place on the image</small></span>' +
      '<input type="checkbox" data-k="hide" aria-labelledby="rhidelbl" checked></div>' +
      '<div class="rrow"><b>Chart style</b>' + seg('style', [['north', 'North'], ['south', 'South']]) + '</div>' +
      '<div class="rrow"><b>Shape</b>' + seg('shape', [['tall', 'Tall (phone)'], ['wide', 'Wide 16:9']]) + '</div></div>' +
      '<div class="rbtns"><a class="btn" data-dl>Download image</a><button type="button" class="btn ghost" data-copy>Copy for Reddit</button></div>' +
      '<div class="rcopy" hidden></div></div>';
    let url = null;
    const paint = () => {
      d.querySelectorAll('.rseg button').forEach(b => b.setAttribute('aria-pressed', String(o[b.dataset.k] === b.dataset.v)));
      draw(F, o).toBlob(blob => {
        if (!blob) return;
        if (url) URL.revokeObjectURL(url);
        url = URL.createObjectURL(blob);
        d.querySelector('.rimg img').src = url;
        const a = d.querySelector('[data-dl]'); a.href = url;
        a.download = 'chart-' + F.l.sign.toLowerCase() + '-lagna' + (o.shape === 'wide' ? '-wide' : '') + '.png';
      }, 'image/png');
    };
    const close = () => { d.remove(); if (url) setTimeout(() => URL.revokeObjectURL(url), 1000); removeEventListener('keydown', key) };
    const key = e => { if (e.key === 'Escape') close() };
    addEventListener('keydown', key);
    const copyBox = () => {
      const p = post(F), box = d.querySelector('.rcopy');
      box.innerHTML = '<p class="hint">Paste the title, then the post into a text post, and add your image. Reddit shows the tables properly.</p>' +
        '<div class="rfield"><small>TITLE</small><div class="rtitle">' + esc(p.title) + '<i>your question here</i></div><button type="button" class="btn ghost" data-ct>Copy title</button></div>' +
        '<div class="rfield"><small>POST</small><pre>' + esc(p.body) + '</pre><button type="button" class="btn" data-cb>Copy post</button></div>';
      box.hidden = false; box.scrollIntoView({behavior: 'smooth', block: 'nearest'});
    };
    const copy = async (text, b) => {
      try { await navigator.clipboard.writeText(text); const t = b.textContent; b.textContent = 'Copied ✓'; setTimeout(() => { b.textContent = t }, 1600) }
      catch (e) { b.textContent = 'Select the text and copy it' }
    };
    d.addEventListener('click', e => {
      const t = e.target;
      if (t === d || t.closest('[data-close]')) return close();
      const sb = t.closest('.rseg button');
      if (sb) { o[sb.dataset.k] = sb.dataset.v; paint(); return }
      if (t.closest('[data-copy]')) { copyBox(); track('chart/reddit-copy'); return }
      if (t.closest('[data-ct]')) return copy(post(F).title, t.closest('button'));
      if (t.closest('[data-cb]')) return copy(post(F).body, t.closest('button'));
      if (t.closest('[data-dl]')) track('chart/reddit-image');
    });
    d.addEventListener('change', e => { if (e.target.dataset.k === 'hide') { o.hide = e.target.checked; paint() } });
    const track = window.track || (() => {});
    document.body.appendChild(d);
    d.querySelector('[data-close]').focus();
    paint();
  }
  window.redditImage = open;
  window._redditImageForTest = {facts, post, dignity, draw};
})();
