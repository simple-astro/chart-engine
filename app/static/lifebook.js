// The Life Book (app/lifebook.py) on My Charts: a card with the book's status; six short questions before it is
// written; then "being reviewed by your astrologer"; once approved, a reader with the contents first and one chapter
// per page (Prev / Next, like the house lords).
(function () {
  const esc = s => String(s ?? '').replace(/[&<>"]/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));
  const FOCUS = [['career', 'Career'], ['money', 'Money'], ['marriage', 'Marriage & relationships'], ['children', 'Children'],
    ['home', 'Home & property'], ['abroad', 'Living abroad'], ['studies', 'Studies'], ['health', 'Health habits'], ['spiritual', 'Spiritual path']];
  const STAGE = [['work', 'Work', [['student', 'Student'], ['job', 'Job'], ['business', 'Business'], ['home', 'Homemaker'], ['retired', 'Retired']]],
    ['relationship', 'Relationship', [['single', 'Single'], ['relationship', 'In a relationship'], ['married', 'Married']]],
    ['children', 'Children', [['none', 'None'], ['planning', 'Planning'], ['yes', 'Yes']]]];
  const RATE = [['career', 'Career'], ['money', 'Money'], ['relationships', 'Relationships'], ['health', 'Health'], ['peace', 'Peace of mind']];
  const STEPS = ['Focus', 'Where you are', 'Your questions', 'Big life dates', 'How it feels now', 'Last details'];
  const TRACK = [['writing', 'Writing your book'], ['review', 'Your astrologer reviews it'], ['ready', 'Ready to read']];
  let S = { pid: null, name: '', data: null, kinds: [], step: 0, a: null, ch: null, poll: null };

  const api = async (path, opt) => {
    const r = await fetch(path, opt), d = await r.json().catch(() => ({}));
    if (!r.ok) throw new Error(window.apiErr ? window.apiErr(d.detail) || r.statusText : r.statusText);
    return d;
  };
  const fresh = () => ({ focus: [], stage: {}, questions: ['', '', ''], events: [{ kind: '', year: '', month: '' }],
    ratings: {}, prefs: { tob: 'exact', remedies: 'habits' }, consent: false });

  window.renderLifeBook = async function (card, pid, name) {
    S.pid = pid; S.name = (name || '').split(' ')[0];
    card.hidden = false; card.innerHTML = '<p class="hint">Checking your Life Book…</p>';
    try { S.data = await api('/profiles/' + pid + '/lifebook'); } catch (e) { card.hidden = true; return; }
    paintCard(card);
  };

  function paintCard(card) {
    card = card || document.getElementById('lbcard');
    const d = S.data || {}, st = d.status;
    clearTimeout(S.poll);
    let body;
    if (!st) body = '<p>A personal book from your chart: your strengths, your house lords, the best windows for what matters to you, '
      + 'the year ahead and answers to your own questions, reviewed by your astrologer.</p>'
      + '<button type="button" class="btn" data-lb="start">Answer 6 quick questions ›</button><small class="hint">About 3 minutes · free while in testing</small>';
    else if (st === 'ready') body = '<p>Your book is ready. Reviewed by your astrologer.</p>'
      + '<div class="lb-acts"><button type="button" class="btn" data-lb="read">Read your Life Book ›</button>'
      + '<a class="btn ghost" href="/profiles/' + S.pid + '/lifebook.pdf" download data-lb="pdf">⬇ Download PDF</a></div>'
      + '<button type="button" class="linkbtn" data-lb="start">Make a new one</button>';
    else if (st === 'failed') body = '<p>Something went wrong while writing your book. Your answers are saved.</p>'
      + '<button type="button" class="btn" data-lb="start">Try again</button>';
    else {
      const at = TRACK.findIndex(t => t[0] === st);
      body = '<ol class="lb-track">' + TRACK.map((t, i) => '<li class="' + (i < at ? 'done' : i === at ? 'now' : '') + '">' + t[1] + '</li>').join('') + '</ol>'
        + '<p class="hint">' + (st === 'writing' ? 'This takes a minute or two.' : 'You will see it here as soon as your astrologer approves it.') + '</p>';
      if (st === 'writing') S.poll = setTimeout(async () => { try { S.data = await api('/profiles/' + S.pid + '/lifebook'); paintCard(); } catch (e) {} }, 15000);
    }
    card.innerHTML = '<div class="lb-head"><span class="lb-ico" aria-hidden="true">❖</span><div><h3>Your Life Book</h3>'
      + (st ? '<small>' + esc(d.status_text) + '</small>' : '') + '</div></div>' + body;
  }

  // ----- the questions: one step per screen -----
  async function openForm() {
    S.a = fresh(); S.step = 0;
    if (!S.kinds.length) { try { S.kinds = (await api('/profiles/' + S.pid + '/events')).kinds; } catch (e) {} }
    sheet().hidden = false; document.body.classList.add('lb-open'); paintForm();
  }
  function sheet() {
    let el = document.getElementById('lbsheet');
    if (!el) {
      el = document.createElement('div'); el.id = 'lbsheet'; el.className = 'lb-sheet'; el.setAttribute('role', 'dialog');
      el.setAttribute('aria-modal', 'true'); el.setAttribute('aria-label', 'Your Life Book'); el.hidden = true;
      document.body.appendChild(el);
      el.addEventListener('click', onSheet); el.addEventListener('input', onInput); el.addEventListener('change', onInput);
      document.addEventListener('keydown', e => { if (e.key === 'Escape' && !el.hidden) close(); });
    }
    return el;
  }
  function close() { const el = sheet(); el.hidden = true; el.innerHTML = ''; document.body.classList.remove('lb-open'); }

  function stepBody() {
    const a = S.a;
    if (S.step === 0) return '<h2>What should your book help with?</h2><p class="hint">Pick up to 3.</p><div class="lb-chips">'
      + FOCUS.map(([k, l]) => '<button type="button" data-focus="' + k + '" aria-pressed="' + a.focus.includes(k) + '">' + l + '</button>').join('') + '</div>';
    if (S.step === 1) return '<h2>Where are you in life?</h2><p class="hint">So the book never tells you something that no longer fits.</p>'
      + STAGE.map(([k, l, opts]) => '<fieldset class="lb-seg"><legend>' + l + '</legend>' + opts.map(([v, t]) =>
        '<button type="button" data-stage="' + k + '" data-v="' + v + '" aria-pressed="' + (a.stage[k] === v) + '">' + t + '</button>').join('') + '</fieldset>').join('');
    if (S.step === 2) return '<h2>Your questions</h2><p class="hint">Up to 3 questions you most want answered. They are answered from your chart and checked against it.</p>'
      + a.questions.map((q, i) => '<label class="lb-field"><span>Question ' + (i + 1) + '</span><textarea rows="2" maxlength="300" data-q="' + i + '" placeholder="'
        + ['e.g. When is a good time to grow my business?', 'e.g. What should I focus on this year?', ''][i] + '">' + esc(q) + '</textarea></label>').join('');
    if (S.step === 3) return '<h2>Big dates in your life</h2><p class="hint">Up to 5 past events with the year (and month, if you know it). They show how well your chart fits your life, and check your birth time.</p>'
      + a.events.map((e, i) => '<div class="lb-ev"><select data-ev="' + i + '" data-k="kind" aria-label="What happened"><option value="">What happened…</option>'
        + S.kinds.map(k => '<option value="' + k.key + '"' + (e.kind === k.key ? ' selected' : '') + '>' + esc(k.label) + '</option>').join('') + '</select>'
        + '<input data-ev="' + i + '" data-k="year" inputmode="numeric" maxlength="4" placeholder="Year" aria-label="Year" value="' + esc(e.year) + '">'
        + '<select data-ev="' + i + '" data-k="month" aria-label="Month"><option value="">Month</option>' + ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
          .map((m, j) => '<option value="' + (j + 1) + '"' + (+e.month === j + 1 ? ' selected' : '') + '>' + m + '</option>').join('') + '</select></div>').join('')
      + (a.events.length < 5 ? '<button type="button" class="linkbtn" data-lb="addev">+ Add another date</button>' : '');
    if (S.step === 4) return '<h2>How does each area feel now?</h2><p class="hint">1 is hard, 5 is great. Your book puts this beside what your chart shows now.</p>'
      + RATE.map(([k, l]) => '<fieldset class="lb-rate"><legend>' + l + '</legend>' + [1, 2, 3, 4, 5].map(n =>
        '<button type="button" data-rate="' + k + '" data-v="' + n + '" aria-pressed="' + (a.ratings[k] === n) + '" aria-label="' + l + ' ' + n + ' of 5">' + n + '</button>').join('') + '</fieldset>').join('');
    return '<h2>Last details</h2>'
      + '<fieldset class="lb-seg"><legend>Your birth time is</legend>' + [['exact', 'Exact (from a certificate)'], ['approx', 'Approximate']].map(([v, t]) =>
        '<button type="button" data-pref="tob" data-v="' + v + '" aria-pressed="' + (a.prefs.tob === v) + '">' + t + '</button>').join('') + '</fieldset>'
      + '<fieldset class="lb-seg"><legend>Remedies in the book</legend>' + [['habits', 'Simple habits'], ['none', 'No remedies']].map(([v, t]) =>
        '<button type="button" data-pref="remedies" data-v="' + v + '" aria-pressed="' + (a.prefs.remedies === v) + '">' + t + '</button>').join('') + '</fieldset>'
      + '<p class="hint">Language: English (Hindi coming later).</p>'
      + '<label class="lb-consent"><input type="checkbox" data-consent' + (a.consent ? ' checked' : '') + '> I agree that my astrologer reviews my book before I see it, and that my answers are kept privately with my chart.</label>'
      + '<p class="lb-err" id="lberr" role="alert"></p>';
  }

  function paintForm() {
    const last = S.step === STEPS.length - 1;
    sheet().innerHTML = '<div class="lb-wrap"><div class="lb-top"><button type="button" class="linkbtn" data-lb="close">✕ Close</button>'
      + '<span>Step ' + (S.step + 1) + ' of ' + STEPS.length + ' · ' + STEPS[S.step] + '</span></div>'
      + '<div class="lb-bar"><i style="width:' + ((S.step + 1) / STEPS.length * 100) + '%"></i></div>'
      + '<div class="lb-body">' + stepBody() + '</div>'
      + '<div class="lb-nav">' + (S.step ? '<button type="button" class="btn ghost" data-lb="back">‹ Back</button>' : '<span></span>')
      + (last ? '<button type="button" class="btn" data-lb="send"' + (S.a.consent ? '' : ' disabled') + '>Write my Life Book</button>'
        : '<button type="button" class="btn" data-lb="next">' + (S.step === 2 || S.step === 3 ? 'Next (or skip) ›' : 'Next ›') + '</button>') + '</div></div>';
    const f = sheet().querySelector('.lb-body h2'); if (f) { f.tabIndex = -1; f.focus(); }
  }

  function onInput(e) {
    const t = e.target, a = S.a; if (!a) return;
    if (t.dataset.q != null) a.questions[+t.dataset.q] = t.value;
    if (t.dataset.ev != null) a.events[+t.dataset.ev][t.dataset.k] = t.value;
    if (t.hasAttribute('data-consent')) { a.consent = t.checked; const b = sheet().querySelector('[data-lb="send"]'); if (b) b.disabled = !t.checked; }
  }

  async function onSheet(e) {
    const b = e.target.closest('button'); if (!b) return;
    const a = S.a, act = b.dataset.lb;
    if (b.dataset.focus) { const k = b.dataset.focus, i = a.focus.indexOf(k); if (i >= 0) a.focus.splice(i, 1); else if (a.focus.length < 3) a.focus.push(k); return paintForm(); }
    if (b.dataset.stage) { a.stage[b.dataset.stage] = b.dataset.v; return paintForm(); }
    if (b.dataset.rate) { a.ratings[b.dataset.rate] = +b.dataset.v; return paintForm(); }
    if (b.dataset.pref) { a.prefs[b.dataset.pref] = b.dataset.v; return paintForm(); }
    if (b.dataset.chapter != null) { S.ch = +b.dataset.chapter; return paintBook(); }
    if (act === 'close') return close();
    if (act === 'addev') { a.events.push({ kind: '', year: '', month: '' }); return paintForm(); }
    if (act === 'back') { S.step--; return paintForm(); }
    if (act === 'next') { S.step++; return paintForm(); }
    if (act === 'toc') { S.ch = null; return paintBook(); }
    if (act === 'send') {
      b.disabled = true;
      const body = { focus: a.focus, stage: a.stage, questions: a.questions.filter(q => q.trim()), ratings: a.ratings, prefs: a.prefs, consent: a.consent,
        events: a.events.filter(x => x.kind && /^\d{4}$/.test(x.year)).map(x => ({ kind: x.kind, year: +x.year, month: x.month ? +x.month : null })) };
      try {
        S.data = await api('/profiles/' + S.pid + '/lifebook', { method: 'POST', headers: { 'content-type': 'application/json' }, body: JSON.stringify(body) });
        if (window.track) window.track('chart/lifebook-start');
        close(); paintCard();
      } catch (err) { const m = document.getElementById('lberr'); if (m) m.textContent = err.message; b.disabled = false; }
    }
  }

  // ----- the reader: contents, then one chapter per page -----
  function block(b) {
    if (b.type === 'p') return '<p>' + esc(b.text) + '</p>';
    if (b.type === 'list') return (b.title ? '<h4>' + esc(b.title) + '</h4>' : '') + (b.items.length ? '<ul>' + b.items.map(x => '<li>' + esc(x) + '</li>').join('') + '</ul>' : '');
    if (b.type === 'rows') return '<dl class="lb-rows">' + b.rows.map(([k, v]) => '<div><dt>' + esc(k) + '</dt><dd>' + esc(v) + '</dd></div>').join('') + '</dl>';
    if (b.type === 'qa') return b.items.map(x => '<div class="lb-qa"><h4>' + esc(x.q) + '</h4>' + esc(x.a).split(/\n+/).map(p => '<p>' + p + '</p>').join('') + '</div>').join('');
    if (b.type === 'cards') return '<div class="lb-cards">' + b.items.map(c => '<article><div class="lb-ct"><b>' + esc(c.title) + '</b>'
      + (c.tag ? '<span class="hl-tag ' + ({ Strong: 'strong', Mixed: 'mixed', 'Needs care': 'care' }[c.tag] || '') + '">' + esc(c.tag) + '</span>' : '') + '</div>'
      + '<p>' + esc(c.text) + '</p>' + (c.sub ? '<small>' + esc(c.sub) + '</small>' : '') + '</article>').join('') + '</div>';
    return '';
  }
  function paintBook() {
    const book = S.data && S.data.book; if (!book) return;
    const chs = book.chapters, el = sheet();
    let body;
    if (S.ch == null) body = '<div class="lb-cover"><small>LIFE BOOK</small><h2>' + esc(book.title) + '</h2><p class="hint">' + esc(book.lagna) + ' lagna · made '
      + new Date(book.made).toLocaleDateString(undefined, { day: 'numeric', month: 'long', year: 'numeric' }) + ' · reviewed by your astrologer</p></div>'
      + '<button type="button" class="btn lb-start" data-chapter="0">Start reading ›</button>'
      + '<a class="btn ghost lb-start lb-dl" href="/profiles/' + S.pid + '/lifebook.pdf" download>⬇ Download as PDF</a>'
      + '<ol class="lb-toc">' + chs.map((c, i) => '<li><button type="button" data-chapter="' + i + '"><span>' + (i + 1) + '</span>' + esc(c.title) + '</button></li>').join('') + '</ol>';
    else {
      const c = chs[S.ch];
      body = '<div class="lb-page"><small>Chapter ' + (S.ch + 1) + ' of ' + chs.length + '</small><h2>' + esc(c.title) + '</h2>'
        + (c.intro ? '<p class="lb-intro">' + esc(c.intro) + '</p>' : '') + c.blocks.map(block).join('') + '</div>'
        + '<div class="lb-nav">' + (S.ch ? '<button type="button" class="btn ghost" data-chapter="' + (S.ch - 1) + '">‹ ' + esc(chs[S.ch - 1].title) + '</button>' : '<button type="button" class="btn ghost" data-lb="toc">‹ Contents</button>')
        + (S.ch < chs.length - 1 ? '<button type="button" class="btn" data-chapter="' + (S.ch + 1) + '">' + esc(chs[S.ch + 1].title) + ' ›</button>' : '<button type="button" class="btn" data-lb="toc">Back to contents</button>') + '</div>';
    }
    el.innerHTML = '<div class="lb-wrap"><div class="lb-top"><button type="button" class="linkbtn" data-lb="close">✕ Close</button>'
      + (S.ch != null ? '<span><button type="button" class="linkbtn" data-lb="toc">Contents</button> · <a class="linkbtn" href="/profiles/' + S.pid + '/lifebook.pdf" download>PDF</a></span>' : '<span></span>')
      + '</div><div class="lb-body">' + body + '</div></div>';
    el.scrollTop = 0; const h = el.querySelector('h2'); if (h) { h.tabIndex = -1; h.focus(); }
  }

  document.addEventListener('click', e => {
    const b = e.target.closest('#lbcard [data-lb]'); if (!b) return;
    if (b.dataset.lb === 'start') openForm();
    if (b.dataset.lb === 'read') { S.ch = null; sheet().hidden = false; document.body.classList.add('lb-open'); paintBook(); if (window.track) window.track('chart/lifebook-read'); }
  });
})();
