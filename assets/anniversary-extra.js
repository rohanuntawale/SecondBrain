/* Private, browser-local keepsake interactions. No network calls or messages. */
(() => {
  'use strict';
  const $ = id => document.getElementById(id);
  const STORAGE_KEY = 'rp-anniversary-keepsake-v1';
  let stored = {};
  let storageAvailable = true;
  try { stored = JSON.parse(localStorage.getItem(STORAGE_KEY) || '{}') || {}; }
  catch { storageAvailable = false; }
  const validIds = (value, count) => Array.isArray(value)
    ? [...new Set(value.filter(n => Number.isInteger(n) && n >= 0 && n < count))] : [];
  const state = {
    favourites: validIds(stored.favourites, 36),
    letters: validIds(stored.letters, 6),
    coupons: validIds(stored.coupons, 6),
    stars: validIds(stored.stars, 6),
    flowers: Number.isInteger(stored.flowers) ? Math.max(0, Math.min(12, stored.flowers)) : 0,
    hugs: Number.isSafeInteger(stored.hugs) ? Math.max(0, stored.hugs) : 0,
    date: typeof stored.date === 'string' ? stored.date : null,
  };
  function save() {
    try { localStorage.setItem(STORAGE_KEY, JSON.stringify(state)); }
    catch { storageAvailable = false; }
    if (!storageAvailable && !$('storage-note')) {
      const note = document.createElement('p');
      note.id = 'storage-note';
      note.className = 'storage-note';
      note.textContent = 'Your browser cannot save this visit. Everything still works until you close or refresh the page.';
      document.querySelector('footer').after(note);
    }
  }
  save();

  // Hash routes make each chapter a distinct page, with browser back support.
  const routeNames = ['home', 'notes', 'letters', 'dates', 'universe'];
  function showPage(focus = true) {
    const hash = location.hash.slice(1);
    const route = routeNames.includes(hash) ? hash : 'home';
    document.querySelectorAll('[data-page]').forEach(page => {
      page.hidden = page.dataset.page !== route;
    });
    document.querySelectorAll('[data-route]').forEach(link => {
      if (link.dataset.route === route) link.setAttribute('aria-current', 'page');
      else link.removeAttribute('aria-current');
    });
    document.title = `${route === 'home' ? 'One year of us' : document.querySelector(`[data-route="${route}"]`).textContent} · Rohan & Pooja`;
    if (routeNames.includes(hash) || !hash) {
      window.scrollTo({top: 0, behavior: 'instant'});
      if (focus) {
        const heading = document.querySelector(`[data-page="${route}"] h1`);
        heading.setAttribute('tabindex', '-1');
        heading.focus({preventScroll: true});
      }
    } else {
      // Preserve the original letter link and the keyboard skip link.
      requestAnimationFrame(() => document.getElementById(hash)?.scrollIntoView());
    }
  }
  window.addEventListener('hashchange', () => showPage());
  // A srcdoc iframe inherits the app URL as its base. Native #links would
  // navigate to a nested copy of Streamlit instead of switching chapters.
  document.addEventListener('click', event => {
    const link = event.target.closest('a[href^="#"]');
    if (!link) return;
    event.preventDefault();
    const hash = link.getAttribute('href').slice(1) || 'home';
    if (location.hash.slice(1) === hash) showPage();
    else location.hash = hash;
  });
  showPage(false);

  function hearts(button) {
    if (matchMedia('(prefers-reduced-motion: reduce)').matches) return;
    const rect = button.getBoundingClientRect();
    for (let i = 0; i < 7; i++) {
      const heart = document.createElement('span');
      heart.className = 'confetti-heart';
      heart.setAttribute('aria-hidden', 'true');
      heart.textContent = i % 2 ? '♡' : '♥';
      heart.style.left = `${rect.left + rect.width / 2}px`;
      heart.style.top = `${rect.top + rect.height / 2}px`;
      heart.style.setProperty('--float-x', `${(i - 3) * 22}px`);
      heart.style.animationDelay = `${i * .05}s`;
      document.body.appendChild(heart);
      setTimeout(() => heart.remove(), 2400);
    }
  }
  function shuffled(values) {
    const result = [...values];
    for (let i = result.length - 1; i > 0; i--) {
      const j = Math.floor(Math.random() * (i + 1));
      [result[i], result[j]] = [result[j], result[i]];
    }
    return result;
  }
  const notes = [
    ['soft', 'If my day had a favourite part, it would be the part with you in it.'],
    ['soft', 'I hope you catch yourself smiling today. And I hope, just a little, that I am the reason.'],
    ['soft', 'You are the person I want beside me when something wonderful happens — and when absolutely nothing happens.'],
    ['soft', 'I would like a hundred ordinary evenings with you. And then a hundred more.'],
    ['soft', 'Somewhere in the middle of my day, there is always a little thought of you.'],
    ['soft', 'I love that I get to say “my girlfriend” and mean you. Still makes me smile.'],
    ['soft', 'If I could send you the way I feel when I think of you, this screen would be warm.'],
    ['soft', 'You, a little sunlight, and nowhere we need to rush to. That sounds like a very good day.'],
    ['soft', 'There is so much life ahead of us. I am especially excited about the tiny bits we get to share.'],
    ['soft', 'I made you a whole garden because “thinking of you” needed somewhere to bloom.'],
    ['soft', 'I want to learn the little things that make you feel loved, and then remember to do them.'],
    ['soft', 'Pooja. Even your name is one of my favourite things to see on my screen.'],
    ['silly', 'You are my favourite distraction. This is a formal complaint. Please continue.'],
    ['silly', 'I was going to play it cool. Then you existed. Very inconvenient of you.'],
    ['silly', 'Your boyfriend has been diagnosed with a serious case of wanting to hold your hand.'],
    ['silly', 'If being ridiculously into you were a full-time job, I would be employee of the month.'],
    ['silly', 'Important announcement: you are cute. Further updates will follow unnecessarily often.'],
    ['silly', 'I want to steal your attention. And maybe a bite of whatever you are eating.'],
    ['silly', 'My brain has many tabs open. An embarrassing number of them are you.'],
    ['silly', 'I like you more than a perfectly working Wi-Fi connection. Please appreciate the gravity of this statement.'],
    ['silly', 'You + me + snacks. I believe I have solved weekend planning.'],
    ['silly', 'This note is redeemable for one forehead kiss. Actually, several. I am bad at these limits.'],
    ['silly', 'I checked the sunflower garden. You are still the cutest thing here. The flowers are taking it well.'],
    ['silly', 'Congratulations! You have won another day of me being extremely fond of you. There is no unsubscribe button on my feelings.'],
    ['comfort', 'You can have a quiet day. You do not have to be entertaining or cheerful to be loved by me.'],
    ['comfort', 'If today was a lot, let this be small: a breath, a sip of water, and a reminder that I care about you.'],
    ['comfort', 'You do not have to solve everything tonight. I would happily sit beside you while the world waits a minute.'],
    ['comfort', 'I want the honest answer when I ask how you are. Even if it takes a while to find the words.'],
    ['comfort', 'Being tired does not make you less wonderful. Put the heavy things down for a little while, love.'],
    ['comfort', 'I am proud of the effort nobody else gets to see. I hope you give yourself a little credit too.'],
    ['comfort', 'You deserve gentleness, especially from yourself. Pretend this note is me reminding you very softly.'],
    ['comfort', 'A messy day is still a day I am glad you are in my life.'],
    ['comfort', 'You are allowed to ask for a little extra reassurance. I do not want you guessing whether you matter to me.'],
    ['comfort', 'If I cannot fix the thing, I can still listen. And listen again.'],
    ['comfort', 'There is no version of a difficult day that makes you a burden for having feelings.'],
    ['comfort', 'For now, unclench your shoulders. Imagine my hand in yours. We can take the next little step slowly.'],
  ];
  let filter = 'all';
  let currentNote = null;
  const noteDecks = new Map();
  function drawNote() {
    let deck = noteDecks.get(filter) || [];
    if (!deck.length) {
      deck = shuffled(notes.map((_, i) => i).filter(i => filter === 'all' || notes[i][0] === filter));
      if (deck[deck.length - 1] === currentNote) [deck[0], deck[deck.length - 1]] = [deck[deck.length - 1], deck[0]];
    }
    currentNote = deck.pop();
    noteDecks.set(filter, deck);
    $('jar-note').textContent = notes[currentNote][1];
    $('note-number').textContent = `Little love note ${String(currentNote + 1).padStart(2, '0')} / 36`;
    $('save-note').disabled = false;
    updateSaveButton();
    $('note-status').textContent = deck.length ? `${deck.length} more little reminders in this collection.` : 'Every note read. Another tap gives your collection a fresh shuffle.';
  }
  function updateSaveButton() {
    const saved = state.favourites.includes(currentNote);
    $('save-note').textContent = saved ? '♥ Kept for you' : '♡ Keep this one';
    $('save-note').setAttribute('aria-pressed', String(saved));
  }
  function renderSavedNotes() {
    $('saved-notes').replaceChildren();
    if (!state.favourites.length) {
      const empty = document.createElement('p');
      empty.className = 'empty-saved';
      empty.textContent = 'Your little collection starts with “Keep this one.”';
      $('saved-notes').appendChild(empty);
    }
    state.favourites.forEach(id => {
      const article = document.createElement('article');
      article.className = 'saved-note';
      const text = document.createElement('p');
      text.textContent = notes[id][1];
      const remove = document.createElement('button');
      remove.textContent = 'Put this one back in the jar';
      remove.setAttribute('aria-label', `Remove saved note ${id + 1}`);
      remove.addEventListener('click', () => {
        const index = state.favourites.indexOf(id);
        state.favourites = state.favourites.filter(n => n !== id);
        save(); renderSavedNotes(); updateSaveButton();
        const buttons = $('saved-notes').querySelectorAll('button');
        (buttons[Math.min(index, buttons.length - 1)] || $('draw-note')).focus();
        $('note-status').textContent = 'Back in the jar. You can always keep it again.';
      });
      article.append(text, remove);
      $('saved-notes').appendChild(article);
    });
  }
  document.querySelectorAll('[data-note-filter]').forEach(button => button.addEventListener('click', () => {
    filter = button.dataset.noteFilter;
    document.querySelectorAll('[data-note-filter]').forEach(b => b.setAttribute('aria-pressed', String(b === button)));
    drawNote();
  }));
  $('draw-note').addEventListener('click', drawNote);
  $('save-note').addEventListener('click', () => {
    if (currentNote === null) return;
    if (state.favourites.includes(currentNote)) state.favourites = state.favourites.filter(n => n !== currentNote);
    else { state.favourites.push(currentNote); hearts($('save-note')); }
    save(); renderSavedNotes(); updateSaveButton();
    $('note-status').textContent = state.favourites.includes(currentNote) ? 'Kept between our pages, just for you.' : 'Back in the jar, ready to find you again.';
  });
  renderSavedNotes();

  const letters = [
    ['you miss me', [
      'Hi, my love. If I could step out of this little envelope and sit beside you, I would. Preferably close enough that our shoulders touch.',
      'Until then, here is what I want you to know: missing you is also wanting to hear about your day. The boring bits, the funny bits, the thing you almost forgot to tell me. I want those too.',
      'When we next get a little time together, let’s leave some of it unplanned. No impressive activity required. Just you and me, being happy about the you-and-me part.',
      'Consider this an extremely long hug, folded down to fit in an envelope.'
    ]],
    ['today feels heavy', [
      'You do not need to make this a happy letter. If today was difficult, we can let it have been difficult.',
      'Take a breath if you can. Put down whatever you can put down for a moment. I wish I could bring you some water and sit quietly next to you without asking you to explain everything.',
      'You are not less lovable when you are worn out. You do not have to package your feelings nicely for me.',
      'When you feel like talking, tell me what you need: a listening ear, a distraction, or just some company. I want to get better at being there in the way that helps you.'
    ]],
    ['you need a smile', [
      'This is an official message from your boyfriend: I have reviewed the available evidence and concluded that I like you a frankly unreasonable amount.',
      'Symptoms include smiling at your name, making a whole website about you, and considering “look at this cute sunflower” a valid reason to interrupt your day.',
      'There is currently no plan to become normal about you. Thank you for your patience during this ongoing situation.',
      'Also, imagine me trying to hand you this letter with a perfectly serious face. I would ruin it by smiling immediately.'
    ]],
    ['you cannot sleep', [
      'Hello, sleepy sunflower. You do not need to reply to this letter. That is the nicest thing about a letter waiting here for you.',
      'Imagine a quiet evening, a soft blanket, and nothing left to prove to anyone. I would like to be there, talking softly until neither of us finishes a sentence.',
      'Whatever tomorrow needs can wait a little. You have already made it through today.',
      'If putting the phone down feels right, this is your little goodnight. I love you. This page will still be here in the morning.'
    ]],
    ['you doubt yourself', [
      'I know one little letter cannot untangle every doubtful thought. But I can leave you something kinder to read alongside them.',
      'You are allowed to be learning. You are allowed to need another try. One difficult moment is not the whole story of who you are.',
      'I care about the person doing the trying, not just the outcome. And I want to hear about the dreams that matter to you, even the ones you are still working up the courage to say out loud.',
      'I am in your corner, Pooja. Not with a scoreboard. With a very enthusiastic amount of affection.'
    ]],
    ['you think about us', [
      'One whole year. And somehow the thought of more ordinary days with you still feels like the most exciting part.',
      'I do not expect us to have every answer. I want us to keep asking, keep listening, and keep making space for the real people we are.',
      'I want more silly conversations. More little plans. More moments where one of us says “wait, I have to tell you something” and the other stays to hear it.',
      'If our first year is a pressed flower between these pages, the next one is a whole empty garden. I would really like to grow it with you.'
    ]],
  ];
  const dialog = $('love-letter-dialog');
  letters.forEach(([title, paragraphs], id) => {
    const button = document.createElement('button');
    button.className = 'envelope';
    const preface = document.createElement('span'); preface.className = 'eyebrow'; preface.textContent = 'Open when…';
    const label = document.createElement('strong'); label.textContent = title;
    const read = document.createElement('span'); read.className = 'read-mark'; read.textContent = state.letters.includes(id) ? 'Opened with love ♡' : 'Just for you';
    button.append(preface, label, read);
    button.addEventListener('click', () => {
      $('opened-letter-title').textContent = `When ${title}…`;
      $('opened-letter-body').replaceChildren(...paragraphs.map(text => { const p = document.createElement('p'); p.textContent = text; return p; }));
      if (!state.letters.includes(id)) state.letters.push(id);
      read.textContent = 'Opened with love ♡'; save();
      dialog.showModal(); dialog.scrollTop = 0;
    });
    $('envelopes').appendChild(button);
  });
  dialog.querySelectorAll('.dialog-close,.dialog-done').forEach(button => button.addEventListener('click', () => dialog.close()));
  dialog.addEventListener('click', event => { if (event.target === dialog) {
    const rect = dialog.getBoundingClientRect();
    if (event.clientX < rect.left || event.clientX > rect.right || event.clientY < rect.top || event.clientY > rect.bottom) dialog.close();
  }});

  const dates = {
    cosy: [
      ['The tiny living-room picnic', 'Spread out a blanket, gather your favourite snacks, and eat like the floor is the nicest restaurant in town.', 'Bring: snacks, two drinks, and one very soft blanket.'],
      ['A very unserious portrait studio', 'Give each other ten minutes to draw a portrait. Reveal them together. Artistic talent is absolutely not an entry requirement.', 'Bring: paper, pencils, and a generous interpretation of “likeness.”'],
      ['Our two-person film festival', 'Each choose one short film or a favourite episode. Trade picks, share snacks, and give the evening a wildly pretentious review.', 'Bring: two picks and a snack worth sharing.'],
      ['The little kitchen experiment', 'Pick one simple recipe neither of us has tried. Make it together and give our imaginary café a name.', 'Bring: one recipe, the ingredients, and room for a delicious mistake.'],
    ],
    outside: [
      ['The sunflower mission', 'Take a little walk and look for something yellow: a flower, a sign, a doorway. Photograph five things that feel like sunshine.', 'Bring: a phone, comfortable shoes, and a yellow-things radar.'],
      ['A sunset with no agenda', 'Find a comfortable place to watch the evening change colour. Each bring one question you have always wanted to ask the other.', 'Bring: water and enough time to stay a little longer.'],
      ['The choose-for-me snack date', 'Visit a place with a few snack options and choose something for each other. Explain your extremely scientific selection process.', 'Bring: a small snack budget and your best food-review voice.'],
      ['The bookshop daydream', 'Browse a bookshop or library. Find a title that sounds like us and a place in a book you would like to visit together.', 'Bring: curiosity. Buying anything is optional.'],
    ],
    apart: [
      ['Same sky, same little moment', 'At the same time, each take a photo of the view from where you are. Trade photos and one thing you wish the other could see.', 'Bring: a phone and a few uninterrupted minutes.'],
      ['The three-song love note', 'Each pick three songs: one for today, one that makes you think of us, and one for a future adventure. Listen and explain the picks.', 'Bring: three songs and the stories behind them.'],
      ['Dinner on both sides of the screen', 'Choose the same kind of easy meal, set a time, and have a video-call dinner. Take turns asking the questions.', 'Bring: dinner, a charged phone, and a little time for just us.'],
      ['A tiny scavenger hunt', 'Give each other five prompts: something cosy, something yellow, something funny, something old, and something you want to explain.', 'Bring: five objects nearby and your best show-and-tell energy.'],
    ],
  };
  let mood = 'cosy'; let currentDate = null;
  const dateDecks = new Map();
  function lookupDate(key) { const [type, index] = (key || '').split(':'); return dates[type]?.[Number(index)]; }
  function renderSavedDate() {
    const plan = lookupDate(state.date);
    $('saved-date').hidden = !plan;
    $('saved-date').textContent = plan ? `Saved for us: ${plan[0]}. ${plan[1]} ${plan[2]}` : '';
  }
  document.querySelectorAll('[data-date-mood]').forEach(button => button.addEventListener('click', () => {
    mood = button.dataset.dateMood;
    document.querySelectorAll('[data-date-mood]').forEach(b => b.setAttribute('aria-pressed', String(b === button)));
    pickDate();
  }));
  function pickDate() {
    let deck = dateDecks.get(mood) || [];
    if (!deck.length) { deck = shuffled([0, 1, 2, 3]); if (`${mood}:${deck[3]}` === currentDate) [deck[0], deck[3]] = [deck[3], deck[0]]; }
    const index = deck.pop(); dateDecks.set(mood, deck); currentDate = `${mood}:${index}`;
    const [title, description, detail] = dates[mood][index];
    $('date-label').textContent = document.querySelector(`[data-date-mood="${mood}"]`).textContent;
    $('date-title').textContent = title; $('date-description').textContent = description; $('date-detail').textContent = detail;
    $('keep-date').disabled = false; $('keep-date').textContent = state.date === currentDate ? '♥ Plan saved' : '♡ Save this plan';
    $('date-status').textContent = 'A suggestion, a little anticipation, and a very cute date partner.';
  }
  $('pick-date').addEventListener('click', pickDate);
  $('keep-date').addEventListener('click', () => {
    if (!currentDate) return;
    state.date = currentDate; save(); renderSavedDate();
    $('keep-date').textContent = '♥ Plan saved';
    $('date-status').textContent = 'Saved here for us. Now we just need to choose a day together.';
    hearts($('keep-date'));
  });
  renderSavedDate();
  const coupons = [
    ['A forehead kiss', 'Or a rain check until we are together.'],
    ['You pick the movie', 'Yes, I will pay attention to the plot.'],
    ['One very long hug', 'No rushing the letting-go part.'],
    ['A listening date', 'Your stories. My full attention.'],
    ['A handwritten note', 'The pen-and-paper kind of “I love you.”'],
    ['A sunflower outing', 'Let’s go find you a little sunshine.'],
  ];
  coupons.forEach(([title, description], id) => {
    const button = document.createElement('button'); button.className = 'coupon';
    const mark = document.createElement('span'); mark.className = 'coupon-mark'; mark.textContent = '♡';
    const heading = document.createElement('strong'); heading.textContent = title;
    const detail = document.createElement('small'); detail.textContent = description;
    const status = document.createElement('p'); status.className = 'tiny-status';
    const render = () => { const kept = state.coupons.includes(id); button.setAttribute('aria-pressed', String(kept)); status.textContent = kept ? 'In your pocket ♥ · tap to put back' : 'Tuck into your pocket ↗'; };
    button.append(mark, heading, detail, status); render();
    button.addEventListener('click', () => {
      if (state.coupons.includes(id)) state.coupons = state.coupons.filter(n => n !== id);
      else { state.coupons.push(id); hearts(button); }
      save(); render();
    });
    $('coupons').appendChild(button);
  });

  const stars = [
    [10, 66, 'You are my favourite “just one more minute” before saying goodbye.'],
    [26, 24, 'Somewhere between all our conversations, you became the person I most wanted to talk to.'],
    [47, 51.2, 'I hope we get to be wonderfully silly together for a very long time.'],
    [62, 18, 'If I could bottle a feeling for you, it would be knowing you are wanted here.'],
    [85, 44, 'There are so many places in this world. Beside you is high on my list.'],
    [74, 83.2, 'A whole sky of possibilities, and I am here making little wishes about us.'],
  ];
  function updateStarProgress() { $('star-progress').textContent = state.stars.length === 6 ? 'A whole constellation of us. You found every little light. ♡' : `${state.stars.length} of 6 little lights discovered`; }
  stars.forEach(([x, y, message], id) => {
    const button = document.createElement('button'); button.className = 'star-button'; button.textContent = '✧';
    button.style.left = `${x}%`; button.style.top = `${y}%`;
    button.setAttribute('aria-label', `Discover star ${id + 1}`);
    button.setAttribute('aria-pressed', String(state.stars.includes(id)));
    button.addEventListener('click', () => {
      if (!state.stars.includes(id)) state.stars.push(id);
      button.setAttribute('aria-pressed', 'true'); $('star-message').textContent = message; updateStarProgress(); save();
    });
    $('constellation').appendChild(button);
  });
  updateStarProgress();
  const hugs = ['Come here, love. Imagine the sort of hug that lets your shoulders drop.', 'An extra squeeze, because the first one was clearly not enough.', 'One hand in yours. One very happy boyfriend.', 'No clever words for this one. Just a long, warm hug.', 'Still here. Still very, very fond of you.'];
  function updateHugs() { $('hug-count').textContent = state.hugs ? `${state.hugs} little ${state.hugs === 1 ? 'hug' : 'hugs'} collected. There is always another.` : 'Unlimited hugs. Obviously.'; }
  $('hug-button').addEventListener('click', () => {
    $('hug-message').textContent = hugs[state.hugs % hugs.length]; state.hugs++; save(); updateHugs();
    $('hug-button').classList.remove('hugging'); void $('hug-button').offsetWidth; $('hug-button').classList.add('hugging'); hearts($('hug-button'));
  });
  updateHugs();
  const wishes = ['More mornings to say good morning.', 'More laughing until the story stops making sense.', 'More listening, even when words come slowly.', 'More snacks that somehow become a date.', 'More courage for the dreams we care about.', 'More little things worth telling each other.', 'More gentle days when the world gets loud.', 'More adventures, even tiny ones.', 'More honest conversations and softer landings.', 'More reasons to put the phone down and stay.', 'More growing into ourselves, beside each other.', 'And always, always, more us.'];
  function renderGarden() {
    $('mini-garden').replaceChildren();
    for (let i = 0; i < 12; i++) {
      const slot = document.createElement('span');
      if (i < state.flowers) {
        slot.innerHTML = '<svg viewBox="-85 -85 170 200" aria-hidden="true"><path d="M0 15 L0 105" stroke="#698044" stroke-width="6"/><use href="#leaf" transform="translate(0 95) scale(.6)"/><use href="#flower"/></svg>';
        slot.setAttribute('aria-label', `Sunflower ${i + 1}`); slot.setAttribute('role', 'img');
      } else { slot.className = 'seed-space'; slot.textContent = '·'; slot.setAttribute('aria-hidden', 'true'); }
      $('mini-garden').appendChild(slot);
    }
    $('plant-flower').disabled = state.flowers === 12;
    $('plant-flower').textContent = state.flowers === 12 ? 'Our little garden is in bloom ♡' : 'Plant a little sunshine ＋';
    $('plant-message').textContent = state.flowers ? `${state.flowers}/12 · ${wishes[state.flowers - 1]}` : 'A little room to grow, together.';
  }
  $('plant-flower').addEventListener('click', () => { if (state.flowers < 12) { state.flowers++; save(); renderGarden(); } });
  renderGarden();
  const pairs = [{symbol: '🌻', label: 'sunflower'}, {symbol: '♡', label: 'heart'}, {symbol: '☾', label: 'moon'}, {symbol: '💋', label: 'kiss'}];
  let mismatchTimer = null;
  function startMatchingGame() {
    clearTimeout(mismatchTimer);
    const cards = shuffled([...pairs, ...pairs]);
    let open = []; let moves = 0; let matches = 0; let locked = false;
    $('match-grid').replaceChildren();
    $('match-status').textContent = 'Turn over two cards to begin, love.';
    cards.forEach((pair, id) => {
      const button = document.createElement('button'); button.className = 'match-card';
      const close = () => { button.textContent = 'R + P'; button.dataset.open = 'false'; button.setAttribute('aria-label', `Turn over card ${id + 1}`); };
      close();
      button.addEventListener('click', () => {
        if (locked || button.dataset.open === 'true' || button.dataset.matched === 'true') return;
        button.textContent = pair.symbol; button.dataset.open = 'true'; button.setAttribute('aria-label', `Card ${id + 1}: ${pair.label}`);
        open.push({button, pair, close});
        if (open.length < 2) { $('match-status').textContent = `${pair.label[0].toUpperCase() + pair.label.slice(1)}. Find its little other half.`; return; }
        moves++;
        if (open[0].pair.label === open[1].pair.label) {
          matches++; open.forEach(card => { card.button.dataset.matched = 'true'; card.button.setAttribute('aria-label', `${card.pair.label}: matched`); }); open = [];
          $('match-status').textContent = matches === 4 ? `All four pairs found in ${moves} turns. My favourite pair is still you and me. Here's your kiss. 💋` : `${matches} of 4 pairs together · ${moves} ${moves === 1 ? 'turn' : 'turns'}. Some things are meant to find each other.`;
          if (matches === 4) hearts($('restart-match'));
        } else {
          locked = true; $('match-status').textContent = `Not quite their other halves. ${moves} ${moves === 1 ? 'turn' : 'turns'} · keep looking, love.`;
          mismatchTimer = setTimeout(() => { open.forEach(card => card.close()); open = []; locked = false; }, 950);
        }
      });
      $('match-grid').appendChild(button);
    });
  }
  $('restart-match').addEventListener('click', startMatchingGame);
  startMatchingGame();
  $('yes-button').addEventListener('click', () => {
    $('yes-message').textContent = 'Excellent. Your subscription includes terrible jokes, enthusiastic support, and a boyfriend who is very happy it is you. ♡';
    $('yes-button').textContent = 'Your ridiculous human, reporting for duty ♥'; hearts($('yes-button'));
  });
  const secrets = ['Psst. This entire place is just a very elaborate way of saying I love you.', 'If you were wondering: yes, I smiled while making this for you.', 'Tiny secret number three: I would absolutely make you another whole garden.', 'You found the secret corner. Your prize is one imaginary kiss on the nose. ♡'];
  let secretIndex = 0;
  $('secret-button').addEventListener('click', () => { $('secret-message').textContent = secrets[secretIndex++ % secrets.length]; hearts($('secret-button')); });
})();
