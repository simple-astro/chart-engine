// SimpleJyotish Pro: a desktop dashboard of widgets for professional astrologers.
// Every widget reads data the engine already makes (the chart, Shadbala, birth extras, transits, KP timing) plus
// /pro/api/tables (avasthas, friendships, Vimshopaka, upagrahas, Sade Sati). Extra data loads only when a widget
// on screen needs it. One time control drives every timing widget; clicking a planet highlights it everywhere.
(() => {
  const $ = id => document.getElementById(id);
  const esc = s => String(s ?? '').replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
  const P9 = ['Sun', 'Moon', 'Mars', 'Mercury', 'Jupiter', 'Venus', 'Saturn', 'Rahu', 'Ketu'], P7 = P9.slice(0, 7);
  const AB = { Sun: 'Su', Moon: 'Mo', Mars: 'Ma', Mercury: 'Me', Jupiter: 'Ju', Venus: 'Ve', Saturn: 'Sa', Rahu: 'Ra', Ketu: 'Ke', Uranus: 'Ur', Neptune: 'Ne', Pluto: 'Pl' };
  // Uranus, Neptune and Pluto: off by default; the same switch as the app's Settings (shared in this browser)
  let SHOW_OUTER = false; try { SHOW_OUTER = localStorage.getItem('sj-outer') === '1'; } catch (e) {}
  const outerOn = () => SHOW_OUTER && S.c && S.c.outer ? Object.entries(S.c.outer) : [];
  const FULL = Object.fromEntries(Object.entries(AB).map(([k, v]) => [v, k]));
  const SIGNS = ['Aries', 'Taurus', 'Gemini', 'Cancer', 'Leo', 'Virgo', 'Libra', 'Scorpio', 'Sagittarius', 'Capricorn', 'Aquarius', 'Pisces'];
  const SA = ['Ari', 'Tau', 'Gem', 'Can', 'Leo', 'Vir', 'Lib', 'Sco', 'Sag', 'Cap', 'Aqu', 'Pis'];
  const LORDS = ['Mars', 'Venus', 'Mercury', 'Moon', 'Sun', 'Mercury', 'Venus', 'Mars', 'Jupiter', 'Saturn', 'Saturn', 'Jupiter'];
  const EXALT = { Sun: 0, Moon: 1, Mars: 9, Mercury: 5, Jupiter: 3, Venus: 11, Saturn: 6, Rahu: 1, Ketu: 7 };
  const VIM_ORDER = ['Ketu', 'Venus', 'Sun', 'Moon', 'Mars', 'Rahu', 'Jupiter', 'Saturn', 'Mercury'];
  const VIM_YRS = { Ketu: 7, Venus: 20, Sun: 6, Moon: 10, Mars: 7, Rahu: 18, Jupiter: 16, Saturn: 19, Mercury: 17 };
  // Natural planet colours (Sun saffron, Moon white, Mars red, Mercury green, Jupiter yellow, Venus pink, Saturn blue,
  // Rahu smoky, Ketu earthy): real hex values, so a transparency suffix like col(p) + '33' stays a valid colour.
  // Planet colours come from the theme (pro.html), so they read on dark and light pages alike.
  const HEX = { Sun: 'var(--Su)', Moon: 'var(--Mo)', Mars: 'var(--Ma)', Mercury: 'var(--Me)', Jupiter: 'var(--Ju)', Venus: 'var(--Ve)', Saturn: 'var(--Sa)', Rahu: 'var(--Ra)', Ketu: 'var(--Ke)', Uranus: 'var(--Ur)', Neptune: 'var(--Ne)', Pluto: 'var(--Pl)' };
  const col = p => HEX[p] || HEX[FULL[p]] || 'var(--mut)';
  const tint = (c, pct) => `color-mix(in srgb, ${c} ${pct}%, transparent)`;
  const pn = (p, short) => `<span class="p" data-p="${p}" style="color:${col(p)}">${short ? AB[p] : p}</span>`;
  const dms = x => { const d = Math.floor(x), mf = (x - d) * 60, m = Math.floor(mf), s = Math.round((mf - m) * 60);
    return `${String(d).padStart(2, '0')}°${String(s === 60 ? m + 1 : m).padStart(2, '0')}′${String(s === 60 ? 0 : s).padStart(2, '0')}″`; };
  const dm = x => `${Math.floor(x)}°${String(Math.floor((x % 1) * 60)).padStart(2, '0')}′`;
  const dt = iso => iso ? new Date(iso.length > 10 ? iso : iso + 'T12:00:00Z').toLocaleDateString(undefined, { day: '2-digit', month: 'short', year: 'numeric' }) : '–';
  const ymd = d => d.toLocaleDateString('en-CA');
  const dignity = (p, s) => EXALT[p] === s ? 'exalted' : (EXALT[p] + 6) % 12 === s ? 'debilitated' : LORDS[s] === p ? 'own' : '';
  const tbl = (head, rows, num = []) => `<table><thead><tr>${head.map((h, i) => `<th class="${num.includes(i) ? 'n' : ''}">${h}</th>`).join('')}</tr></thead><tbody>${rows.map(r => `<tr>${r.map((c, i) => `<td class="${num.includes(i) ? 'n' : ''}">${c}</td>`).join('')}</tr>`).join('')}</tbody></table>`;
  const kv = rows => `<div class="kv">${rows.map(([k, v]) => `<span>${k}</span><b>${v}</b>`).join('')}</div>`;
  const tone = v => ({ strong: 'good', favourable: 'good', good: 'good', Strong: 'good', mixed: 'mid', Mixed: 'mid', Weak: 'mid', challenging: 'bad', present: 'bad', Present: 'mid', bad: 'bad' }[v] || 'neu');

  // ----- state -----
  const S = { pid: null, P: null, c: null, req: null, cache: {}, time: new Date(), sel: null, layout: [], timer: null };
  async function api(url, body) {
    const r = await fetch(url, body ? { method: 'POST', headers: { 'content-type': 'application/json' }, body: JSON.stringify(body) } : {});
    if (r.status === 401) { location.href = '/pro'; throw new Error('Signed out'); }
    if (!r.ok) throw new Error((await r.json().catch(() => ({}))).detail || r.statusText);
    return r.json();
  }
  const LOAD = {
    T: () => api('/pro/api/tables/' + S.pid),
    SB: () => api('/shadbala', S.req),
    BX: () => api('/birth-extras', S.req),
    PAN: () => api('/panchang', { on: S.req.dob, lat: S.req.lat, lon: S.req.lon, tz_name: S.req.tz_name }),
    LK: () => api('/lal-kitab', S.req),
    TJ: () => api(`/profiles/${S.pid}/tajika`),
  };
  function need(k) { if (!S.cache[k]) S.cache[k] = LOAD[k](); return S.cache[k]; }
  function gochar() { const d = ymd(S.time), k = 'GO' + d; if (!S.cache[k]) S.cache[k] = api(`/profiles/${S.pid}/transit?date=${d}&tz=${encodeURIComponent(S.req.tz_name)}`); return S.cache[k]; }
  function life(topic) { const k = 'LIFE' + topic; if (!S.cache[k]) S.cache[k] = api(`/profiles/${S.pid}/graph/life?topic=${topic}&ahead=36`); return S.cache[k]; }
  function ruling(at) { at = at || { lat: S.req.lat, lon: S.req.lon, tz_name: S.req.tz_name };
    const k = 'RP' + at.lat + at.lon + S.time.toISOString().slice(0, 16); if (!S.cache[k]) S.cache[k] = api('/ruling-planets', { lat: at.lat, lon: at.lon, tz_name: at.tz_name, at: S.time.toISOString() }); return S.cache[k]; }
  const here = () => { try { const h = JSON.parse(localStorage.getItem('sj_here') || 'null'); if (h && isFinite(h.lat) && h.tz_name) return h; } catch (e) {} return null; };

  // ----- charts (North Indian, or South when the app is set to South) -----
  const STYLE = (() => { try { return localStorage.getItem('sj-chart-style') === 'south' ? 'south' : 'north'; } catch (e) { return 'north'; } })();
  const NP = [[200, 95], [100, 45], [45, 100], [95, 200], [45, 300], [100, 355], [200, 305], [300, 355], [355, 300], [305, 200], [355, 100], [300, 45]];
  // Ashtakavarga frame around the North Indian chart: each house's score in the band along its own edge
  // (top 2 · 1 · 12, left 3 · 4 · 5, bottom 6 · 7 · 8, right 11 · 10 · 9), like the classic printed kundlis.
  const FRAME = [[2, -11, -11, 129, 9], [1, 118, -11, 164, 9], [12, 282, -11, 129, 9],
    [3, -11, -2, 9, 132], [4, -11, 130, 9, 140], [5, -11, 270, 9, 132],
    [6, -11, 402, 129, 9], [7, 118, 402, 164, 9], [8, 282, 402, 129, 9],
    [11, 402, -2, 9, 132], [10, 402, 130, 9, 140], [9, 402, 270, 9, 132]];
  const savCol = s => s >= 30 ? 'var(--teal)' : s <= 22 ? 'var(--red)' : 'var(--ink2)';
  const SC = [[1, 0], [2, 0], [3, 0], [3, 1], [3, 2], [3, 3], [2, 3], [1, 3], [0, 3], [0, 2], [0, 1], [0, 0]];
  const lab = it => it.p ? `<tspan data-p="${it.p}" style="fill:${col(it.p)}">${it.t}</tspan>` : `<tspan style="fill:${it.c || 'var(--gold)'}">${it.t}</tspan>`;
  function chartSVG(lag, byH, o = {}) {
    const ring = !!o.sav && STYLE !== 'south', vb = ring ? '-13 -13 426 426' : '-2 -2 404 404', big = o.big !== false;
    let v = `<svg viewBox="${vb}" role="img" aria-label="${esc(o.label || 'chart')}">`;
    if (STYLE === 'south' && !o.houseSigns) {
      v += '<rect x="0" y="0" width="400" height="400" style="fill:var(--chartbg);stroke:var(--chartline)" stroke-width="3"/><path d="M0 100H400M0 300H400M100 0V400M300 0V400M0 200H100M300 200H400M200 0V100M200 300V400" style="stroke:var(--chartline)" stroke-width="2.5"/>';
      v += `<text x="200" y="205" text-anchor="middle" font-size="18" style="fill:var(--dim)">${esc(o.label || '')}</text>`;
      for (let h = 0; h < 12; h++) {
        const sg = (lag + h) % 12, [cx, cy] = SC[sg], x = cx * 100, y = cy * 100, pl = byH[h] || [];
        if (h === 0) v += `<path d="M${x} ${y + 28}L${x + 28} ${y}" style="stroke:var(--gold)" stroke-width="3"/>`;
        v += `<text x="${x + 94}" y="${y + 16}" text-anchor="end" font-size="13" style="fill:var(--dim)">${SA[sg]}</text>`;
        const rows = Math.ceil(pl.length / 2), t = y + 52 - (rows - 1) * 12;
        for (let r = 0; r < rows; r++) v += `<text x="${x + 50}" y="${t + r * 24}" text-anchor="middle" font-size="22" font-weight="700">${pl.slice(r * 2, r * 2 + 2).map(lab).join(' ')}</text>`;
        if (o.sav) { const sc = o.sav[h]; v += `<text x="${x + 6}" y="${y + 94}" font-size="15" font-weight="700" style="fill:${savCol(sc)}">${sc}</text>`; }  // South: score in the box corner
      }
    } else {
      v += '<rect x="0" y="0" width="400" height="400" style="fill:var(--chartbg);stroke:var(--chartline)" stroke-width="3"/><polygon points="200,0 300,100 200,200 100,100" style="fill:color-mix(in srgb,var(--gold) 9%,transparent);stroke:var(--gold)" stroke-width="2.5"/><path d="M0 0L400 400M400 0L0 400M200 0L400 200L200 400L0 200Z" fill="none" style="stroke:var(--chartline)" stroke-width="2.5"/>';
      NP.forEach(([x, y], h) => {
        const pl = byH[h] || [], per = o.deg ? 1 : 2, rows = Math.ceil(pl.length / per), lh = o.deg ? (pl.length > 3 ? 17 : 20) : 27, t = y - (rows - 1) * lh / 2 + 12;
        const sg = o.houseSigns ? o.houseSigns[h] : (lag + h) % 12;
        v += `<text x="${x}" y="${pl.length ? t - (o.deg ? 20 : 24) : y + 6}" text-anchor="middle" font-size="15" style="fill:var(--dim)">${sg + 1}${o.cuspDeg ? `<tspan font-size="11" style="fill:var(--mut)" dx="3">${o.cuspDeg[h]}</tspan>` : ''}</text>`;
        for (let r = 0; r < rows; r++) v += `<text x="${x}" y="${t + r * lh}" text-anchor="middle" font-size="${o.deg ? (pl.length > 3 ? 15 : 17) : pl.length > 4 ? 20 : 24}" font-weight="700">${pl.slice(r * per, r * per + per).map(it => lab(it) + (o.deg && it.d ? `<tspan font-size="${pl.length > 3 ? 10 : 11}" font-weight="500" style="fill:var(--ink2)" dy="-6">${it.d}</tspan>${it.f || ''}<tspan dy="6"> </tspan>` : '')).join(' ')}</text>`;
      });
    }
    if (ring) FRAME.forEach(([h, x, y, w, ht]) => { const s = o.sav[h - 1], c = savCol(s), side = w < ht, cx = x + w / 2, cy = y + ht / 2;
      v += `<rect x="${x}" y="${y}" width="${w}" height="${ht}" style="fill:${tint(c, 7)};stroke:var(--line)" stroke-width=".6"/>` +
        `<text x="${cx}" y="${cy + 2.6}" text-anchor="middle" font-size="7.5" font-weight="700" style="fill:${c}"${side ? '' : ' letter-spacing=".3"'}><title>House ${h}: ${s} bindus</title>${s}</text>`; });
    return v + '</svg>';
  }
  const retro = (p, g) => g.retrograde && p !== 'Rahu' && p !== 'Ketu' ? 'ᴿ' : '';
  const NATAL = p => S.c.grahas[p].sign_index;  // the birth chart's signs: only these charts also take the outer planets
  function byHouse(signOf, lag, extra = [], deg) {
    const o = {};
    P9.forEach(p => { const s = signOf(p); if (s == null) return; const h = (s - lag + 12) % 12; (o[h] = o[h] || []).push({ t: AB[p] + retro(p, S.c.grahas[p]), p, d: deg ? dm(S.c.grahas[p].degrees_in_sign) : null }); });
    extra.forEach(([t, s]) => { const h = (s - lag + 12) % 12; (o[h] = o[h] || []).push({ t }); });
    if (signOf === NATAL) outerOn().forEach(([p, g]) => { const h = (g.sign_index - lag + 12) % 12;
      (o[h] = o[h] || []).push({ t: AB[p] + (g.retrograde ? 'ᴿ' : ''), p, d: deg ? dm(g.degrees_in_sign) : null }); });
    return o;
  }
  const savHouses = lag => { const sav = S.c.ashtakavarga && S.c.ashtakavarga.sav; return sav ? sav.map((_, i) => sav[(lag + i) % 12]) : null; };
  const vargaChart = v => { const L = S.c.varga_lagna[v]; return chartSVG(L, byHouse(p => S.c.vargas[v][p] && S.c.vargas[v][p].sign_index, L), { label: v }); };

  // ----- Vimshottari at any moment (5 levels; the chart stores 3, the rest split in the same proportions) -----
  const vimSplit = p => { const out = [], i0 = VIM_ORDER.indexOf(p.lord), L = p.end - p.start; let s = +p.start;
    for (let k = 0; k < 9; k++) { const l = VIM_ORDER[(i0 + k) % 9], e = s + L * VIM_YRS[l] / 120; out.push({ lord: l, start: new Date(s), end: new Date(e) }); s = e; } return out; };
  const norm = d => ({ lord: d.lord, start: new Date(d.start), end: new Date(d.end), children: d.children });
  function dashaAt(t) {
    const out = []; let lv = (S.c.dasha || []).map(norm);
    for (let i = 0; i < 5 && lv.length; i++) { const n = lv.find(d => t >= d.start && t < d.end); if (!n) break; out.push(n);
      lv = n.children && n.children.length ? n.children.map(norm) : vimSplit(n); }
    return out;
  }
  const LV = ['Mahadasha', 'Antardasha', 'Pratyantar', 'Sookshma', 'Prana'];

  // ----- the widget library -----
  const W = [];
  const add = (id, t, g, w, r, o = {}) => W.push({ id, t, g, w, r, time: !!o.time, kw: o.kw || '' });
  const G = { pan: 'Panchang', moon: 'Moon', prim: 'Primary charts', div: 'Divisional charts', pos: 'Planet positions', av: 'Avastha',
    fr: 'Friendship', da: 'Divisional analysis', ak: 'Ashtakavarga', vim: 'Vimshottari dasha', sb: 'Shadbala', dr: 'Drishti',
    yog: 'Yogini dasha', jai: 'Jaimini', ss: 'Sade Sati', go: 'Gochar (transits)', kp: 'KP', yg: 'Yogas', ours: 'SimpleJyotish only' };

  // Panchang and Moon
  add('panchang', 'Panchang', G.pan, 1, async () => { const [bx, pan] = await Promise.all([need('BX'), need('PAN').catch(() => null)]);
    const a = k => (bx.avakhada.rows.find(x => x.label === k) || {}).value || '–', m = S.c.grahas.Moon, sun = S.c.grahas.Sun;
    const tm = iso => iso ? new Date(iso).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', timeZone: S.req.tz_name }) : '–';
    return kv([['Tithi', a('Tithi at birth')], ['Vara', a('Birth day (Vedic)')], ['Nakshatra', `${m.nakshatra} ${m.pada}`], ['Yoga', a('Yoga at birth')],
      ['Karana', a('Karana at birth')], ['Sun nakshatra', sun.nakshatra], ['Sunrise', tm(pan && pan.sunrise)], ['Sunset', tm(pan && pan.sunset)]]); }, { kw: 'tithi yoga karana sunrise' });
  add('moonq', 'Moon quality', G.moon, 1, async () => { const bx = await need('BX');
    return kv(bx.avakhada.rows.filter(x => !/Tithi|Yoga at|Karana|Birth day|Ayanamsha|Lagna/.test(x.label)).map(x => [esc(x.label), esc(x.value)])); }, { kw: 'avakhada varna yoni gana nadi' });

  // Primary charts
  add('d1', 'Lagna · D1', G.prim, 1, () => { const L = S.c.lagna.sign_index; return chartSVG(L, byHouse(NATAL, L), { label: 'D1' }); }, { kw: 'rasi birth chart' });
  add('d9', 'Navamsha · D9', G.prim, 1, () => { const v = S.c.vargas.D9, L = S.c.varga_lagna.D9;
    const vo = P9.filter(p => v[p].sign_index === S.c.grahas[p].sign_index), own = P7.filter(p => LORDS[v[p].sign_index] === p), deb = P7.filter(p => dignity(p, v[p].sign_index) === 'debilitated'), ex = P7.filter(p => dignity(p, v[p].sign_index) === 'exalted');
    return vargaChart('D9') + `<div class="note">D9 Lagna ${SIGNS[L]}${vo.length ? ' · Vargottama ' + vo.map(p => pn(p, 1)).join(' ') : ''}${ex.length ? ' · Exalted ' + ex.map(p => pn(p, 1)).join(' ') : ''}${own.length ? ' · Own ' + own.map(p => pn(p, 1)).join(' ') : ''}${deb.length ? ' · Debilitated ' + deb.map(p => pn(p, 1)).join(' ') : ''}</div>`; }, { kw: 'navamsa marriage' });
  add('chalit', 'Bhava Chalit', G.prim, 1, () => { const o = {}; P9.forEach(p => { const h = S.c.grahas[p].house - 1; (o[h] = o[h] || []).push({ t: AB[p] + retro(p, S.c.grahas[p]), p }); });
    return chartSVG(0, o, { houseSigns: S.c.houses.map(h => h.sign_index), label: 'Chalit' }) + `<div class="note">Houses from the ${esc(S.c.meta.house_system)} cusps</div>`; }, { kw: 'chalit cusps bhava' });
  add('moonchart', 'Moon chart', G.prim, 1, () => { const L = S.c.grahas.Moon.sign_index; return chartSVG(L, byHouse(NATAL, L, [['As', S.c.lagna.sign_index]]), { label: 'Chandra' }); }, { kw: 'chandra lagna' });
  add('sunchart', 'Sun chart', G.prim, 1, () => { const L = S.c.grahas.Sun.sign_index; return chartSVG(L, byHouse(NATAL, L, [['As', S.c.lagna.sign_index]]), { label: 'Surya' }); }, { kw: 'surya lagna' });

  // Divisional charts
  const VN = { D2: 'Hora', D3: 'Drekkana', D4: 'Chaturthamsa', D7: 'Saptamsa', D10: 'Dasamsa', D12: 'Dwadasamsa', D16: 'Shodasamsa', D20: 'Vimsamsa',
    D24: 'Chaturvimsamsa', D27: 'Bhamsa', D30: 'Trimsamsa', D40: 'Khavedamsa', D45: 'Akshavedamsa', D60: 'Shashtiamsa', D150: 'Nadi amsha' };
  Object.entries(VN).forEach(([v, n]) => add('v' + v, `${n} · ${v}`, G.div, 1, () => S.c.vargas[v] ? vargaChart(v) : '<p class="note">Not calculated for this chart.</p>', { kw: v }));
  add('vall', 'All divisional charts', G.div, 4, () => `<div class="vg">${Object.keys(S.c.vargas).map(v => `<div><span>${v} ${esc(VN[v] || 'Rasi')}</span>${vargaChart(v)}</div>`).join('')}</div>`, { kw: 'varga grid' });

  // Planet positions
  add('spasht', 'Grah spasht · KP lords', G.pos, 2, () => { const L = S.c.lagna, lk = L.kp || {};
    const rows = [[`<b style="color:var(--gold)">Lagna</b>`, SIGNS[L.sign_index], dms(L.ascendant % 30), '–', LORDS[L.sign_index], lk.star_lord || '–', lk.sub_lord || '–', '1', '']].concat(
      P9.map(p => { const g = S.c.grahas[p], k = g.kp || {}, d = dignity(p, g.sign_index);
        return [pn(p) + (retro(p, g) ? ' ℞' : ''), g.sign, dms(g.degrees_in_sign), `${g.nakshatra} ${g.pada}`, pn(g.sign_lord, 1), pn(k.star_lord || g.nakshatra_lord, 1), k.sub_lord ? pn(k.sub_lord, 1) : '–', g.house,
          [d && `<span class="tag ${d === 'debilitated' ? 'bad' : 'good'}">${d}</span>`, g.combust && '<span class="tag mid">combust</span>'].filter(Boolean).join('')]; }));
    outerOn().forEach(([p, g]) => rows.push([pn(p) + (g.retrograde ? ' ℞' : ''), g.sign, dms(g.degrees_in_sign), `${g.nakshatra} ${g.pada}`, pn(g.kp.sign_lord, 1), pn(g.kp.star_lord, 1), pn(g.kp.sub_lord, 1), g.house, '<span class="tag neu">outer</span>']));
    return tbl(['Planet', 'Sign', 'Degree', 'Nakshatra', 'Lord', 'Star', 'Sub', 'House', ''], rows, [7]); }, { kw: 'positions degrees sub lord uranus neptune pluto' });
  add('retro', 'Retrograde & combust', G.pos, 1, () => tbl(['Planet', 'Speed °/day', 'Motion'], P9.map(p => { const g = S.c.grahas[p];
    return [pn(p), g.speed.toFixed(3), [g.retrograde && (p === 'Rahu' || p === 'Ketu' ? 'always retrograde' : '<span class="tag mid">retrograde</span>'), g.combust && '<span class="tag bad">combust</span>'].filter(Boolean).join(' ') || '<span class="tag neu">direct</span>']; }), [1]), { kw: 'vakri asta' });

  // Avastha
  add('baladi', 'Avastha · Baladi', G.av, 1, async () => { const t = await need('T'); return tbl(['Planet', 'Degree', 'State'], P7.map(p => [pn(p), dm(S.c.grahas[p].degrees_in_sign), esc(t.avastha[p].baladi)])); }, { kw: 'age state' });
  add('jagrad', 'Avastha · Jagradadi', G.av, 1, async () => { const t = await need('T'); return tbl(['Planet', 'Sign', 'State'], P7.map(p => [pn(p), S.c.grahas[p].sign, esc(t.avastha[p].jagradadi)])); }, { kw: 'awake asleep' });

  // Friendship
  const FT = { 'Great friend': 'good', Friend: 'good', Neutral: 'neu', Enemy: 'bad', 'Great enemy': 'bad' }, FS = { 'Great friend': 'GF', Friend: 'F', Neutral: 'N', Enemy: 'E', 'Great enemy': 'GE' };
  const mtx = m => `<div class="mtx" style="grid-template-columns:repeat(8,1fr)"><div style="background:none"></div>${P7.map(p => `<div style="background:none">${pn(p, 1)}</div>`).join('')}${P7.map(r =>
    `<div style="background:none">${pn(r, 1)}</div>${P7.map(c => r === c ? '<div>·</div>' : `<div class="${FT[m[r][c]]}" title="${r} to ${c}: ${m[r][c]}">${FS[m[r][c]]}</div>`).join('')}`).join('')}</div><div class="note">Row planet's view of the column planet</div>`;
  add('fnat', 'Naisargik maitri (natural)', G.fr, 1, async () => mtx((await need('T')).friendship.natural), { kw: 'friendship natural' });
  add('ftat', 'Tatkalik maitri (temporary)', G.fr, 1, async () => mtx((await need('T')).friendship.temporary), { kw: 'friendship temporary' });
  add('fpan', 'Panchadha maitri (fivefold)', G.fr, 1, async () => mtx((await need('T')).friendship.fivefold), { kw: 'friendship compound' });

  // Divisional analysis
  add('karakas', 'Chara karakas', G.da, 1, () => tbl(['Karaka', 'Planet', 'Degree', 'Signifies'], S.c.jaimini.karakas.map(k => [k.short, pn(k.planet), dm(k.degree), esc(k.role)])), { kw: 'atmakaraka jaimini' });
  add('vimsho', 'Vimshopaka (Shodash varga totals)', G.da, 2, async () => { const v = (await need('T')).vimshopaka;
    return tbl(['Planet', 'Shadvarga', 'Saptavarga', 'Dashavarga', 'Shodashavarga', ''], P7.map(p => [pn(p), v[p].shadvarga, v[p].saptavarga, v[p].dashavarga, v[p].shodashavarga,
      `<div class="bt" style="width:90px"><i style="width:${v[p].shodashavarga / 20 * 100}%;background:${col(p)}"></i></div>`]), [1, 2, 3, 4]) + '<div class="note">Out of 20 · own and exaltation count in full</div>'; }, { kw: 'vimsopaka varga strength' });
  add('vargottam', 'Vargottama planets', G.da, 1, () => { const rows = P9.map(p => { const d1 = S.c.grahas[p].sign_index, hits = Object.keys(S.c.vargas).filter(v => v !== 'D1' && S.c.vargas[v][p] && S.c.vargas[v][p].sign_index === d1);
    return [pn(p), SA[d1], hits.includes('D9') ? '<span class="tag good">D9</span>' : '–', hits.filter(v => v !== 'D9').join(' ') || '–']; });
    return tbl(['Planet', 'D1', 'Vargottama', 'Same sign also in'], rows); }, { kw: 'vargottam' });
  add('special', 'Special lagnas', G.da, 2, async () => { const bx = await need('BX');
    return tbl(['Point', 'Sign', 'Degree', 'House', 'Nakshatra'], bx.special.points.map(x => [`<b>${esc(x.name)}</b>`, esc(x.sign), x.degrees_in_sign == null ? '–' : dm(x.degrees_in_sign), x.house || '–', esc(x.nakshatra || '–')])) +
      (bx.special.pushkara && bx.special.pushkara.length ? `<div class="note">Pushkara navamsha: ${bx.special.pushkara.map(esc).join(', ')}</div>` : ''); }, { kw: 'bhrigu bindu hora ghati indu mandi gulika' });
  add('upagraha', 'Upagrahas', G.da, 1, async () => { const [t, bx] = await Promise.all([need('T'), need('BX')]);
    const mg = bx.special.points.filter(x => /Mandi|Gulika/.test(x.name));
    return tbl(['Upagraha', 'Sign', 'Degree', 'House'], t.upagrahas.map(u => [esc(u.name), SA[u.sign_index], dm(u.degrees_in_sign), u.house]).concat(mg.map(x => [esc(x.name), esc(x.sign).slice(0, 3), x.degrees_in_sign == null ? '–' : dm(x.degrees_in_sign), x.house])), [3]); }, { kw: 'dhuma vyatipata gulika mandi' });

  // Ashtakavarga
  add('d1sav', 'D1 with Ashtakavarga', G.ak, 1, () => { const L = S.c.lagna.sign_index; return chartSVG(L, byHouse(NATAL, L), { sav: savHouses(L), label: 'D1' }) +
    '<div class="note">Frame: Sarva Ashtakavarga bindus per house · teal 30+, red 22 or less · total ' + S.c.ashtakavarga.sav_total + '</div>'; }, { kw: 'rasi sav bindus frame' });
  add('sav', 'Sarva Ashtakavarga', G.ak, 2, () => { const a = S.c.ashtakavarga, L = S.c.lagna.sign_index, cls = v => v >= 30 ? 'good' : v <= 22 ? 'bad' : 'neu';
    return tbl(['', ...SA, 'Σ'], [['Sign', ...a.sav.map(v => `<span class="tag ${cls(v)}">${v}</span>`), `<b>${a.sav_total}</b>`],
      ['House', ...a.sav.map((_, i) => (i - L + 12) % 12 + 1), ''], ...P7.map(p => [pn(p, 1), ...a.bav[p], a.bav[p].reduce((x, y) => x + y, 0)])], [...Array(13).keys()].slice(1)) + `<div class="note">${esc(a.method || 'parashara')} tables</div>`; }, { kw: 'sav bindus' });
  P7.concat(['Lagna']).forEach(p => add('bav' + p, `BAV · ${p}`, G.ak, 1, () => { const b = S.c.ashtakavarga.bav[p]; if (!b) return '<p class="note">Not calculated.</p>';
    const L = S.c.lagna.sign_index; return chartSVG(L, {}, { sav: b.map((_, i) => b[(L + i) % 12]), label: 'BAV ' + p }) + `<div class="note">Total ${b.reduce((x, y) => x + y, 0)} · numbers per house</div>`; }, { kw: 'bhinna ' + p }));

  // Vimshottari
  add('dnow', 'Current dasha', G.vim, 1, () => { const d = dashaAt(S.time);
    return d.map((x, i) => `<div class="bar" style="grid-template-columns:86px 1fr 96px"><span style="color:var(--mut)">${LV[i]}</span>${pn(x.lord)}<span class="note" style="margin:0;text-align:right">to ${dt(x.end.toISOString())}</span></div>`).join('') +
      `<div class="note">At ${S.time.toLocaleString([], { dateStyle: 'medium', timeStyle: 'short' })}</div>`; }, { time: true, kw: 'vimshottari running' });
  add('dlist', 'Mahadasha periods', G.vim, 2, () => { const now = S.time, all = S.c.dasha || [], t0 = +new Date(all[0].start), t1 = +new Date(all[all.length - 1].end);
    const rib = `<div class="ribbon">${all.map(d => `<i style="flex:${(new Date(d.end) - new Date(d.start))};background:${col(d.lord)};opacity:${now >= new Date(d.start) && now < new Date(d.end) ? 1 : .35}" title="${d.lord}"></i>`).join('')}<span class="now" style="left:${(now - t0) / (t1 - t0) * 100}%"></span></div>`;
    return rib + all.map(d => { const on = now >= new Date(d.start) && now < new Date(d.end);
      return `<details${on ? ' open' : ''}><summary>${pn(d.lord)} · ${VIM_YRS[d.lord]} yrs · ${dt(d.start)} – ${dt(d.end)}</summary>${tbl(['Antardasha', 'Starts', 'Ends'], (d.children || []).map(a => [pn(a.lord) + (now >= new Date(a.start) && now < new Date(a.end) ? ' <span class="tag good">now</span>' : ''), dt(a.start), dt(a.end)]))}</details>`; }).join(''); }, { time: true, kw: 'mahadasha antardasha' });

  // Shadbala
  const sbRow = (title, f, unit = '') => async () => { const sb = await need('SB'), mx = Math.max(...P7.map(p => f(sb.planets[p]))) || 1;
    return P7.map(p => { const v = f(sb.planets[p]); return `<div class="bar">${pn(p)}<div class="bt"><i style="width:${v / mx * 100}%;background:${col(p)}"></i></div><span class="n" style="text-align:right">${v.toFixed(1)}${unit}</span></div>`; }).join('') + `<div class="note">${title}</div>`; };
  add('sbt', 'Shadbala totals', G.sb, 2, async () => { const sb = await need('SB'), MX = 12;
    return P7.map(p => { const s = sb.planets[p]; return `<div class="bar" style="grid-template-columns:70px 1fr 150px">${pn(p)}<div class="bt"><i style="width:${Math.min(s.rupas / MX, 1) * 100}%;background:${col(p)}${s.rupas < s.required ? '99' : ''}"></i><span class="mk" style="left:${s.required / MX * 100}%"></span></div><span style="text-align:right">${s.rupas.toFixed(2)} r · ${s.ratio.toFixed(2)}× · #${s.rank}</span></div>`; }).join('') +
      '<div class="note">Rupas against the classical minimum (white line) · ratio · rank. For study.</div>'; }, { kw: 'six strength rupa' });
  add('sbsthana', 'Sthana Bala', G.sb, 1, async () => { const sb = await need('SB');
    return tbl(['Planet', 'Uchcha', 'Sapta', 'Oja', 'Kendra', 'Drek', 'Total'], P7.map(p => { const x = sb.planets[p].sthana; return [pn(p, 1), x.uchcha, x.saptavarga, x.ojayugma, x.kendra, x.drekkana, `<b>${x.total}</b>`]; }), [1, 2, 3, 4, 5, 6]); }, { kw: 'positional' });
  add('sbkala', 'Kala Bala', G.sb, 2, async () => { const sb = await need('SB'), K = ['nathonnatha', 'paksha', 'tribhaga', 'abda', 'masa', 'vara', 'hora', 'ayana', 'yuddha'];
    return tbl(['Planet', 'Natonnata', 'Paksha', 'Tribhaga', 'Abda', 'Masa', 'Vara', 'Hora', 'Ayana', 'Yuddha', 'Total'], P7.map(p => { const x = sb.planets[p].kala; return [pn(p, 1), ...K.map(k => x[k]), `<b>${x.total}</b>`]; }), [...Array(11).keys()].slice(1)); }, { kw: 'temporal' });
  add('sbchesta', 'Cheshta Bala', G.sb, 1, async () => { const sb = await need('SB'), ch = S.c.cheshta && S.c.cheshta.planets || {};
    return tbl(['Planet', 'Virupas', 'Motion'], P7.map(p => [pn(p), sb.planets[p].cheshta, esc(ch[p] ? `${ch[p].name} (${ch[p].plain})` : '–')]), [1]); }, { kw: 'motional chesta' });
  add('sbdig', 'Dig Bala', G.sb, 1, sbRow('Directional strength (virupas)', x => x.dig), { kw: 'directional' });
  add('sbdrik', 'Drik Bala', G.sb, 1, async () => { const sb = await need('SB');
    return tbl(['Planet', 'Virupas'], P7.map(p => [pn(p), `<span style="color:${sb.planets[p].drik < 0 ? 'var(--red)' : 'var(--teal)'}">${sb.planets[p].drik}</span>`]), [1]) + '<div class="note">Aspect strength: benefic minus malefic</div>'; }, { kw: 'aspectual' });
  add('sbnais', 'Naisargik Bala', G.sb, 1, sbRow('Natural strength (virupas)', x => x.naisargika), { kw: 'natural' });
  add('sbik', 'Ishta & Kashta phala', G.sb, 1, async () => { const sb = await need('SB');
    return tbl(['Planet', 'Ishta', 'Kashta'], P7.map(p => [pn(p), `<span style="color:var(--teal)">${sb.planets[p].ishta}</span>`, `<span style="color:var(--red)">${sb.planets[p].kashta}</span>`]), [1, 2]); }, { kw: 'good bad results' });
  add('bhavab', 'Bhava Bala', G.sb, 2, async () => { const sb = await need('SB'), mx = Math.max(...sb.bhavas.map(b => b.rupas));
    return sb.bhavas.map(b => `<div class="bar" style="grid-template-columns:96px 1fr 92px"><span>House ${b.house} · ${pn(b.lord, 1)}</span><div class="bt"><i style="width:${b.rupas / mx * 100}%;background:var(--gold)"></i></div><span style="text-align:right">${b.rupas.toFixed(2)} r · #${b.rank}</span></div>`).join('') + '<div class="note">Lord + direction + aspects, per house</div>'; }, { kw: 'house strength' });

  // Drishti
  add('drishti', 'Drishti matrix', G.dr, 2, () => { const A = S.c.strength.aspects;
    return `<div class="mtx" style="grid-template-columns:repeat(10,1fr)"><div style="background:none">→</div>${P9.map(p => `<div style="background:none">${pn(p, 1)}</div>`).join('')}${P9.map(r =>
      `<div style="background:none">${pn(r, 1)}</div>${P9.map(c => { const on = A[r] && A[r].planets.includes(c); return r === c ? '<div>·</div>' : `<div style="${on ? `background:${tint(col(r), 20)};color:${col(r)}` : ''}">${on ? '●' : ''}</div>`; }).join('')}`).join('')}</div>
      <div class="note">Row aspects column (sign aspects).</div>${tbl(['Planet', 'Aspects houses'], P9.map(p => [pn(p), (A[p] ? A[p].houses : []).join(', ') || '–']))}`; }, { kw: 'aspects graha drishti' });

  // D1 with every aspect drawn as an arrow, and the exchanges of lordship
  add('d1asp', 'D1 with aspects', G.dr, 2, el => {
    const L = S.c.lagna.sign_index, A = S.c.strength.aspects, off = new Set((el.dataset.off || '').split(',').filter(Boolean));
    const flags = (p, g) => { const d = dignity(p, g.sign_index), f = [];
      if (retro(p, g) || ((p === 'Rahu' || p === 'Ketu') && g.retrograde)) f.push('<tspan style="fill:var(--teal)" font-weight="700" font-size="11"> R</tspan>');
      if (g.combust) f.push('<tspan style="fill:var(--amber)" font-weight="700" font-size="11"> c</tspan>');
      if (d === 'debilitated') f.push('<tspan style="fill:var(--red)" font-size="11"> ▼</tspan>'); else if (d === 'exalted') f.push('<tspan style="fill:var(--teal)" font-size="11"> ▲</tspan>');
      return f.join(''); };
    const o = {}; P9.forEach(p => { const g = S.c.grahas[p], h = (g.sign_index - L + 12) % 12; (o[h] = o[h] || []).push({ t: AB[p], p, d: Math.floor(g.degrees_in_sign) + '°', f: flags(p, g) }); });
    const j = S.c.jaimini; [[j.arudha_lagna && j.arudha_lagna.house, 'AL'], [j.upapada && j.upapada.house, 'UL']].forEach(([h, t]) => { if (h) (o[h - 1] = o[h - 1] || []).push({ t, c: 'var(--teal)' }); });
    let svg = chartSVG(L, o, { deg: true, label: 'D1 aspects' });
    // arrows: from the planet's house to each house it aspects, in the planet's colour, bowed so they do not overlap
    let arr = '', k = 0;
    P9.forEach(p => { if (off.has(p) || !A[p]) return; const from = (S.c.grahas[p].sign_index - L + 12) % 12;
      A[p].houses.forEach(hn => { const to = hn - 1, [x1, y1] = NP[from], [x2, y2] = NP[to], mx = (x1 + x2) / 2, my = (y1 + y2) / 2, dx = x2 - x1, dy = y2 - y1, len = Math.hypot(dx, dy) || 1;
        const bow = 34 + (k++ % 3) * 14, cx = mx - dy / len * bow, cy = my + dx / len * bow, c = col(p);
        arr += `<path data-p="${p}" d="M${x1} ${y1 - 8}Q${cx} ${cy} ${x2} ${y2 - 2}" fill="none" style="stroke:${c}" stroke-width="1.3" stroke-opacity=".55" stroke-linecap="round" marker-end="url(#ah-${AB[p]})"/>`; }); });
    const defs = '<defs>' + P9.map(p => `<marker id="ah-${AB[p]}" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="5" markerHeight="5" orient="auto-start-reverse"><path d="M0 1L10 5L0 9z" style="fill:${col(p)}" fill-opacity=".75"/></marker>`).join('') + '</defs>';
    svg = svg.replace(/<rect /, defs + '<rect ').replace('</svg>', arr + '</svg>');
    const toggles = `<div class="tc" style="margin-bottom:6px">${P9.map(p => `<button class="btn" data-asp="${p}" style="padding:3px 8px;${off.has(p) ? 'opacity:.4' : `border-color:${tint(col(p), 40)}`}"><span style="color:${col(p)};font-weight:700">${AB[p]}</span></button>`).join('')}<button class="btn" data-asp="*" style="padding:3px 8px">All</button></div>`;
    return toggles + svg + '<div class="note">Arrows: each planet to the houses it aspects (7th for all; Mars 4 · 8, Jupiter 5 · 9, Saturn 3 · 10; Rahu and Ketu per the chart setting) · R retrograde · c combust · ▼ debilitated · ▲ exalted · AL / UL Arudha and Upapada</div>'; }, { kw: 'drishti aspects arrows' });
  G.lord = 'Lordship';
  add('lordx', 'Exchange of lordships', G.lord, 2, () => {
    const ex = S.c.exchanges || {}, row = e => [e.planets.map(p => pn(p)).join(' ⇄ '), `houses ${e.houses.join(' ⇄ ')}`, `<span class="tag ${e.type === 'Maha' ? 'good' : e.type === 'Dainya' ? 'bad' : 'mid'}">${esc(e.type)}</span>`];
    const sec = (t, list) => `<p class="note" style="margin:6px 0 2px;color:var(--gold)">${t}</p>` + (list && list.length ? tbl(['Planets', 'Houses', 'Kind'], list.map(row)) : '<p class="note" style="margin:0">No exchange.</p>');
    const nl = p => (S.c.grahas[p].kp || {}).star_lord || S.c.grahas[p].nakshatra_lord, star = [];
    P9.forEach((a, i) => P9.slice(i + 1).forEach(b => { if (nl(a) === b && nl(b) === a) star.push([pn(a) + ' ⇄ ' + pn(b), `${esc(S.c.grahas[a].nakshatra)} · ${esc(S.c.grahas[b].nakshatra)}`]); }));
    const lords = tbl(['House', 'Sign', 'Lord', 'Sits in house'], S.c.lords.map(x => [`<b>${x.house}</b>`, SA[x.sign_index], pn(x.lord), `<b>${x.lord_in}</b>` + (x.lord_in === x.house ? ' <span class="tag good">own house</span>' : '')]));
    return sec('Parivartana · D1 (sign exchange)', ex.D1) + sec('Parivartana · D9', ex.D9) +
      `<p class="note" style="margin:6px 0 2px;color:var(--gold)">Nakshatra exchange</p>` + (star.length ? tbl(['Planets', 'Nakshatras'], star) : '<p class="note" style="margin:0">No exchange.</p>') +
      `<p class="note" style="margin:8px 0 2px;color:var(--gold)">Where each house lord sits</p>` + lords +
      '<div class="note">Maha: between good houses · Dainya: one house is 6, 8 or 12 · Khala: one house is the 3rd</div>'; }, { kw: 'parivartana exchange lords mutual' });

  // Yogini, Chara, Narayana
  add('ynow', 'Current Yogini dasha', G.yog, 1, () => { const y = S.c.yogini;
    return kv([['Yogini', `<b>${esc(y.current.yogini)}</b> · ${pn(y.current.planet)}`], ['Until', dt(y.current.end)], ['Sub', y.sub ? `${esc(y.sub.yogini)} · ${pn(y.sub.planet)}` : '–'], ['Next', y.next ? `${esc(y.next.yogini)} · ${pn(y.next.planet)}` : '–']]) + `<div class="note">${esc(y.current.text)}</div>`; }, { kw: 'yogini' });
  add('ylist', 'Yogini mahadasha list', G.yog, 1, () => tbl(['Yogini', 'Planet', 'Years', 'From', 'To'], S.c.yogini.timeline.map(y => [esc(y.yogini), pn(y.planet, 1), y.years, dt(y.start), dt(y.end)]), [2]), { kw: 'yogini timeline' });
  add('chara', 'Chara dasha (Jaimini)', G.jai, 1, () => tbl(['Sign', 'House', 'Years', 'From', 'To'], S.c.chara.timeline.map(x => [esc(x.sign), x.house, x.years, dt(x.start), dt(x.end)]), [1, 2]), { kw: 'chara jaimini' });
  add('narayana', 'Narayana dasha', G.jai, 1, () => tbl(['Sign', 'House', 'Years', 'From'], S.c.narayana.periods.map(x => [esc(x.sign), x.house, x.years, dt(x.start)]), [1, 2]) + `<div class="note">Starts from ${esc(S.c.narayana.start_sign)} (${esc(S.c.narayana.from)})</div>`, { kw: 'narayana' });
  add('arudha', 'Arudha padas', G.jai, 2, () => { const j = S.c.jaimini;
    return tbl(['Pada', 'Sign', 'In house', 'Planets', 'Shows'], j.arudhas.map(a => [`<b>${esc(a.short)}</b>`, esc(a.sign), a.in_house, (a.planets || []).map(p => pn(p, 1)).join(' ') || '–', `<span style="color:var(--mut)">${esc(a.shows)}</span>`])) +
      `<div class="note">Karakamsa: ${esc(typeof j.karakamsa === 'object' ? (j.karakamsa.sign || '') : j.karakamsa)} · AL ${esc((j.arudha_lagna || {}).sign || '')} · UL ${esc((j.upapada || {}).sign || '')}</div>`; }, { kw: 'arudha upapada karakamsa' });

  // Sade Sati
  add('ssnow', 'Sade Sati status', G.ss, 1, async () => { const s = (await need('T')).sade_sati.status;
    return kv([['Moon sign', esc(s.moon_sign)], ['Saturn in', `${esc(s.saturn_sign)} · ${s.house_from_moon} from Moon`], ['Sade Sati', s.in_sade_sati ? `<span class="tag mid">${esc(s.phase)}</span>` : '<span class="tag good">No</span>'],
      ['Dhaiya', s.in_dhaiya ? `<span class="tag mid">${esc(s.in_dhaiya)}</span>` : 'No'], ['Next Sade Sati', dt(s.next_sade_sati)]]) + '<div class="note">As of today</div>'; }, { kw: 'saturn shani' });
  add('ssep', 'Sade Sati episodes', G.ss, 2, async () => { const e = (await need('T')).sade_sati.episodes;
    return tbl(['From', 'To', 'Phases'], e.map(x => [dt(x.start) + (x.from_birth ? ' (birth)' : ''), dt(x.end), x.phases.map(p => `<span class="tag ${p.phase === 'Peak' ? 'mid' : 'neu'}">${p.phase} ${p.start.slice(0, 4)}–${p.end.slice(0, 4)}</span>`).join('')])); }, { kw: 'sade sati life' });
  add('ssdh', 'Saturn dhaiyas', G.ss, 1, async () => tbl(['Dhaiya', 'From', 'To'], (await need('T')).sade_sati.dhaiyas.map(d => [esc(d.kind), dt(d.start), dt(d.end)])), { kw: 'kantaka ashtama' });

  // Gochar
  add('gtime', 'Gochar time control', G.go, 2, () => { const d0 = new Date(), off = Math.round((S.time - d0) / 864e5);
    return `<div class="tc"><button class="btn" data-step="-30">−30d</button><button class="btn" data-step="-1">‹ Day</button>
      <input type="range" min="-1825" max="1825" step="1" value="${Math.max(-1825, Math.min(1825, off))}" id="gslider" aria-label="Days from today">
      <button class="btn" data-step="1">Day ›</button><button class="btn" data-step="30">+30d</button><button class="btn" data-step="now">Today</button>
      <button class="btn" id="gplay" aria-pressed="${!!S.timer}">${S.timer ? '❚❚ Pause' : '▶ Play'}</button>
      <input type="datetime-local" id="gdate" value="${new Date(S.time - S.time.getTimezoneOffset() * 6e4).toISOString().slice(0, 16)}" class="sel"></div>
      <div class="note">Drives every timing widget: Gochar, current Dasha, ruling planets. ±5 years.</div>`; }, { time: true, kw: 'time travel slider' });
  add('gchart', 'Gochar chart', G.go, 1, async () => { const g = await gochar(), L = S.c.lagna.sign_index, o = {};
    g.planets.forEach(x => { const h = (x.sign_index - L + 12) % 12; (o[h] = o[h] || []).push({ t: AB[x.planet] + (x.retrograde && x.planet !== 'Rahu' && x.planet !== 'Ketu' ? 'ᴿ' : ''), p: x.planet }); });
    return chartSVG(L, o, { label: 'Transit' }) + `<div class="note">${dt(g.date)} · in houses from the natal Lagna</div>`; }, { time: true, kw: 'transit chart' });
  add('gpos', 'Gochar positions', G.go, 2, async () => { const g = await gochar();
    return tbl(['Planet', 'Sign', 'Degree', 'Nakshatra', 'Star', 'Sub', 'From Lagna', 'From Moon', 'SAV'], g.planets.map(x => [pn(x.planet) + (x.retrograde ? ' ℞' : ''), SA[x.sign_index], dm(x.deg), `${esc(x.nakshatra)} ${x.pada}`, pn(x.star_lord, 1), pn(x.sub_lord, 1), x.h_lagna, x.h_moon, x.sav]), [6, 7, 8]); }, { time: true, kw: 'transit positions' });
  add('gbasic', 'Gochar basics', G.go, 1, async () => { const g = await gochar();
    return g.notes.map(n => `<div style="margin:4px 0"><span class="tag ${n.kind === 'good' ? 'good' : n.kind === 'bad' ? 'bad' : 'neu'}">${esc(n.kind)}</span> ${esc(n.text)}</div>`).join('') || '<p class="note">Nothing notable.</p>'; }, { time: true, kw: 'transit notes' });

  // KP
  add('kpcusp', 'KP cusps', G.kp, 2, () => tbl(['Cusp', 'Sign', 'Degree', 'Sign lord', 'Star', 'Sub', 'Sub-sub'], S.c.houses.map(h => { const k = h.kp || {};
    return [`<b>${h.house}</b>`, SA[h.sign_index], dms(h.degrees_in_sign), pn(k.sign_lord || h.sign_lord, 1), pn(k.star_lord, 1), pn(k.sub_lord, 1), k.sub_sub_lord ? pn(k.sub_sub_lord, 1) : '–']; })) + `<div class="note">${esc(S.c.meta.house_system)} cusps</div>`, { kw: 'cuspal sub lord' });
  add('kpsigh', 'KP significators by house', G.kp, 2, () => tbl(['House', 'Significators'], Object.entries(S.c.significators.by_house).map(([h, ps]) => [`<b>${h}</b>`, ps.map(p => pn(p, 1)).join(' ')])), { kw: 'significator house' });
  add('kpsigp', 'KP significations by planet', G.kp, 2, () => tbl(['Planet', 'Star lord occupies', 'Star lord owns', 'Occupies', 'Owns', 'All houses'], P9.map(p => { const x = S.c.significators.by_planet[p] || {};
    return [pn(p), (x.occupied_by_star_lord || []).join(', '), (x.owned_by_star_lord || []).join(', '), (x.occupied || []).join(', '), (x.owned || []).join(', '), `<b>${(x.houses || []).join(', ')}</b>`]; })), { kw: 'four levels' });
  add('ruling', 'Ruling planets', G.kp, 1, async () => { const r = await ruling();
    return tbl(['Role', 'Planet'], r.rows.map(x => [esc(x.role), pn(x.planet)])) + `<div class="note">Ruling: ${r.ruling_planets.map(p => pn(p, 1)).join(' ')} · at the time control's moment, birthplace</div>`; }, { time: true, kw: 'rp horary' });

  // Yogas
  add('yogas', 'Yogas · checked', G.yg, 2, () => tbl(['Yoga', 'Planets', 'Status', 'Meaning'], S.c.yoga_check.yogas.map(y => [`<b>${esc(y.name)}</b>`, (y.planets || []).map(p => pn(p, 1)).join(' '), `<span class="tag ${tone(y.status)}">${esc(y.status)}</span>`,
    `<span style="color:var(--mut);white-space:normal">${esc(y.meaning)}</span>`])), { kw: 'raja dhana combinations' });

  // Ours only
  const TOPICS = [['career', 'Career'], ['money', 'Money'], ['marriage', 'Marriage'], ['property', 'Property'], ['foreign', 'Abroad'], ['job_change', 'Job change'], ['children', 'Children'], ['education', 'Education'], ['business', 'Business'], ['health', 'Health']];
  add('kpwin', 'KP event windows', G.ours, 2, async el => { const topic = el.dataset.topic || 'career', g = await life(topic);
    const best = new Set((g.best_ahead || []).map(b => b[0])), now = S.time;
    const sel = `<select class="sel" data-topic-sel>${TOPICS.map(([k, n]) => `<option value="${k}"${k === topic ? ' selected' : ''}>${n}</option>`).join('')}</select>`;
    return `${sel} <span class="tag ${/not/.test(g.promise.verdict) ? 'bad' : 'good'}">${esc(g.promise.verdict)}</span> <span class="note">cusp ${g.promise.cusp} sub lord ${pn(g.promise.cusp_sub_lord, 1)}</span>` +
      tbl(['Period', 'From', 'To', 'Verdict', 'Score'], g.windows.filter(w => new Date(w.ends) >= now).slice(0, 12).map(w => [`${pn(w.maha, 1)}›${pn(w.antar, 1)}›${pn(w.praty, 1)}${best.has(w.starts) ? ' <span class="tag good">best</span>' : ''}`, dt(w.starts), dt(w.ends), `<span class="tag ${tone(w.verdict)}">${esc(w.verdict)}</span>`, w.score]), [4]); }, { kw: 'timing prediction windows' });
  add('bnn', 'BNN trines', G.ours, 2, () => tbl(['Element', 'Signs', 'Planets'], S.c.bnn.trines.map(t => [esc(t.element), t.signs.map(s => s.slice(0, 3)).join(' · '), t.planets.map(p => pn(p.planet, 1) + (p.retro ? 'ᴿ' : '') + (p.also ? '*' : '')).join(' ') || '–'])) + '<div class="note">Bhrigu Nandi Nadi · * also acts from the sign before (retrograde)</div>', { kw: 'bhrigu nandi nadi' });
  add('nadi', 'Nadi amsha · D150', G.ours, 1, () => { const v = S.c.vargas.D150; return v ? vargaChart('D150') : '<p class="note">Not available.</p>'; }, { kw: 'nadi d150' });
  add('lalkitab', 'Lal Kitab houses', G.ours, 1, async () => { const lk = await need('LK'), o = {};
    Object.entries(lk.houses).forEach(([h, ps]) => { o[+h - 1] = ps.map(p => ({ t: AB[p] || p, p })); });
    return chartSVG(0, o, { houseSigns: [...Array(12).keys()], label: 'Lal Kitab' }) + '<div class="note">Fixed houses: Aries = house 1</div>'; }, { kw: 'lal kitab' });
  add('tajika', 'Varshaphal (Tajika)', G.ours, 1, async () => { const t = await need('TJ');
    return kv([['Year from', dt(t.varsha_pravesh)], ['Age', t.age], ['Varsha Lagna', esc((t.lagna || {}).sign || '–')], ['Muntha', esc((t.muntha || {}).sign || '–') + (t.muntha && t.muntha.house ? ' · house ' + t.muntha.house : '')],
      ['Year lord', t.year_lord ? pn(t.year_lord.planet || t.year_lord) : '–']]); }, { kw: 'annual tajika varsha' });

  // Nadi · KP (the classic KP / Nadi software screens)
  G.nadi = 'Nadi · KP';
  const VORDER = [['Ketu', 'Moon', 'Jupiter'], ['Venus', 'Mars', 'Saturn'], ['Sun', 'Rahu', 'Mercury']];
  const fullDT = (d, tz) => d.toLocaleString('en-GB', { day: '2-digit', month: '2-digit', year: 'numeric', hour: '2-digit', minute: '2-digit', second: '2-digit', hour12: false, timeZone: tz }).replace(',', '');
  add('nlagdeg', 'Lagna chart with degrees', G.nadi, 1, () => { const L = S.c.lagna.sign_index, o = byHouse(NATAL, L, [], true);
    (o[0] = o[0] || []).unshift({ t: 'Asc', d: dm(S.c.lagna.ascendant % 30) }); return chartSVG(L, o, { deg: true, label: 'D1' }); }, { kw: 'degrees rasi nadi' });
  add('ncusp', 'Nirayana cusps chart', G.nadi, 1, () => { const o = {};
    P9.forEach(p => { const g = S.c.grahas[p], h = g.house - 1; (o[h] = o[h] || []).push({ t: AB[p] + retro(p, g), p, d: dm(g.degrees_in_sign) }); });
    return chartSVG(0, o, { deg: true, houseSigns: S.c.houses.map(h => h.sign_index), cuspDeg: S.c.houses.map(h => dm(h.degrees_in_sign)), label: 'Cusps' }) +
      `<div class="note">Planets in their bhava · sign number and cusp degree in each house · ${esc(S.c.meta.house_system)}</div>`; }, { kw: 'bhava cusps nirayana' });
  // Events read on the grid: houses that support (green) and houses that negate (red), as in the KP / Nadi tables
  const EVENTS = [['marriage', 'Marriage', [2, 7, 11], [1, 6, 10]], ['divorce', 'Divorce / separation', [1, 6, 10], [2, 7, 11]],
    ['love', 'Love affair (5, 9, 11 or 5, 8, 11)', [5, 8, 9, 11], [6]], ['career', 'Job / promotion', [2, 6, 10, 11], [5, 9]],
    ['job_change', 'Job change', [5, 9], [2, 6, 11]], ['business', 'Business', [2, 7, 10, 11], [1, 6, 9]], ['money', 'Money and gains', [2, 6, 11], [1, 5, 10]],
    ['property', 'Buying property', [4, 11, 12], [3, 10]], ['vehicle', 'Buying a vehicle', [4, 11, 12], [10]], ['foreign', 'Foreign travel / settling', [3, 9, 12], [2, 4, 11]],
    ['children', 'Children', [2, 5, 11], [1, 4, 10]], ['education', 'Education', [4, 9, 11], [6, 8, 12]], ['health', 'Recovery from illness', [1, 5, 9, 11], [6, 8, 12]],
    ['litigation', 'Winning a dispute', [1, 6, 10, 11], [5, 8, 12]]];
  add('nsig3', 'Planet · star · sub houses', G.nadi, 2, el => { const H = S.c.kp_houses, ev = EVENTS.find(e => e[0] === (el.dataset.ev || '')) || null;
    const hs = hh => (hh || []).map(h => ev && ev[2].includes(h) ? `<span style="color:var(--teal);font-weight:800">${h}</span>` : ev && ev[3].includes(h) ? `<span style="color:var(--red);font-weight:800">${h}</span>` : `<span style="${ev ? 'color:var(--dim)' : ''}">${h}</span>`).join(', ') || '–';
    const judge = q => { const hh = H[q] || [], g = ev[2].filter(h => hh.includes(h)).length, b = ev[3].filter(h => hh.includes(h)).length;
      return g && !b ? ['good', 'supports'] : b && !g ? ['bad', 'against'] : g && b ? ['mid', 'mixed'] : ['neu', 'neutral']; };
    const cell = p => { const k = S.c.grahas[p].kp || {}, st = k.star_lord || S.c.grahas[p].nakshatra_lord, sb = k.sub_lord, j = ev ? judge(sb) : null;
      return (j ? `<div style="padding:1px 6px 3px"><span class="tag ${j[0]}">sub lord: ${j[1]}</span></div>` : '') + [p, st, sb].map((q, i) => `<div style="display:grid;grid-template-columns:54px 1fr;gap:4px;padding:2px 6px;${i ? '' : 'background:var(--field);border-radius:5px'}"><span>${pn(q, 1)}${i ? `<span class="note" style="margin:0 0 0 4px">${i === 1 ? 'star' : 'sub'}</span>` : ''}</span><b style="font-weight:${i ? 500 : 700}">${hs(H[q])}</b></div>`).join(''); };
    const sel = `<select class="sel" data-ev-sel><option value="">Show an event…</option>${EVENTS.map(e => `<option value="${e[0]}"${ev && ev[0] === e[0] ? ' selected' : ''}>${e[1]}</option>`).join('')}</select>`;
    const key = ev ? `<span class="note" style="margin-left:8px"><span style="color:var(--teal);font-weight:700">${ev[2].join(', ')}</span> support · <span style="color:var(--red);font-weight:700">${ev[3].join(', ')}</span> negate</span>` : '';
    return `<div style="margin-bottom:6px">${sel}${key}</div><div style="display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:6px">${VORDER.flat().map(p => `<div style="border:1px solid var(--line2);border-radius:8px;padding:3px">${cell(p)}</div>`).join('')}</div>
      <div class="note">Each planet, then its star lord and sub lord, with the houses each signifies by itself (Nadi method) · Vimshottari order${ev ? ' · the sub lord decides: green supports, red works against' : ''}</div>`; }, { kw: 'nadi significator planet star sub event marriage divorce love job' });
  add('nplanet', 'Planet position · KP', G.nadi, 2, () => { const L = S.c.lagna, lk = L.kp || {};
    return tbl(['Planet', 'Sign', 'Degree', 'Sign lord', 'N. lord', 'S. lord', 'S.S. lord'], [[`<b style="color:var(--gold)">Asc</b>`, SA[L.sign_index], dms(L.ascendant % 30), pn(lk.sign_lord, 1), pn(lk.star_lord, 1), pn(lk.sub_lord, 1), lk.sub_sub_lord ? pn(lk.sub_sub_lord, 1) : '–']].concat(
      P9.map(p => { const g = S.c.grahas[p], k = g.kp || {}; return [pn(p) + (retro(p, g) ? '-R' : ''), SA[g.sign_index], dms(g.degrees_in_sign), pn(k.sign_lord || g.sign_lord, 1), pn(k.star_lord || g.nakshatra_lord, 1), k.sub_lord ? pn(k.sub_lord, 1) : '–', k.sub_sub_lord ? pn(k.sub_sub_lord, 1) : '–']; }))); }, { kw: 'sub sub lord ss' });
  add('nprime', 'Prime significators · 4 levels', G.nadi, 2, () => { const B = S.c.significators.by_planet, star = p => (S.c.grahas[p].kp || {}).star_lord || S.c.grahas[p].nakshatra_lord;
    const occ = h => P9.filter(p => (B[p].occupied || []).includes(h)), own = h => P9.filter(p => (B[p].owned || []).includes(h)), inStar = set => P9.filter(p => set.includes(star(p)));
    const L = ps => ps.length ? ps.map(p => pn(p, 1)).join(' ') : '–';
    return tbl(['House', 'L1 · in star of occupants', 'L2 · occupants', 'L3 · in star of owner', 'L4 · owner'], [...Array(12).keys()].map(i => { const h = i + 1, o = occ(h), w = own(h); return [`<b>${h}</b>`, L(inStar(o)), L(o), L(inStar(w)), L(w)]; })) +
      '<div class="note">KP significator levels, strongest first</div>'; }, { kw: 'significator levels kp prime' });
  add('nrevolve', 'House revolve', G.nadi, 1, el => { const n = +(el.dataset.rev || 1), L = (S.c.lagna.sign_index + n - 1) % 12;
    return `<select class="sel" data-rev-sel>${[...Array(12).keys()].map(i => `<option value="${i + 1}"${i + 1 === n ? ' selected' : ''}>Treat house ${i + 1} as Lagna</option>`).join('')}</select>` +
      chartSVG(L, byHouse(NATAL, L), { label: 'From H' + n }) + `<div class="note">Bhavat bhavam: houses counted from house ${n} (${SIGNS[L]})</div>`; }, { kw: 'house revolve bhavat bhavam rotate' });
  const ASP = [[0, 'Conjunction', 8], [60, 'Sextile', 6], [90, 'Square', 7], [120, 'Trine', 7], [180, 'Opposition', 8]];
  const aspect = (a, b) => { const d = Math.abs(((a - b) % 360 + 540) % 360 - 180); const sep = 180 - d; for (const [ang, n, orb] of ASP) { if (Math.abs(sep - ang) <= orb) return [n, Math.abs(sep - ang)]; } return null; };
  add('naspp', 'Aspects to planets', G.nadi, 2, () => { const rows = [];
    P9.forEach((p, i) => P9.slice(i + 1).forEach(q => { if ((p === 'Rahu' && q === 'Ketu')) return; const a = aspect(S.c.grahas[p].longitude, S.c.grahas[q].longitude); if (a) rows.push([pn(p), esc(a[0]), pn(q), dm(a[1]), a[1]]); }));
    rows.sort((x, y) => x[4] - y[4]); return tbl(['Planet', 'Aspect', 'Planet', 'Orb'], rows.map(r => r.slice(0, 4)), [3]) + '<div class="note">By degree: 0°, 60°, 90°, 120°, 180° within 6–8°, tightest first</div>'; }, { kw: 'aspplanet degree aspects' });
  add('naspc', 'Aspects to cusps', G.nadi, 2, () => { const rows = [];
    P9.forEach(p => S.c.houses.forEach(h => { const a = aspect(S.c.grahas[p].longitude, h.longitude); if (a) rows.push([pn(p), esc(a[0]), `<b>Cusp ${h.house}</b>`, dm(a[1]), a[1]]); }));
    rows.sort((x, y) => x[4] - y[4]); return tbl(['Planet', 'Aspect', 'Cusp', 'Orb'], rows.map(r => r.slice(0, 4)), [3]) + '<div class="note">By degree to each cusp, tightest first</div>'; }, { kw: 'aspcusp cusp aspects' });
  const RPNAV = { lvl: 2, focus: null };
  add('ndasha', 'Dasha navigator', G.nadi, 2, () => { const lvl = RPNAV.lvl, f = RPNAV.focus || S.time, chain = dashaAt(f), par = chain[lvl - 1];
    if (!par) return '<p class="note">Outside the Dasha range.</p>';
    const kids = par.children && par.children.length ? par.children.map(norm) : vimSplit(par), tz = S.req.tz_name, now = S.time;
    return `<div class="tc" style="margin-bottom:4px"><b style="flex:1">${chain.slice(0, lvl).map(x => pn(x.lord, 1)).join(' › ')}</b>${['B', 'A', 'S', 'P'].map((k, i) => `<button class="btn" data-nlvl="${i + 1}" style="${lvl === i + 1 ? 'border-color:var(--gold);color:var(--gold)' : ''}" title="${['Bhukti', 'Antara', 'Sookshma', 'Prana'][i]}">${k}</button>`).join('')}<button class="btn" data-nmove="-1">‹‹</button><button class="btn" data-nmove="1">››</button></div>` +
      tbl(['', 'From', 'To'], kids.map(k => [pn(k.lord), fullDT(k.start, tz), fullDT(k.end, tz)].map((c, i) => now >= k.start && now < k.end ? `<b>${c}</b>` : c)).map((r, i) => [r[0], r[1], r[2]])) +
      `<div class="note">B Bhukti · A Antara · S Sookshma · P Prana · times in ${esc(tz)} · ‹‹ ›› step the period above</div>`; }, { time: true, kw: 'dasha bhukti antara sookshma prana navigator' });
  add('nrp2', 'Ruling planets · birth and now', G.nadi, 1, async () => { const L = S.c.lagna.kp || {}, M = S.c.grahas.Moon.kp || {}, bx = await need('BX');
    const vara = (bx.avakhada.rows.find(x => x.label === 'Birth day (Vedic)') || {}).value, DL = { Sunday: 'Sun', Monday: 'Moon', Tuesday: 'Mars', Wednesday: 'Mercury', Thursday: 'Jupiter', Friday: 'Venus', Saturday: 'Saturn' };
    const at = here() || { lat: S.req.lat, lon: S.req.lon, tz_name: S.req.tz_name, name: (S.req.place || '').split(',')[0] }, r = await ruling(at);
    const role = re => { const x = r.rows.find(y => re.test(y.role)); return x ? x.planet : null; };
    const trio = (a, b, c) => [a, b, c].map(p => p ? pn(p, 1) : '–').join(' / ');
    return `<p class="note" style="margin:0 0 3px">Birth time · ${esc(S.req.dob)} ${esc((S.req.tob || '').slice(0, 5))}</p>` + kv([['Asc lord / star / sub', trio(L.sign_lord, L.star_lord, L.sub_lord)], ['Moon lord / star / sub', trio(M.sign_lord, M.star_lord, M.sub_lord)], ['Day lord', DL[vara] ? pn(DL[vara], 1) : '–']]) +
      `<p class="note" style="margin:8px 0 3px">Now · ${esc(at.name || 'your place')} · ${S.time.toLocaleString([], { dateStyle: 'medium', timeStyle: 'medium' })}</p>` +
      kv([['Asc lord / star / sub', trio(role(/Lagna sign/), role(/Lagna star/), r.lagna && r.lagna.sub_lord)], ['Moon lord / star / sub', trio(role(/Moon sign/), role(/Moon star/), r.moon && r.moon.sub_lord)], ['Day lord', role(/Day/) ? pn(role(/Day/), 1) : '–']]); }, { time: true, kw: 'ruling planets rp birth now' });
  const UNITS = [['Year', 'y'], ['Month', 'mo'], ['Day', 864e5], ['Hour', 36e5], ['10 Min', 6e5], ['Minute', 6e4], ['10 Sec', 1e4], ['Second', 1e3]];
  add('ntime', 'Time tool', G.nadi, 1, () => `<div style="display:grid;grid-template-columns:auto auto 1fr;gap:4px 6px;align-items:center">${UNITS.map(([n, u]) => `<button class="btn" data-tt="${u}" data-sg="1">＋</button><button class="btn" data-tt="${u}" data-sg="-1">−</button><span>${n}</span>`).join('')}</div>
    <div class="tc" style="margin-top:6px"><button class="btn" data-tt="birth">Birth time</button><button class="btn" data-tt="now">Now</button><label style="display:flex;gap:5px;align-items:center"><input type="checkbox" data-clock${S.clock ? ' checked' : ''}> Live clock</label></div>
    <div class="note">${fullDT(S.time, S.req.tz_name)} · ${esc(S.req.tz_name)}</div>`, { time: true, kw: 'time tool seconds horary rectify' });

  // ----- presets -----
  const PRESETS = {
    parashari: ['d1sav:1', 'd9:1', 'panchang:1', 'moonq:1', 'spasht:2', 'dnow:1', 'ynow:1', 'sbt:2', 'sav:2', 'yogas:2', 'vimsho:2', 'drishti:2', 'dlist:2'],
    kp: ['chalit:1', 'kpcusp:2', 'ruling:1', 'spasht:2', 'kpsigh:2', 'kpsigp:2', 'kpwin:2', 'dnow:1', 'gtime:2', 'gpos:2'],
    nadi: ['nlagdeg:1', 'ncusp:1', 'ndasha:2', 'nsig3:2', 'nrp2:1', 'ntime:1', 'nplanet:2', 'kpcusp:2', 'nprime:2', 'naspp:2', 'naspc:2', 'nrevolve:1', 'bnn:2', 'kpwin:2'],
    prashna: ['ruling:1', 'gchart:1', 'dnow:1', 'gbasic:1', 'gtime:2', 'gpos:2'],
    transit: ['gtime:2', 'gchart:1', 'dnow:1', 'gpos:2', 'gbasic:1', 'ssnow:1', 'ssep:2', 'ssdh:1', 'd1sav:1', 'sav:2'],
    strength: ['sbt:2', 'bhavab:2', 'sbsthana:2', 'sbkala:2', 'sbchesta:1', 'sbdig:1', 'sbdrik:1', 'sbnais:1', 'sbik:1', 'vimsho:2', 'baladi:1', 'jagrad:1'],
    all: W.map(w => `${w.id}:${w.w}`),
  };
  const PN = { parashari: 'Parashari reading', kp: 'KP reading', nadi: 'Nadi · BNN', prashna: 'Prashna', transit: 'Transit day', strength: 'Strength', all: 'Every widget' };
  const fromPreset = k => PRESETS[k].map(s => { const [id, w] = s.split(':'); return { id, w: +w }; }).filter(x => W.some(y => y.id === x.id));

  // ----- layout: saved per astrologer on the server, this browser as a fallback -----
  let saveT = null;
  function save() { clearTimeout(saveT); saveT = setTimeout(() => {
    try { localStorage.setItem('sj-pro-layout', JSON.stringify(S.layout)); } catch (e) {}
    fetch('/pro/api/layout', { method: 'PUT', headers: { 'content-type': 'application/json' }, body: JSON.stringify({ widgets: S.layout }) }).catch(() => {}); }, 400); }
  async function loadLayout() {
    try { const r = await api('/pro/api/layout'); if (r.widgets && r.widgets.length) return r.widgets.filter(x => W.some(y => y.id === x.id)); } catch (e) {}
    try { const l = JSON.parse(localStorage.getItem('sj-pro-layout') || 'null'); if (l && l.length) return l; } catch (e) {}
    return fromPreset('parashari');
  }

  // ----- rendering -----
  const byId = id => W.find(w => w.id === id);
  async function paint(card) {
    const w = byId(card.dataset.id), body = card.querySelector('.wb');
    if (!S.c) { body.innerHTML = '<p class="note">Choose a chart.</p>'; return; }
    try { const h = await w.r(body); body.innerHTML = h; body.classList.remove('empty'); }
    catch (e) { body.innerHTML = `<p class="note">Couldn’t load: ${esc(e.message)}</p>`; }
  }
  function cardFor(item) {
    const w = byId(item.id), el = document.createElement('section');
    el.className = 'w'; el.dataset.id = item.id; el.dataset.w = item.w;
    el.innerHTML = `<div class="wh" title="Drag the header to move this widget"><span class="grip" aria-hidden="true">⠿</span><b>${esc(w.t)}</b><small>${['¼', '½', '¾', '1'][item.w - 1]}</small><button data-act="wider" title="Width">⇔</button><button data-act="hide" title="Remove">✕</button></div><div class="wb empty">Loading…</div>`;
    return el;
  }
  function renderAll() {
    const g = $('grid'); g.innerHTML = '';
    S.layout.forEach(it => { if (byId(it.id)) { const c = cardFor(it); g.appendChild(c); paint(c); } });
    if (!S.layout.length) g.innerHTML = '<p class="note">No widgets. Open Customize or press Ctrl K to add some.</p>';
    $('nlay').textContent = S.layout.length; $('nlib').textContent = W.length;
  }
  function repaintTime() { document.querySelectorAll('#grid .w').forEach(c => { const w = byId(c.dataset.id); if (w && w.time) paint(c); }); paintTop(); }
  function setTime(t) { S.time = t; clearTimeout(S.tt); S.tt = setTimeout(repaintTime, 120); $('ctime').textContent = '⏱ ' + t.toLocaleString([], { dateStyle: 'medium', timeStyle: 'short' }); }

  function paintTop() {
    if (!S.c) return;
    const r = S.req, d = dashaAt(S.time);
    $('cbirth').textContent = `${dt(r.dob)} · ${r.tob_unknown ? 'time unknown' : r.tob.slice(0, 5)} · ${(r.place || '').split(',')[0]}`;
    $('cdasha').hidden = !d.length; $('cdasha').textContent = '● ' + d.slice(0, 3).map(x => x.lord).join(' › ');
    $('ctime').textContent = '⏱ ' + S.time.toLocaleString([], { dateStyle: 'medium', timeStyle: 'short' });
    need('PAN').then(p => { const tm = iso => new Date(iso).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', timeZone: r.tz_name }); $('csun').hidden = false; $('csun').textContent = `☀ ${tm(p.sunrise)} · ☾ ${tm(p.sunset)}`; }).catch(() => {});
  }

  async function openChart(id) {
    S.pid = id; S.cache = {}; S.P = await api('/profiles/' + id); S.c = S.P.chart; S.req = S.P.request;
    try { localStorage.setItem('sj-pro-chart', id); } catch (e) {}
    paintTop(); renderAll();
  }

  // ----- interactions on the grid: widths, removal, topic menus, time control, drag-and-drop, linked highlight -----
  const grid = $('grid');
  grid.addEventListener('click', e => {
    const b = e.target.closest('[data-act]'), card = e.target.closest('.w');
    if (b && card) { const it = S.layout.find(x => x.id === card.dataset.id);
      if (b.dataset.act === 'hide') S.layout = S.layout.filter(x => x !== it); else it.w = it.w % 4 + 1;
      save(); if (b.dataset.act === 'hide') card.remove(); else { card.dataset.w = it.w; card.querySelector('.wh small').textContent = ['¼', '½', '¾', '1'][it.w - 1]; paint(card); }
      paintCust(); return; }
    const ab = e.target.closest('[data-asp]');
    if (ab && card) { const body = card.querySelector('.wb'), off = new Set((body.dataset.off || '').split(',').filter(Boolean)), p = ab.dataset.asp;
      if (p === '*') off.clear(); else off.has(p) ? off.delete(p) : off.add(p); body.dataset.off = [...off].join(','); paint(card); return; }
    const nl = e.target.closest('[data-nlvl]'), nm = e.target.closest('[data-nmove]'), tt = e.target.closest('[data-tt]');
    if (nl) { RPNAV.lvl = +nl.dataset.nlvl; RPNAV.focus = null; paint(card); return; }
    if (nm) { const chain = dashaAt(RPNAV.focus || S.time), par = chain[RPNAV.lvl - 1]; if (par) RPNAV.focus = new Date(+nm.dataset.nmove < 0 ? +par.start - 1 : +par.end + 1); paint(card); return; }
    if (tt) { const u = tt.dataset.tt, sg = +tt.dataset.sg || 0, t = new Date(S.time);
      if (u === 'birth') setTime(new Date((S.c.meta.julian_day - 2440587.5) * 864e5));  // the birth moment, from its Julian day
      else if (u === 'now') setTime(new Date());
      else if (u === 'y') { t.setFullYear(t.getFullYear() + sg); setTime(t); } else if (u === 'mo') { t.setMonth(t.getMonth() + sg); setTime(t); } else setTime(new Date(+t + sg * +u));
      RPNAV.focus = null; return; }
    const st = e.target.closest('[data-step]');
    if (st) { const v = st.dataset.step; setTime(v === 'now' ? new Date() : new Date(+S.time + (+v) * 864e5)); return; }
    if (e.target.id === 'gplay') { if (S.timer) { clearInterval(S.timer); S.timer = null; } else S.timer = setInterval(() => setTime(new Date(+S.time + 864e5)), 900); repaintTime(); return; }
    const p = e.target.closest('[data-p]');
    if (p) { S.sel = S.sel === p.dataset.p ? null : p.dataset.p; highlight(); }
  });
  grid.addEventListener('input', e => { if (e.target.id === 'gslider') { const t = new Date(); t.setDate(t.getDate() + +e.target.value); setTime(t); } });
  grid.addEventListener('change', e => {
    if (e.target.id === 'gdate' && e.target.value) setTime(new Date(e.target.value));
    if (e.target.matches('[data-ev-sel]')) { const card = e.target.closest('.w'), body = card.querySelector('.wb'); body.dataset.ev = e.target.value; paint(card); }
    if (e.target.matches('[data-rev-sel]')) { const card = e.target.closest('.w'), body = card.querySelector('.wb'); body.dataset.rev = e.target.value; paint(card); }
    if (e.target.matches('[data-clock]')) { clearInterval(S.clockT); S.clock = e.target.checked; if (S.clock) { setTime(new Date()); S.clockT = setInterval(() => setTime(new Date()), 1000); } }
    if (e.target.matches('[data-topic-sel]')) { const card = e.target.closest('.w'), body = card.querySelector('.wb'); body.dataset.topic = e.target.value; paint(card); }
  });
  function highlight() {
    document.body.toggleAttribute('data-sel', !!S.sel);
    $('csel').hidden = !S.sel; if (S.sel) { $('csel').innerHTML = `Highlight: <b style="color:${col(S.sel)}">${S.sel}</b> ✕`; }
    document.querySelectorAll('[data-p]').forEach(n => n.classList.toggle('sel-on', n.dataset.p === S.sel));
  }
  new MutationObserver(() => { if (S.sel) highlight(); }).observe(grid, { childList: true, subtree: true });
  // ----- drag and drop: grab a card's header and move it; a dashed placeholder shows where it will land.
  // Pointer events, so the same code works with a mouse, a trackpad and touch; the page scrolls near its edges.
  let D = null;
  grid.addEventListener('pointerdown', e => {
    const h = e.target.closest('.wh'); if (!h || e.target.closest('button') || e.button > 0) return;
    const card = h.closest('.w'); D = { card, x0: e.clientX, y0: e.clientY, on: false, id: e.pointerId };
  });
  addEventListener('pointermove', e => {
    if (!D) return;
    if (!D.on) { if (Math.hypot(e.clientX - D.x0, e.clientY - D.y0) < 6) return; startDrag(e); }
    D.x = e.clientX; D.y = e.clientY;
    D.card.style.left = (e.clientX - D.dx) + 'px'; D.card.style.top = (e.clientY - D.dy) + 'px';
    const under = document.elementFromPoint(e.clientX, e.clientY), t = under && under.closest('#grid .w:not(.ghost)');
    if (t && t !== D.ph) { const r = t.getBoundingClientRect(), wide = r.width > grid.clientWidth * 0.6;
      const after = wide ? e.clientY > r.top + r.height / 2 : e.clientX > r.left + r.width / 2;
      grid.insertBefore(D.ph, after ? t.nextSibling : t); }
  });
  function startDrag(e) {
    const r = D.card.getBoundingClientRect(); D.on = true; D.dx = e.clientX - r.left; D.dy = e.clientY - r.top;
    D.ph = document.createElement('div'); D.ph.className = 'w ph'; D.ph.dataset.w = D.card.dataset.w; D.ph.style.height = r.height + 'px';
    grid.insertBefore(D.ph, D.card);
    Object.assign(D.card.style, { width: r.width + 'px', height: r.height + 'px', left: r.left + 'px', top: r.top + 'px' });
    D.card.classList.add('ghost'); document.body.classList.add('dragging'); scrollLoop();
  }
  function scrollLoop() { if (!D || !D.on) return; const m = 70, y = D.y == null ? -1 : D.y;
    if (y >= 0 && y < m) scrollBy(0, -Math.ceil((m - y) / 4)); else if (y > innerHeight - m) scrollBy(0, Math.ceil((y - innerHeight + m) / 4));
    requestAnimationFrame(scrollLoop); }
  function endDrag(cancel) {
    if (!D) return; const d = D; D = null; if (!d.on) return;
    document.body.classList.remove('dragging'); d.card.classList.remove('ghost'); d.card.removeAttribute('style');
    if (!cancel) grid.insertBefore(d.card, d.ph); d.ph.remove();
    if (cancel) return;
    const order = [...grid.querySelectorAll('.w')].map(c => c.dataset.id);
    S.layout.sort((a, b) => order.indexOf(a.id) - order.indexOf(b.id)); save(); paintCust();
  }
  addEventListener('pointerup', () => endDrag(false)); addEventListener('pointercancel', () => endDrag(true));
  addEventListener('keydown', e => { if (e.key === 'Escape' && D && D.on) { endDrag(true); } });
  function move(from, to) {
    if (from === to) return; const a = S.layout.findIndex(x => x.id === from), it = S.layout.splice(a, 1)[0], b = S.layout.findIndex(x => x.id === to);
    S.layout.splice(b, 0, it); save();
    const cf = grid.querySelector(`.w[data-id="${from}"]`), ct = grid.querySelector(`.w[data-id="${to}"]`);
    if (cf && ct) grid.insertBefore(cf, a < b + 1 && a <= b ? ct.nextSibling : ct); paintCust();
  }
  function addWidget(id) {
    if (S.layout.some(x => x.id === id)) { const c = grid.querySelector(`.w[data-id="${id}"]`); if (c) c.scrollIntoView({ behavior: 'smooth', block: 'center' }); return; }
    const w = byId(id), it = { id, w: w.w }; S.layout.push(it); save();
    if (!grid.querySelector('.w')) grid.innerHTML = '';
    const c = cardFor(it); grid.appendChild(c); paint(c); c.scrollIntoView({ behavior: 'smooth', block: 'center' }); paintCust();
  }

  // ----- customize drawer -----
  let tab = 'lay';
  function paintCust() {
    if ($('cust').hidden) return; const body = $('custbody'); $('libtools').hidden = tab !== 'lib';
    document.querySelectorAll('.cust .tabs button').forEach(b => b.classList.toggle('on', b.dataset.tab === tab));
    $('nlay').textContent = S.layout.length; $('nlib').textContent = W.length;
    if (tab === 'lay') {
      body.innerHTML = '<div class="tc" style="margin:4px 0 6px"><button class="btn" data-auto>⇲ Auto-arrange</button><button class="btn" data-resetdef>↺ Reset to default</button></div><p class="note">Drag to reorder: the dashboard behind updates as you go. Set each widget’s width with ¼ / ½ / ¾ / 1.</p>' + S.layout.map((it, i) => { const w = byId(it.id);
        return `<div class="lay" draggable="true" data-id="${it.id}"><span style="color:var(--dim)">⋮⋮ ${i + 1}</span><div class="nm">${esc(w.t)}<small>${esc(w.g)}</small></div><span class="wd">${[1, 2, 3, 4].map(n => `<button data-w="${n}" class="${it.w === n ? 'on' : ''}">${['¼', '½', '¾', '1'][n - 1]}</button>`).join('')}</span><button class="x" data-rm="${it.id}" aria-label="Remove">✕</button></div>`; }).join('') +
        '<button class="btn" data-tab-go="lib" style="width:100%;margin-top:6px">＋ Add widgets</button>';
    } else {
      const q = $('libq').value.trim().toLowerCase(), on = new Set(S.layout.map(x => x.id));
      const groups = [...new Set(W.map(w => w.g))];
      body.innerHTML = groups.map(g => { const ws = W.filter(w => w.g === g && (!q || (w.t + ' ' + w.g + ' ' + w.kw).toLowerCase().includes(q)));
        if (!ws.length) return ''; const n = ws.filter(w => on.has(w.id)).length;
        return `<div class="grp"><h4><span>${esc(g.toUpperCase())} ${n}/${ws.length}</span><button data-grp="${esc(g)}">${n === ws.length ? 'None' : 'All'}</button></h4>${ws.map(w => `<label class="lib"><input type="checkbox" data-lib="${w.id}"${on.has(w.id) ? ' checked' : ''}>${esc(w.t)}</label>`).join('')}</div>`; }).join('') || '<p class="note">No widget matches.</p>';
    }
  }
  function openCust(t) { tab = t || tab; $('cust').hidden = false; $('scrim').hidden = false; paintCust(); }
  function closeCust() { $('cust').hidden = true; $('scrim').hidden = true; }
  $('outerchk').checked = SHOW_OUTER;
  // Theme: every colour is a CSS variable (pro.html), so switching needs no redraw. Saved in this browser.
  const BG = { midnight: '#0a0a0a', slate: '#0e131a', amber: '#120d08', light: '#fbf7ef', paper: '#ffffff' };
  const setTheme = t => { if (!BG[t]) t = 'midnight'; document.documentElement.setAttribute('data-theme', t); $('theme').value = t;
    document.querySelector('meta[name="theme-color"]').content = BG[t]; try { localStorage.setItem('sj-pro-theme', t); } catch (e) {} };
  setTheme(document.documentElement.getAttribute('data-theme') || 'midnight');
  $('theme').onchange = e => setTheme(e.target.value);
  $('outerchk').onchange = e => { SHOW_OUTER = e.target.checked; try { localStorage.setItem('sj-outer', SHOW_OUTER ? '1' : '0'); } catch (_) {} renderAll(); };
  $('custbtn').onclick = () => openCust(); $('custx').onclick = closeCust; $('scrim').onclick = closeCust;
  document.querySelector('.cust .tabs').onclick = e => { const b = e.target.closest('[data-tab]'); if (b) { tab = b.dataset.tab; paintCust(); } };
  $('libq').oninput = paintCust;
  $('custbody').addEventListener('click', e => {
    if (e.target.closest('[data-auto]')) { autoArrange(); return; }
    if (e.target.closest('[data-resetdef]')) { resetDefault(); return; }
    const go = e.target.closest('[data-tab-go]'); if (go) { tab = go.dataset.tabGo; paintCust(); return; }
    const wb = e.target.closest('[data-w]'), row = e.target.closest('.lay');
    if (wb && row) { const it = S.layout.find(x => x.id === row.dataset.id); it.w = +wb.dataset.w; save(); const c = grid.querySelector(`.w[data-id="${it.id}"]`); if (c) { c.dataset.w = it.w; c.querySelector('.wh small').textContent = ['¼', '½', '¾', '1'][it.w - 1]; paint(c); } paintCust(); return; }
    const rm = e.target.closest('[data-rm]'); if (rm) { S.layout = S.layout.filter(x => x.id !== rm.dataset.rm); save(); const c = grid.querySelector(`.w[data-id="${rm.dataset.rm}"]`); if (c) c.remove(); paintCust(); return; }
    const gb = e.target.closest('[data-grp]'); if (gb) { const ws = W.filter(w => w.g === gb.dataset.grp), allOn = ws.every(w => S.layout.some(x => x.id === w.id));
      if (allOn) { S.layout = S.layout.filter(x => !ws.some(w => w.id === x.id)); save(); renderAll(); } else ws.forEach(w => addWidget(w.id)); paintCust(); }
  });
  $('custbody').addEventListener('change', e => { const id = e.target.dataset && e.target.dataset.lib; if (!id) return;
    if (e.target.checked) addWidget(id); else { S.layout = S.layout.filter(x => x.id !== id); save(); const c = grid.querySelector(`.w[data-id="${id}"]`); if (c) c.remove(); paintCust(); } });
  let ldrag = null;
  $('custbody').addEventListener('dragstart', e => { const r = e.target.closest('.lay'); if (r) { ldrag = r.dataset.id; r.classList.add('drag'); } });
  $('custbody').addEventListener('dragover', e => { const r = e.target.closest('.lay'); if (r && ldrag) { e.preventDefault(); r.classList.add('over'); } });
  $('custbody').addEventListener('dragleave', e => { const r = e.target.closest('.lay'); if (r) r.classList.remove('over'); });
  $('custbody').addEventListener('drop', e => { const r = e.target.closest('.lay'); if (r && ldrag) { e.preventDefault(); move(ldrag, r.dataset.id); ldrag = null; } });
  $('custbody').addEventListener('dragend', () => { ldrag = null; paintCust(); });
  // Auto-arrange: keep each module group together (library order), then pack the widgets into full rows of 4 columns
  // (first fit: each row takes the next widgets that still fit, so wide and narrow widgets share rows without gaps).
  function autoArrange() {
    const gi = id => [...new Set(W.map(w => w.g))].indexOf(byId(id).g), li = id => W.findIndex(w => w.id === id);
    const left = [...S.layout].sort((a, b) => gi(a.id) - gi(b.id) || li(a.id) - li(b.id)), rows = [];
    while (left.length) { let room = 4; const row = [];
      for (let i = 0; i < left.length && room > 0;) { if (left[i].w <= room) { room -= left[i].w; row.push(left.splice(i, 1)[0]); } else i++; }
      if (!row.length) row.push(left.shift());
      rows.push(row); }
    // Even out each row: spare columns go to the narrowest widgets first, then the row is laid out symmetrically
    // (one wide widget between two narrow ones), so every row is full and balanced.
    rows.forEach(row => { let room = 4 - row.reduce((a, x) => a + x.w, 0);
      while (room > 0) { const n = [...row].sort((a, b) => a.w - b.w)[row.length === 3 && row.every(x => x.w === 1) ? 0 : 0];
        const target = row.length === 3 && row.every(x => x.w === 1) ? row[1] : n; target.w += 1; room--; }
      if (row.length === 3) { const wide = row.reduce((m, x, i) => x.w > row[m].w ? i : m, 0); if (wide !== 1) row.splice(1, 0, row.splice(wide, 1)[0]); } });
    S.layout = rows.flat(); save(); renderAll(); paintCust(); toast('Arranged: related widgets together, rows full and balanced');
  }
  function resetDefault() { if (!confirm('Reset the dashboard to the default layout? Your current arrangement will be replaced.')) return;
    S.layout = fromPreset('parashari'); save(); renderAll(); paintCust(); toast('Back to the default layout'); }
  function toast(t) { const d = document.createElement('div'); d.className = 'toast'; d.textContent = t; document.body.appendChild(d); setTimeout(() => d.remove(), 2200); }
  $('autoarr').onclick = autoArrange; $('resetdef').onclick = resetDefault;
  $('showall').onclick = () => { S.layout = fromPreset('all'); save(); renderAll(); paintCust(); };
  $('hideall').onclick = () => { S.layout = []; save(); renderAll(); paintCust(); };
  $('reset').onclick = resetDefault;

  // presets
  $('preset').innerHTML = '<option value="">Preset…</option>' + Object.entries(PN).map(([k, n]) => `<option value="${k}">${n}</option>`).join('');
  $('preset').onchange = e => { if (!e.target.value) return; S.layout = fromPreset(e.target.value); save(); renderAll(); paintCust(); e.target.value = ''; };

  // ----- command palette (Ctrl K / ⌘K) -----
  let pi = 0;
  function palList() { const q = $('palq').value.trim().toLowerCase();
    const ws = W.filter(w => !q || (w.t + ' ' + w.g + ' ' + w.kw).toLowerCase().includes(q)).slice(0, 40); pi = Math.min(pi, Math.max(ws.length - 1, 0));
    $('pallist').innerHTML = ws.map((w, i) => `<li data-id="${w.id}" class="${i === pi ? 'on' : ''}"><span>${esc(w.t)}</span><small>${esc(w.g)}${S.layout.some(x => x.id === w.id) ? ' · on board' : ''}</small></li>`).join('') || '<li>No widget matches</li>'; }
  function openPal() { $('pal').hidden = false; $('palscrim').hidden = false; $('palq').value = ''; pi = 0; palList(); $('palq').focus(); }
  function closePal() { $('pal').hidden = true; $('palscrim').hidden = true; }
  $('palbtn').onclick = openPal; $('palscrim').onclick = closePal; $('palq').oninput = () => { pi = 0; palList(); };
  $('pallist').onclick = e => { const li = e.target.closest('li[data-id]'); if (li) { addWidget(li.dataset.id); closePal(); } };
  $('palq').onkeydown = e => { const lis = [...$('pallist').querySelectorAll('li[data-id]')];
    if (e.key === 'ArrowDown') { pi = Math.min(pi + 1, lis.length - 1); palList(); e.preventDefault(); }
    else if (e.key === 'ArrowUp') { pi = Math.max(pi - 1, 0); palList(); e.preventDefault(); }
    else if (e.key === 'Enter' && lis[pi]) { addWidget(lis[pi].dataset.id); closePal(); }
    else if (e.key === 'Escape') closePal(); };
  addEventListener('keydown', e => { if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 'k') { e.preventDefault(); $('pal').hidden ? openPal() : closePal(); }
    if (e.key === 'Escape') { closePal(); closeCust(); } });

  // ----- start -----
  $('csel').onclick = () => { S.sel = null; highlight(); };
  $('client').onchange = e => openChart(+e.target.value);
  (async () => {
    S.layout = await loadLayout(); renderAll();
    let list = [];
    try { list = await api('/profiles'); } catch (e) { $('grid').innerHTML = `<p class="note">Couldn’t load your charts: ${esc(e.message)}</p>`; return; }
    if (!list.length) { $('grid').innerHTML = '<p class="note">No saved charts yet. <a href="/#new">Make a chart in the app</a>, then come back.</p>'; return; }
    $('client').innerHTML = list.map(p => `<option value="${p.id}">${esc(p.name)}${p.request && p.request.dob ? ' · ' + esc(p.request.dob) : ''}</option>`).join('');
    let want = null; try { want = +localStorage.getItem('sj-pro-chart'); } catch (e) {}
    const id = list.some(p => p.id === want) ? want : list[0].id; $('client').value = id; openChart(id);
  })();
})();
