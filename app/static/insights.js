// Easy-language readings built from the /chart response: house-by-house interpretation,
// daśā prediction, and lucky factors with life-area summaries. Uses whole-sign houses
// counted from the lagna so the text matches the drawn chart. Traditional guidance only.
(function () {
  const SIGNS = ['Aries', 'Taurus', 'Gemini', 'Cancer', 'Leo', 'Virgo', 'Libra', 'Scorpio', 'Sagittarius',
    'Capricorn', 'Aquarius', 'Pisces'];
  const LORD = ['Mars', 'Venus', 'Mercury', 'Moon', 'Sun', 'Mercury', 'Venus', 'Mars', 'Jupiter', 'Saturn',
    'Saturn', 'Jupiter'];
  const EXALT = { Sun: 0, Moon: 1, Mars: 9, Mercury: 5, Jupiter: 3, Venus: 11, Saturn: 6, Rahu: 1, Ketu: 7 };
  const FRIENDS = {
    Sun: ['Moon', 'Mars', 'Jupiter'], Moon: ['Sun', 'Mercury'], Mars: ['Sun', 'Moon', 'Jupiter'],
    Mercury: ['Sun', 'Venus'], Jupiter: ['Sun', 'Moon', 'Mars'], Venus: ['Mercury', 'Saturn'],
    Saturn: ['Mercury', 'Venus'], Rahu: ['Mercury', 'Venus', 'Saturn'], Ketu: ['Mars', 'Jupiter'],
  };
  const ENEMIES = {
    Sun: ['Venus', 'Saturn'], Moon: [], Mars: ['Mercury'], Mercury: ['Moon'], Jupiter: ['Mercury', 'Venus'],
    Venus: ['Sun', 'Moon'], Saturn: ['Sun', 'Moon', 'Mars'], Rahu: ['Sun', 'Moon', 'Mars'], Ketu: ['Moon', 'Venus'],
  };
  const BENEFIC = ['Jupiter', 'Venus', 'Mercury', 'Moon'];
  const KENDRA = [1, 4, 7, 10], TRIKONA = [1, 5, 9], DUSTHANA = [6, 8, 12], UPACHAYA = [3, 6, 10, 11];

  const HOUSE = {
    1: { title: 'Self, body & personality', short: 'self and health',
      covers: 'your nature, looks, health, confidence and the way you approach life',
      good: 'You come across with confidence, recover well from setbacks and are able to steer your own life.',
      care: 'Look after your energy and self-belief; steady routines help you feel strong and in charge.' },
    2: { title: 'Wealth, family & speech', short: 'money and family',
      covers: 'savings, family, food habits, speech and the values you hold',
      good: 'Money tends to build steadily, family support is good and your words carry weight.',
      care: 'Savings need discipline; speak gently at home and avoid lending without care.' },
    3: { title: 'Courage, siblings & effort', short: 'courage and siblings',
      covers: 'courage, brothers and sisters, short trips, hobbies, writing and your own effort',
      good: 'You have courage and initiative; siblings and your own hard work open doors.',
      care: 'Keep up your effort and patience with siblings; avoid giving up too early.' },
    4: { title: 'Mother, home & happiness', short: 'home and mother',
      covers: 'mother, home, property, vehicles, schooling and peace of mind',
      good: 'Home life, property and a peaceful mind are well supported; mother is a source of strength.',
      care: 'Peace of mind needs nurturing; take care with property papers and mother’s wellbeing.' },
    5: { title: 'Children, intelligence & romance', short: 'children and studies',
      covers: 'children, intelligence, studies, creativity, romance and past-life merit',
      good: 'Sharp intelligence and creativity; children and studies bring joy and pride.',
      care: 'Studies and matters of children may need more patience; avoid speculation and gambling.' },
    6: { title: 'Health, enemies & daily work', short: 'work and health',
      covers: 'daily work, service, competition, loans, illnesses and how you defeat obstacles',
      good: 'You win over rivals, handle competition well and do well in service or a job.',
      care: 'Watch your health habits and avoid debts or disputes; routine and diet matter.' },
    7: { title: 'Marriage & partnerships', short: 'marriage and partners',
      covers: 'spouse, marriage, business partners, contracts and public dealings',
      good: 'Partnerships, marriage and dealing with the public tend to be supportive.',
      care: 'Relationships need understanding and patience; choose partners and contracts carefully.' },
    8: { title: 'Longevity, change & secrets', short: 'sudden changes',
      covers: 'long life, sudden events, in-laws, inheritance, research and hidden knowledge',
      good: 'Good staying power, interest in research or the occult, and possible gains through inheritance or a spouse.',
      care: 'Expect some sudden ups and downs; keep insurance, savings and health checks in order.' },
    9: { title: 'Luck, father & dharma', short: 'luck and father',
      covers: 'fortune, father, teachers, faith, higher studies and long journeys',
      good: 'Luck supports you; teachers, father figures and faith guide you well.',
      care: 'Luck comes through effort; respect elders and teachers and keep your faith steady.' },
    10: { title: 'Career, status & karma', short: 'career',
      covers: 'profession, status, reputation, authority and your actions in the world',
      good: 'A strong career house: recognition, responsibility and steady professional growth.',
      care: 'Career needs persistence; build skills and relationships with seniors for a steady rise.' },
    11: { title: 'Income, gains & friends', short: 'income and gains',
      covers: 'income, profits, elder siblings, friends, networks and fulfilment of wishes',
      good: 'Income and gains flow well; friends and networks help your wishes come true.',
      care: 'Gains come slower than hoped; choose friends wisely and keep realistic goals.' },
    12: { title: 'Expenses, foreign lands & moksha', short: 'expenses and foreign lands',
      covers: 'spending, losses, foreign travel or settlement, sleep, hospitals, charity and spirituality',
      good: 'Good for foreign links, peaceful sleep, charity and spiritual growth; spending goes to good causes.',
      care: 'Keep an eye on expenses and sleep; meditation and giving help balance this house.' },
  };

  const LAGNA = {
    Aries: 'You are bold, energetic and quick to act. You like to lead, start new things and dislike waiting; learning patience is your growth point.',
    Taurus: 'You are calm, practical and loyal. You value comfort, security and good things in life, and you build slowly but surely; you can be stubborn.',
    Gemini: 'You are curious, talkative and quick-witted. You enjoy learning, variety and people; focusing on one thing at a time helps you most.',
    Cancer: 'You are caring, sensitive and protective. Family and home matter deeply to you; your moods can change like the Moon, so emotional balance is key.',
    Leo: 'You are confident, generous and proud. You like to shine and lead, and people look up to you; watch out for ego clashes.',
    Virgo: 'You are careful, analytical and helpful. You notice details and like to improve things; avoid over-worrying and being too self-critical.',
    Libra: 'You are friendly, fair and charming. You seek balance, beauty and good relationships; decisiveness is your growth point.',
    Scorpio: 'You are intense, private and determined. You feel deeply, research thoroughly and transform through challenges; learn to let go of grudges.',
    Sagittarius: 'You are optimistic, honest and freedom-loving. You love learning, travel and big ideas, and have a natural sense of right and wrong; avoid over-promising.',
    Capricorn: 'You are disciplined, patient and ambitious. You take responsibility early and rise step by step; remember to rest and enjoy the journey.',
    Aquarius: 'You are independent, original and humane. You think differently, value friends and causes, and can seem detached; staying connected helps.',
    Pisces: 'You are kind, imaginative and intuitive. You feel others’ pain and are drawn to art or spirituality; clear boundaries protect your energy.',
  };
  const STYLE = {
    Aries: 'in a bold, direct way', Taurus: 'in a steady, practical way', Gemini: 'through ideas, talk and variety',
    Cancer: 'with care and emotion', Leo: 'with pride and a wish to shine', Virgo: 'with care for detail',
    Libra: 'through balance and cooperation', Scorpio: 'with intensity and depth', Sagittarius: 'with optimism and principle',
    Capricorn: 'with discipline and patience', Aquarius: 'in an independent, unusual way', Pisces: 'with sensitivity and intuition',
  };
  const PLANET = {
    Sun: { gift: 'confidence, authority and recognition', risk: 'ego or friction with authority' },
    Moon: { gift: 'emotional warmth, popularity and care', risk: 'mood swings and restlessness' },
    Mars: { gift: 'energy, courage and drive', risk: 'anger, haste or disputes' },
    Mercury: { gift: 'intelligence, communication and business sense', risk: 'nervousness or overthinking' },
    Jupiter: { gift: 'growth, wisdom and protection', risk: 'over-confidence or over-spending' },
    Venus: { gift: 'love, comfort, beauty and harmony', risk: 'indulgence or luxury spending' },
    Saturn: { gift: 'discipline, endurance and lasting results', risk: 'delays, pressure or loneliness' },
    Rahu: { gift: 'ambition and unusual opportunities', risk: 'confusion, obsession or shortcuts' },
    Ketu: { gift: 'insight, detachment and spiritual depth', risk: 'disinterest or sudden breaks' },
  };
  // Well-known combinations worth calling out in plain words.
  const SPECIAL = {
    'Sun-10': 'Sun in the 10th is a classic sign of leadership and a respected position.',
    'Jupiter-1': 'Jupiter in the 1st gives wisdom, good values and natural protection.',
    'Jupiter-5': 'Jupiter in the 5th is very good for intelligence, children and good advice.',
    'Jupiter-9': 'Jupiter in the 9th is a strong blessing of luck, faith and good teachers.',
    'Moon-4': 'Moon in the 4th gives love for home and a strong bond with mother.',
    'Mars-3': 'Mars in the 3rd gives great courage and the drive to succeed by your own effort.',
    'Mars-10': 'Mars in the 10th gives drive and success in technical, leadership or competitive careers.',
    'Mars-7': 'Mars in the 7th asks for patience and cooperation in marriage (a Manglik placement).',
    'Saturn-7': 'Saturn in the 7th often brings a mature partner or marriage after some delay, and it lasts.',
    'Saturn-11': 'Saturn in the 11th gives steady, growing income over time.',
    'Saturn-3': 'Saturn in the 3rd gives persistence and the stamina to finish what you start.',
    'Venus-7': 'Venus in the 7th supports an attractive, loving partner and pleasant relationships.',
    'Venus-4': 'Venus in the 4th brings comforts, a nice home and vehicles.',
    'Mercury-10': 'Mercury in the 10th suits business, communication, writing or analytical careers.',
    'Rahu-10': 'Rahu in the 10th brings big ambitions and sudden rises, often in modern or foreign fields.',
    'Rahu-6': 'Rahu in the 6th helps you defeat rivals and overcome obstacles.',
    'Rahu-11': 'Rahu in the 11th can bring large or unexpected gains.',
    'Ketu-12': 'Ketu in the 12th is a classic sign of spiritual inclination and inner peace.',
  };
  const MD_THEME = {
    Sun: 'A time to step forward: authority, recognition, government matters and your father come into focus. Confidence rises, but ego clashes need watching.',
    Moon: 'A time of feelings, home and public life: mother, travel, change of residence and emotional growth. The mind can swing, so routines help.',
    Mars: 'A time of energy and action: property, siblings, competition, technical work and bold moves. Avoid anger, haste and accidents.',
    Mercury: 'A time of learning and trade: studies, business, writing, communication, friends and skills. Avoid scattering your energy and nervous strain.',
    Jupiter: 'A time of growth and wisdom: knowledge, children, teachers, finances, marriage and faith expand. Avoid over-promising and over-spending.',
    Venus: 'A time of comforts and relationships: love, marriage, vehicles, home, arts and money matters. Enjoy it, but avoid indulgence.',
    Saturn: 'A time of hard work and slow, solid rise: responsibility, career structure and long-term results. Expect delays early; patience pays later.',
    Rahu: 'A time of big ambitions and sudden changes: foreign links, technology, unusual chances and fast rises. Avoid shortcuts and confusion.',
    Ketu: 'A time of letting go and looking within: research, spirituality and detachment. Sudden breaks can open better paths.',
  };
  const REMEDY = {
    Sun: 'Offer water to the rising Sun, respect your father and seniors.',
    Moon: 'Respect your mother, keep a calm routine, donate milk or rice on Mondays.',
    Mars: 'Practise sport or physical work, control anger, visit Hanuman ji on Tuesdays.',
    Mercury: 'Read, learn and keep promises, feed green fodder to cows on Wednesdays.',
    Jupiter: 'Respect teachers and elders, donate yellow items or turmeric on Thursdays.',
    Venus: 'Respect women, keep yourself and home clean and beautiful, donate white sweets on Fridays.',
    Saturn: 'Be fair to workers and the poor, stay disciplined, donate black sesame or mustard oil on Saturdays.',
    Rahu: 'Avoid shortcuts and intoxicants, and feed birds or dogs on Saturdays.',
    Ketu: 'Meditate, help spiritual causes, feed dogs.',
  };
  const LUCK = {
    Sun: { num: 1, day: 'Sunday', color: 'orange, gold', gem: 'Ruby (Manik)', wear: 'ring finger, in gold, on a Sunday morning' },
    Moon: { num: 2, day: 'Monday', color: 'white, silver', gem: 'Pearl (Moti)', wear: 'little finger, in silver, on a Monday morning' },
    Mars: { num: 9, day: 'Tuesday', color: 'red', gem: 'Red Coral (Moonga)', wear: 'ring finger, in gold or copper, on a Tuesday morning' },
    Mercury: { num: 5, day: 'Wednesday', color: 'green', gem: 'Emerald (Panna)', wear: 'little finger, in gold, on a Wednesday morning' },
    Jupiter: { num: 3, day: 'Thursday', color: 'yellow', gem: 'Yellow Sapphire (Pukhraj)', wear: 'index finger, in gold, on a Thursday morning' },
    Venus: { num: 6, day: 'Friday', color: 'white, pastel pink', gem: 'Diamond or White Sapphire (Opal as a substitute)', wear: 'middle or ring finger, in silver or platinum, on a Friday morning' },
    Saturn: { num: 8, day: 'Saturday', color: 'dark blue, black', gem: 'Blue Sapphire (Neelam)', wear: 'middle finger, in silver or panchdhatu, on a Saturday — only after a trial period' },
    Rahu: { num: 4, day: 'Saturday', color: 'smoky grey', gem: 'Hessonite (Gomed)', wear: 'middle finger, in silver' },
    Ketu: { num: 7, day: 'Tuesday', color: 'grey, multicolour', gem: "Cat's Eye (Lehsunia)", wear: 'little or middle finger, in silver' },
  };
  const BODY = {
    Aries: 'head, eyes and blood pressure', Taurus: 'throat, neck and thyroid', Gemini: 'lungs, shoulders and nerves',
    Cancer: 'chest, stomach and water balance', Leo: 'heart, spine and back', Virgo: 'digestion and intestines',
    Libra: 'kidneys, lower back and skin', Scorpio: 'reproductive and excretory organs', Sagittarius: 'hips, thighs and liver',
    Capricorn: 'knees, bones and joints', Aquarius: 'calves, ankles and circulation', Pisces: 'feet, sleep and immunity',
  };
  const PLANET_BODY = {
    Sun: 'heart, eyes and vitality', Moon: 'sleep, fluids and emotions', Mars: 'blood, injuries and inflammation',
    Mercury: 'nerves and skin', Jupiter: 'liver, weight and sugar levels', Venus: 'kidneys and hormones',
    Saturn: 'joints, teeth and long-standing problems', Rahu: 'allergies, anxiety and hard-to-diagnose issues',
    Ketu: 'sudden infections or minor surgeries',
  };
  const ELEMENT_TIP = {
    fire: 'You run on high energy: avoid burnout, overheating and skipping meals.',
    earth: 'You do best with movement: regular exercise and light digestion keep you well.',
    air: 'Your nerves work hard: good sleep, breathing exercises and less screen time help.',
    water: 'You absorb moods easily: hydration, emotional rest and a calm routine help.',
  };
  const CAREER = {
    Sun: 'government, administration, management, politics, medicine',
    Moon: 'hospitality, nursing, food, public relations, travel, dairy or water-related work',
    Mars: 'engineering, police or defence, sports, surgery, real estate, construction',
    Mercury: 'business, trade, accounts, IT, writing, media, teaching languages, consulting',
    Jupiter: 'teaching, law, finance and banking, advisory roles, religion, counselling',
    Venus: 'arts, fashion, design, beauty, entertainment, luxury goods, hospitality',
    Saturn: 'manufacturing, mining, oil, labour or HR, judiciary, long-term government service',
    Rahu: 'technology, foreign companies, aviation, research, media, politics',
    Ketu: 'research, coding, alternative healing, spirituality, investigation',
  };
  const CAREER_BY_HOUSE = {
    1: 'Your career is closely tied to your own name and personality — self-employment or a visible role suits you.',
    2: 'Career connects with finance, family business, food or speaking — banking, sales or teaching fit well.',
    3: 'Career grows through communication, media, travel or your own initiative and skills.',
    4: 'Career connects with property, vehicles, education or working from home or your homeland.',
    5: 'Career connects with creativity, teaching, advising, entertainment or investments.',
    6: 'Service, a regular job, healthcare, law or competitive fields suit you; steady employment is favoured.',
    7: 'Business, partnerships, trade or client-facing work suit you.',
    8: 'Research, insurance, investigation, mining, occult or behind-the-scenes work suits you.',
    9: 'Career connects with teaching, law, travel, religion or higher education; luck helps your profession.',
    10: 'A strong, self-driven career; you are likely to rise to a position of authority.',
    11: 'Career brings good income and works through networks, large organisations or friends.',
    12: 'Career connects with foreign lands, multinational companies, hospitals, export or spiritual work.',
  };

  const esc = s => String(s).replace(/[&<>]/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;' }[c]));
  const list = a => a.length <= 1 ? a.join('') : a.slice(0, -1).join(', ') + ' and ' + a[a.length - 1];
  const ord = n => n + ({ 1: 'st', 2: 'nd', 3: 'rd' }[n] || 'th');
  const fd = s => new Date(s).toLocaleDateString(undefined, { year: 'numeric', month: 'short' });
  const badge = v => `<span class="badge ${v.cls}">${v.label}</span>`;
  const V = {
    strong: { cls: 'good', label: 'Strong' }, good: { cls: 'good', label: 'Good' },
    mixed: { cls: '', label: 'Mixed' }, care: { cls: 'warn', label: 'Needs care' },
  };

  function ctx(c) {
    const L = c.lagna.sign_index, g = c.grahas;
    const house = p => (g[p].sign_index - L + 12) % 12 + 1;
    const signOf = h => (L + h - 1) % 12;
    const lordOf = h => LORD[signOf(h)];
    const owns = p => [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12].filter(h => lordOf(h) === p);
    const inHouse = h => Object.keys(g).filter(p => house(p) === h);
    const dignity = p => {
      const s = g[p].sign_index;
      if (EXALT[p] === s) return 'exalted';
      if ((EXALT[p] + 6) % 12 === s) return 'debilitated';
      if (LORD[s] === p) return 'own';
      if ((FRIENDS[p] || []).includes(LORD[s])) return 'friendly';
      if ((ENEMIES[p] || []).includes(LORD[s])) return 'enemy';
      return 'neutral';
    };
    return { L, g, house, signOf, lordOf, owns, inHouse, dignity };
  }
  window.planetDignity = (c, p) => ctx(c).dignity(p);

  function houseScore(x, h) {
    const lord = x.lordOf(h), at = x.house(lord);
    let s = 0;
    if (at === h) s += 3;
    else if (KENDRA.includes(at) || TRIKONA.includes(at)) s += 2;
    else if (at === 2 || at === 11) s += 1;
    else if (DUSTHANA.includes(at)) s += DUSTHANA.includes(h) ? 1 : -2;
    const d = x.dignity(lord);
    if (d === 'exalted' || d === 'own') s += 1;
    if (d === 'debilitated') s -= 1;
    for (const p of x.inHouse(h)) {
      if (BENEFIC.includes(p)) s += h === 6 || h === 8 ? 0 : 1;
      else s += UPACHAYA.includes(h) ? 1 : -1;
    }
    return s >= 3 ? 'strong' : s >= 1 ? 'good' : s >= -1 ? 'mixed' : 'care';
  }

  function planetLine(x, p, h) {
    const P = PLANET[p], topic = HOUSE[h].short, d = x.dignity(p);
    let t;
    if (BENEFIC.includes(p)) {
      t = DUSTHANA.includes(h)
        ? `<b>${p}</b> here softens the difficulties of ${topic}; its gifts of ${P.gift} work more quietly.`
        : `<b>${p}</b> here brings ${P.gift} to ${topic}.`;
    } else {
      t = UPACHAYA.includes(h)
        ? `<b>${p}</b> here is a real strength — it gives ${P.gift} to succeed in ${topic}, improving with age.`
        : `<b>${p}</b> here adds ${P.gift}, but can also bring ${P.risk} in matters of ${topic}; patience turns it around.`;
    }
    if (d === 'exalted') t += ` It is exalted here, so its results are very strong.`;
    else if (d === 'own') t += ` It is in its own sign, so it acts confidently.`;
    else if (d === 'debilitated') t += ` It is weak (debilitated) in this sign, so results come after extra effort.`;
    if (x.g[p].retrograde && p !== 'Rahu' && p !== 'Ketu') t += ' Being retrograde, its results often come later or on a second attempt.';
    if (x.g[p].combust) t += ' It is close to the Sun (combust), so it works in the background.';
    if (SPECIAL[`${p}-${h}`]) t += ' ' + SPECIAL[`${p}-${h}`];
    return t;
  }

  function lordLine(x, h) {
    const lord = x.lordOf(h), at = x.house(lord), topic = HOUSE[at].short;
    let how;
    if (at === h) how = 'it guards its own house, which makes this area self-supporting and strong.';
    else if (DUSTHANA.includes(h) && DUSTHANA.includes(at)) how = `an old rule (Viparīta Rāja Yoga) says difficulties here can turn into unexpected gains.`;
    else if (KENDRA.includes(at) || TRIKONA.includes(at)) how = `this is supportive — ${HOUSE[h].short} gets help through ${topic}.`;
    else if (DUSTHANA.includes(at)) how = `this asks for care — ${HOUSE[h].short} may see ups and downs linked to ${topic}.`;
    else how = `${HOUSE[h].short} grows through effort connected with ${topic}.`;
    return `The ruler of this house, <b>${lord}</b>, sits in your ${ord(at)} house (${topic}): ${how}`;
  }

  window.houseReading = function (c) {
    const x = ctx(c);
    return [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12].map(h => {
      const H = HOUSE[h], sign = SIGNS[x.signOf(h)], v = houseScore(x, h), pl = x.inHouse(h);
      const items = [];
      if (h === 1) items.push(`<b>Your nature (${sign} rising):</b> ${LAGNA[sign]}`);
      items.push(`<b>What it covers:</b> ${H.covers}.`);
      if (h !== 1) items.push(`<b>Your sign here, ${sign}:</b> you handle ${H.short} ${STYLE[sign]}.`);
      pl.forEach(p => items.push(planetLine(x, p, h)));
      if (!pl.length) items.push(`No planets sit here, so the results depend mainly on the ruler of the house.`);
      items.push(lordLine(x, h));
      items.push(`<b>In short:</b> ${v === 'strong' || v === 'good' ? H.good : v === 'mixed' ? H.good + ' Some ups and downs are normal here.' : H.care}`);
      return { title: `House ${h} · ${H.title}`, badge: badge(V[v]), items };
    });
  };

  function lordNature(x, p) {
    if (p === 'Rahu' || p === 'Ketu') {
      const disp = LORD[x.g[p].sign_index];
      return { kind: lordNature(x, disp).kind, note: `${p} acts like its sign lord ${disp} and the house it sits in.` };
    }
    const own = x.owns(p), tri = own.some(h => h === 5 || h === 9), ken = own.some(h => [4, 7, 10].includes(h));
    if (own.includes(1)) return { kind: 'good', note: `${p} rules your ascendant, so it works for your wellbeing.` };
    if (tri && ken) return { kind: 'great', note: `${p} rules both a kendra and a trikona house — a Yogakāraka, the best planet for your chart.` };
    if (tri) return { kind: 'good', note: `${p} rules a fortunate (trikona) house, so it is friendly for your chart.` };
    if (own.every(h => [3, 6, 8, 11, 12].includes(h))) return { kind: 'hard', note: `${p} rules only challenging houses for your ascendant, so it brings lessons along with results.` };
    return { kind: 'mixed', note: `${p} gives a mix of results for your ascendant.` };
  }

  function periodVerdict(x, p) {
    const n = lordNature(x, p), at = x.house(p), d = x.dignity(p);
    let s = { great: 3, good: 2, mixed: 0, hard: -2 }[n.kind];
    if (KENDRA.includes(at) || TRIKONA.includes(at)) s += 1;
    if (UPACHAYA.includes(at) && !BENEFIC.includes(p)) s += 1;
    if (DUSTHANA.includes(at)) s -= 1;
    if (d === 'exalted' || d === 'own') s += 1;
    if (d === 'debilitated') s -= 1;
    return { n, v: s >= 2 ? { cls: 'good', label: 'Favourable' } : s >= -1 ? { cls: '', label: 'Mixed' } : { cls: 'warn', label: 'Demanding' } };
  }

  function areas(x, p) {
    const hs = [...new Set([x.house(p), ...x.owns(p)])];
    return hs.sort((a, b) => a - b);
  }

  function periodItems(x, p, sub, parent) {
    const pv = periodVerdict(x, p), at = x.house(p), hs = areas(x, p);
    const own = x.owns(p);
    const items = [];
    if (!sub) items.push(`<b>General theme:</b> ${MD_THEME[p]}`);
    items.push(`<b>In your chart:</b> ${p} sits in your ${ord(at)} house (${HOUSE[at].short})` +
      (own.length ? ` and rules ${own.length > 1 ? 'houses' : 'house'} ${own.join(' & ')} (${own.map(h => HOUSE[h].short).join('; ')}).` : '.') + ' ' + pv.n.note);
    items.push(`<b>Areas that come alive:</b> ${hs.map(h => HOUSE[h].short).join(' · ')}.`);
    const expect = hs.slice(0, 3).map(h => {
      const ok = ['strong', 'good'].includes(houseScore(x, h));
      return (ok ? HOUSE[h].good : HOUSE[h].care).split(';')[0].replace(/\.$/, '') + '.';
    });
    items.push(`<b>What to expect:</b> ${expect.join(' ')}`);
    if (sub && parent) {
      const fr = (FRIENDS[parent] || []).includes(p), en = (ENEMIES[parent] || []).includes(p);
      const dist = (x.house(p) - x.house(parent) + 12) % 12 + 1;
      const rel = fr ? `${p} and ${parent} are natural friends, so this sub-period tends to run smoothly.`
        : en ? `${p} and ${parent} are natural opponents, so expect some push and pull between their themes.`
        : `${p} and ${parent} are neutral to each other, so results depend mostly on their placements.`;
      const pos = [6, 8].includes(dist) ? ` They sit 6/8 houses apart, which can bring friction; stay patient.`
        : [2, 12].includes(dist) ? ' They sit 2/12 apart, so watch expenses and effort.'
        : [1, 5, 9].includes(dist) ? ' They sit in harmony (trine), which helps.' : '';
      items.push(`<b>How it blends with ${parent}:</b> ${rel}${pos}`);
    }
    items.push(`<b>Helpful remedy:</b> ${REMEDY[p]}`);
    return { verdict: pv.v, items };
  }

  window.dashaReading = function (c) {
    const x = ctx(c), now = Date.now(), cur = d => now >= new Date(d.start) && now < new Date(d.end);
    const md = (c.dasha || []).find(cur);
    if (!md) return { current: null, sections: [] };
    const ad = (md.children || []).find(cur);
    const sections = [];
    const m = periodItems(x, md.lord, false);
    sections.push({ title: `${md.lord} Mahādaśā · ${fd(md.start)} – ${fd(md.end)}`, badge: badge(m.verdict), items: m.items, open: true });
    (md.children || []).forEach(a => {
      const r = periodItems(x, a.lord, true, md.lord), isNow = a === ad, past = now >= new Date(a.end);
      sections.push({ title: `${md.lord} / ${a.lord} Antardaśā · ${fd(a.start)} – ${fd(a.end)}${isNow ? ' ◀ now' : ''}`,
        badge: badge(r.verdict), items: r.items, open: isNow, past, sub: true });
    });
    const i = c.dasha.indexOf(md), nx = c.dasha[i + 1];
    if (nx) {
      const r = periodItems(x, nx.lord, false);
      sections.push({ title: `Next: ${nx.lord} Mahādaśā · from ${fd(nx.start)}`, badge: badge(r.verdict), items: r.items.slice(0, 3) });
    }
    return { current: md.lord + (ad ? ' / ' + ad.lord : ''), sections };
  };

  // ----- guidance-first summary: what to do, what to avoid, which upay -----
  const AREA = [
    { key: 'career', name: 'Career & work', houses: [10], key_planet: x => x.lordOf(10),
      good: { dos: ['Take on visible responsibility — your chart supports recognition and leadership.', 'Go ahead with the promotion, launch or new role you have been planning; pick a shubh day for the first step.'],
        donts: ['Don’t undersell yourself or stay hidden in the background.'] },
      care: { dos: ['Stay steady and keep building skills — slow progress here is still progress.', 'Keep seniors on your side: share your work and communicate often.'],
        donts: ['Don’t quit or switch jobs on impulse.', 'Avoid open clashes with bosses or authorities.'] } },
    { key: 'money', name: 'Money & savings', houses: [2, 11], key_planet: x => x.lordOf(2),
      good: { dos: ['Invest steadily for the long term — your chart supports building wealth.', 'Use your network; gains come through people you know.'],
        donts: ['Don’t let comfort turn into overspending.'] },
      care: { dos: ['Keep an emergency fund and track what you spend each month.', 'Save in small, regular amounts rather than big jumps.'],
        donts: ['Avoid lending money or standing guarantee for others.', 'Stay away from speculation and get-rich-quick offers.'] } },
    { key: 'love', name: 'Love & marriage', houses: [7], key_planet: x => ['debilitated', 'enemy'].includes(x.dignity('Venus')) ? 'Venus' : x.lordOf(7),
      good: { dos: ['Express care openly — small gestures keep the bond strong.', 'A good time to move forward on engagement or marriage; choose a shubh muhurat.'],
        donts: ['Don’t take a supportive partner for granted.'] },
      care: { dos: ['Listen more than you argue; patience is your best upay here.', 'Match kundlis carefully before marriage.'],
        donts: ['Don’t make big relationship decisions in anger or in a hurry.', 'Keep work and family stress out of the relationship.'] } },
    { key: 'health', name: 'Health & energy', houses: [1, 6], key_planet: x => x.lordOf(1),
      good: { dos: ['Keep a regular routine — your body recovers well when you rest.', 'Stay active; vitality is one of your strengths.'],
        donts: ['Don’t ignore small symptoms just because you usually bounce back.'] },
      care: { dos: ['Get regular check-ups, especially for your {body}.', 'Sleep, food and daily movement matter more for you than for most.'],
        donts: ['Avoid skipping meals and late nights.', 'Don’t self-medicate — follow your doctor.'] } },
    { key: 'home', name: 'Home & family', houses: [4], key_planet: x => x.lordOf(4),
      good: { dos: ['Spend time with your mother and family — home is your source of strength.', 'Good support for buying property or a vehicle; choose a shubh muhurat.'],
        donts: ['Don’t let work crowd out family time.'] },
      care: { dos: ['Keep your home calm, clean and full of light — it helps your peace of mind.', 'Read property papers carefully before any deal.'],
        donts: ['Avoid family disputes over property or money.', 'Don’t sign property deals in a hurry.'] } },
  ];
  const SCORE = { strong: 2, good: 1, mixed: 0, care: -1 };
  const LEVEL = {
    good: { cls: 'good', label: 'Looking good' }, mixed: { cls: '', label: 'Mixed' }, care: { cls: 'warn', label: 'Needs care' },
  };

  window.guideReading = function (c) {
    const x = ctx(c), now = Date.now(), cur = d => now >= new Date(d.start) && now < new Date(d.end);
    const md = (c.dasha || []).find(cur), ad = md && (md.children || []).find(cur);
    const active = new Set([md, ad].filter(Boolean).flatMap(d => areas(x, d.lord)));
    const sign = SIGNS[x.L];

    const lifeAreas = AREA.map(a => {
      let s = a.houses.reduce((t, h) => t + SCORE[houseScore(x, h)], 0) / a.houses.length;
      if (a.key === 'love') s += { exalted: 1, own: 1, debilitated: -1 }[x.dignity('Venus')] || 0;
      const lv = s >= 1 ? 'good' : s >= 0 ? 'mixed' : 'care';
      const set = lv === 'care' ? a.care : a.good;
      const fill = t => t.replace('{body}', BODY[sign]);
      const dos = (lv === 'mixed' ? [a.good.dos[0], a.care.dos[0]] : set.dos).map(fill);
      const donts = (lv === 'mixed' ? a.care.donts : set.donts).map(fill);
      const kp = a.key_planet(x), h = a.houses[0];
      const head = lv === 'care' ? HOUSE[h].care : HOUSE[h].good + (lv === 'mixed' ? ' Expect some ups and downs.' : '');
      return {
        key: a.key, name: a.name, level: LEVEL[lv], focus: a.houses.some(hh => active.has(hh)),
        outlook: head, dos, donts: [...donts, `Watch for ${PLANET[kp].risk}.`],
        remedy: { planet: kp, text: REMEDY[kp], why: `strengthens ${kp}, which ${kp === 'Venus' && a.key === 'love' ? 'rules love' : `rules your ${ord(h)} house`}` },
      };
    });

    let period = null;
    if (md) {
      const v = periodVerdict(x, md.lord).v;
      period = {
        md: md.lord, ad: ad && ad.lord, until: fd(md.end), adUntil: ad && fd(ad.end), verdict: v,
        text: MD_THEME[md.lord],
        now: ad ? `Right now ${ad.lord} adds ${PLANET[ad.lord].gift}, until ${fd(ad.end)}.` : '',
        focus: [...active].sort((a, b) => a - b).slice(0, 4).map(h => HOUSE[h].short),
      };
    }

    const seven = ['Sun', 'Moon', 'Mars', 'Mercury', 'Jupiter', 'Venus', 'Saturn'];
    const weak = seven.find(p => x.dignity(p) === 'debilitated') || seven.find(p => x.g[p].combust)
      || (lifeAreas.find(a => a.level.cls === 'warn') || {}).remedy?.planet;
    const lag = x.lordOf(1), lk = LUCK[lag];
    const remedies = [];
    if (md) remedies.push({ planet: md.lord, title: `For your current period`, why: `${md.lord} runs your life chapter until ${fd(md.end)}. Keeping it happy smooths the whole period.`, text: REMEDY[md.lord] });
    if (weak && weak !== (md && md.lord)) {
      const nb = ((c.strength || {}).neecha_bhanga || {})[weak];
      const why = x.dignity(weak) === 'debilitated' ? (nb && nb.cancelled
        ? `${weak} is debilitated, but the debilitation is cancelled (Neecha Bhanga): early struggles in its areas turn into strength. This upay speeds that up.`
        : `${weak} is weak in your chart (debilitated), so it needs support.`)
        : x.g[weak].combust ? `${weak} is too close to the Sun (combust) in your chart, so its gifts stay hidden without support.`
          : `${weak} rules an area of your life that needs care right now.`;
      remedies.push({ planet: weak, title: `To strengthen ${weak}`, why, text: REMEDY[weak] });
    }
    remedies.push({ planet: lag, title: 'Your life stone', why: `${lag} rules your ${sign} ascendant — it protects your health, confidence and direction.`,
      text: `${lk.gem}, worn on the ${lk.wear}. Try it for a few days first and consult before buying a costly stone.` });

    return { period, areas: lifeAreas, remedies, lucky: { day: lk.day, color: lk.color, num: lk.num }, rising: sign, moon: x.g.Moon.sign };
  };

  window.luckyReading = function (c) {
    const x = ctx(c), lag = x.lordOf(1), fifth = x.lordOf(5), ninth = x.lordOf(9);
    const sign = SIGNS[x.L], el = ['fire', 'earth', 'air', 'water'][x.L % 4];
    const lk = LUCK[lag];
    const helpers = [...new Set([fifth, ninth].filter(p => p !== lag))];
    const avoid = [...new Set([6, 8, 12].map(h => x.lordOf(h)))].filter(p => ![lag, fifth, ninth].includes(p));
    const tiles = [
      ['Lucky number', String(lk.num), helpers.length ? 'Also good: ' + helpers.map(p => LUCK[p].num).join(', ') : ''],
      ['Lucky day', lk.day, helpers.length ? 'Also good: ' + [...new Set(helpers.map(p => LUCK[p].day))].join(', ') : ''],
      ['Lucky colour', lk.color, helpers.length ? 'Also: ' + helpers.map(p => LUCK[p].color).join('; ') : ''],
      ['Life stone', lk.gem.split(' (')[0], `For ${lag}, your ascendant lord`],
    ];
    const gems = [
      `<b>Life stone — ${lk.gem}</b> for ${lag}, ruler of your ${sign} ascendant: supports health, confidence and overall direction. Wear on the ${lk.wear}.`,
      fifth !== lag ? `<b>Lucky stone — ${LUCK[fifth].gem}</b> for ${fifth}, ruler of your 5th house: supports intelligence, children and good decisions. Wear on the ${LUCK[fifth].wear}.` : '',
      ninth !== lag ? `<b>Fortune stone — ${LUCK[ninth].gem}</b> for ${ninth}, ruler of your 9th house: supports luck and blessings. Wear on the ${LUCK[ninth].wear}.` : '',
      avoid.length ? `<b>Better to avoid</b> unless an astrologer advises: ${avoid.map(p => LUCK[p].gem.split(' (')[0]).join(', ')} (${list(avoid)} rule difficult houses for you).` : '',
      '<small>Gemstones are traditional remedies. Use a natural, untreated stone, try it for a few days first, and consult before wearing Blue Sapphire or any costly stone.</small>',
    ].filter(Boolean);

    const sixth = SIGNS[x.signOf(6)], hp = [...x.inHouse(6), ...x.inHouse(8)].filter((p, i, a) => a.indexOf(p) === i);
    const lagAt = x.house(lag);
    const health = [
      `<b>Areas to look after:</b> ${BODY[sign]} (your ${sign} ascendant), and ${BODY[sixth]} (your 6th house in ${sixth}).`,
      hp.length ? `<b>Planets in the 6th/8th:</b> ${list(hp)} — be mindful of ${list(hp.map(p => PLANET_BODY[p]))}.` : '<b>No planets in the 6th or 8th house</b> — generally a good sign for health.',
      DUSTHANA.includes(lagAt) ? `<b>Vitality:</b> your ascendant lord ${lag} sits in the ${ord(lagAt)} house, so regular rest and check-ups matter more for you.`
        : `<b>Vitality:</b> your ascendant lord ${lag} is well placed in the ${ord(lagAt)} house, which supports good recovery.`,
      `<b>Tip:</b> ${ELEMENT_TIP[el]}`,
      '<small>Astrology shows tendencies only — always follow your doctor’s advice.</small>',
    ];

    const tenth = x.lordOf(10), in10 = x.inHouse(10);
    const seven = ['Sun', 'Moon', 'Mars', 'Mercury', 'Jupiter', 'Venus', 'Saturn'].sort((a, b) => x.g[b].degrees_in_sign - x.g[a].degrees_in_sign);
    const amk = seven[1];
    const fieldsFrom = [...new Set([...in10, tenth, amk])];
    const career = [
      `<b>Your 10th house is ${SIGNS[x.signOf(10)]}:</b> you work best ${STYLE[SIGNS[x.signOf(10)]]}.`,
      in10.length ? `<b>Planets in the 10th:</b> ${list(in10)} — ${in10.map(p => PLANET[p].gift).join('; ')} shape your career.` : '',
      `<b>Career lord ${tenth} in the ${ord(x.house(tenth))} house:</b> ${CAREER_BY_HOUSE[x.house(tenth)]}`,
      `<b>Career planet (Amātyakāraka) — ${amk}:</b> the Jaimini indicator of your profession.`,
      `<b>Fields that suit you:</b> ${fieldsFrom.map(p => CAREER[p]).join('; ')}.`,
      `<b>Career strength:</b> ${badge(V[houseScore(x, 10)])}`,
    ].filter(Boolean);

    const second = x.lordOf(2), eleventh = x.lordOf(11);
    const wealth = [
      `<b>Savings (2nd house):</b> ${badge(V[houseScore(x, 2)])} — ruler ${second} in your ${ord(x.house(second))} house, so money builds through ${HOUSE[x.house(second)].short}.`,
      `<b>Income (11th house):</b> ${badge(V[houseScore(x, 11)])} — ruler ${eleventh} in your ${ord(x.house(eleventh))} house, so gains come through ${HOUSE[x.house(eleventh)].short}.`,
      `<b>Jupiter (wealth and blessings)</b> is in your ${ord(x.house('Jupiter'))} house — ${!DUSTHANA.includes(x.house('Jupiter')) ? 'a helpful sign for long-term prosperity' : 'prosperity grows through wisdom and patience'}.`,
    ];

    const sev = x.lordOf(7), mars = x.house('Mars'), manglik = [1, 2, 4, 7, 8, 12].includes(mars), vd = x.dignity('Venus');
    const marriage = [
      `<b>Marriage house (7th):</b> ${badge(V[houseScore(x, 7)])} — sign ${SIGNS[x.signOf(7)]}, so your partner is likely to relate ${STYLE[SIGNS[x.signOf(7)]]}.`,
      `<b>7th lord ${sev}</b> sits in your ${ord(x.house(sev))} house — your partner may be connected with ${HOUSE[x.house(sev)].short}.`,
      `<b>Venus (love)</b> is ${vd === 'exalted' ? 'exalted — very good for love and harmony' : vd === 'own' ? 'in its own sign — good for love and comfort' : vd === 'debilitated' ? 'weak — love grows through effort and understanding' : vd === 'friendly' ? `in a friendly sign (${x.g.Venus.sign}) — supportive for love` : vd === 'enemy' ? `in an unfriendly sign (${x.g.Venus.sign}) — relationships need extra understanding and patience` : `in a neutral sign (${x.g.Venus.sign})`}.`,
      manglik ? `<b>Manglik:</b> Mars is in your ${ord(mars)} house, a Manglik placement. It is common, often balanced by the partner's chart, and calls for patience in marriage.` : '<b>Manglik:</b> No — Mars is not in a Manglik house from the ascendant.',
    ];

    return {
      tiles,
      sections: [
        { title: 'Gemstones', items: gems },
        { title: 'Career', items: career },
        { title: 'Health', items: health },
        { title: 'Wealth', items: wealth },
        { title: 'Marriage & relationships', items: marriage },
      ],
    };
  };
})();
