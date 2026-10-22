/* NEON RUSH — Engine (renderer + avtomatik sifat), Input (touch tugmalar / giroskop / klaviatura), UI (menyu, HUD,
   minikarta, natijalar), o'yin sikli va NR3D.launch({onResult, onExit}). */
(function () {
  'use strict';
  const NR = window.NR3D, U = NR.U, A = NR.Audio, CARS = NR.CARS, PU = NR.PU, TR = NR.World.TRACKS;
  const el = (tag, cls, html) => { const e = document.createElement(tag); if (cls) e.className = cls; if (html !== undefined) e.innerHTML = html; return e; };
  const esc = (s) => String(s).replace(/[&<>"]/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));
  const DIFFS = { easy: ['Easy', 'Sekinroq raqiblar, kam hujum'], normal: ['Normal', 'Muvozanatli poyga'], hard: ['Hard', 'Tez, tajovuzkor raqiblar'] };
  const MODES = { race: ['Power Race', 'Power-up’lar bilan jangovar poyga (3 aylana)'], clean: ['Clean Race', 'Faqat tezlik: power-up’larsiz toza poyga'] };

  function hasWebGL() { try { const c = document.createElement('canvas'); return !!(window.WebGLRenderingContext && (c.getContext('webgl') || c.getContext('experimental-webgl'))); } catch (e) { return false; } }
  function weakDevice() { const m = navigator.deviceMemory, c = navigator.hardwareConcurrency; return (m && m <= 3) || (c && c <= 4); }

  // ══ Engine ══
  function Engine(view) {
    this.view = view; const q = NR.Save.data.settings.quality;
    this.auto = q === 'auto'; this.quality = this.auto ? (weakDevice() ? 'low' : 'medium') : q;
    this.renderer = new THREE.WebGLRenderer({ antialias: this.quality === 'high', powerPreference: 'high-performance', alpha: false });
    view.appendChild(this.renderer.domElement);
    this.camera = new THREE.PerspectiveCamera(70, 1, 0.3, 1200);
    this.prScale = 1; this.applyQuality();
    this.onResize = () => this.resize(); window.addEventListener('resize', this.onResize); window.addEventListener('orientationchange', this.onResize); this.resize();
  }
  Engine.prototype.applyQuality = function () { const dpr = window.devicePixelRatio || 1, base = { low: 0.6, medium: 1, high: 1.5 }[this.quality] || 1; this.renderer.setPixelRatio(Math.min(dpr, base) * this.prScale); };
  Engine.prototype.resize = function () { const w = this.view.clientWidth || innerWidth, h = this.view.clientHeight || innerHeight; this.renderer.setSize(w, h, false); this.renderer.domElement.style.width = '100%'; this.renderer.domElement.style.height = '100%'; this.camera.aspect = w / Math.max(1, h); this.camera.updateProjectionMatrix(); };
  Engine.prototype.dispose = function () { window.removeEventListener('resize', this.onResize); window.removeEventListener('orientationchange', this.onResize); this.renderer.dispose(); try { this.renderer.forceContextLoss(); } catch (e) { /* */ } this.renderer.domElement.remove(); };

  // ══ Input ══
  function Input(root, ctl) {
    const s = (this.s = { left: false, right: false, brake: false, fire: false, back: false, cycle: false, pause: false, cam: false, keys: {}, tilt: 0, tiltOk: false });
    const btn = (e) => e.target.closest('[data-a]');
    this.ptr = new Map();
    this.down = (e) => {
      const b = btn(e); if (!b) return; e.preventDefault(); try { ctl.setPointerCapture(e.pointerId); } catch (x) { /* */ }
      this.ptr.set(e.pointerId, b); b.classList.add('down'); const a = b.dataset.a;
      if (a === 'left' || a === 'right' || a === 'brake') s[a] = true; else s[a] = true;
      A.resume();
    };
    this.up = (e) => { const b = this.ptr.get(e.pointerId); if (!b) return; this.ptr.delete(e.pointerId); b.classList.remove('down'); const a = b.dataset.a; if (a === 'left' || a === 'right' || a === 'brake') s[a] = [...this.ptr.values()].some((x) => x.dataset.a === a); };
    ctl.addEventListener('pointerdown', this.down, { passive: false }); ctl.addEventListener('pointerup', this.up); ctl.addEventListener('pointercancel', this.up); ctl.addEventListener('lostpointercapture', this.up);
    this.block = (e) => { if (root.classList.contains('playing')) e.preventDefault(); };
    root.addEventListener('touchmove', this.block, { passive: false }); root.addEventListener('contextmenu', (e) => e.preventDefault());
    const KEYS = { ArrowLeft: 1, ArrowRight: 1, KeyA: 1, KeyD: 1, ArrowDown: 1, KeyS: 1, ShiftLeft: 1 };
    this.kd = (e) => {
      if (!root.classList.contains('playing')) return; if (KEYS[e.code]) { s.keys[e.code] = true; e.preventDefault(); } if (e.repeat) return;
      if (e.code === 'Space' || e.code === 'KeyW' || e.code === 'ArrowUp') { s.fire = true; e.preventDefault(); }
      if (e.code === 'KeyE') s.back = true; if (e.code === 'KeyQ' || e.code === 'Tab') { s.cycle = true; e.preventDefault(); }
      if (e.code === 'Escape' || e.code === 'KeyP') s.pause = true; if (e.code === 'KeyC') s.cam = true;
    };
    this.ku = (e) => { if (KEYS[e.code]) s.keys[e.code] = false; };
    addEventListener('keydown', this.kd); addEventListener('keyup', this.ku);
    this.orient = (e) => {
      if (e.gamma == null) return; s.tiltOk = true;
      const land = Math.abs(window.orientation || (screen.orientation && screen.orientation.angle) || 0) === 90;
      let v = land ? e.beta : e.gamma; if (land && ((window.orientation || (screen.orientation && screen.orientation.angle)) === -90 || (screen.orientation && screen.orientation.angle === 270))) v = -v;
      s.tilt = U.clamp(v / 28, -1, 1);
    };
    addEventListener('deviceorientation', this.orient);
  }
  Input.prototype.steer = function () {
    const s = this.s, k = s.keys, set = NR.Save.data.settings;
    let v = (s.right || k.ArrowRight || k.KeyD ? 1 : 0) - (s.left || k.ArrowLeft || k.KeyA ? 1 : 0);
    if (!v && set.steer === 'tilt' && s.tiltOk) { v = s.tilt * set.tilt; if (Math.abs(v) < 0.06) v = 0; v = U.clamp(v, -1, 1); }
    return v;
  };
  Input.prototype.brake = function () { const k = this.s.keys; return this.s.brake || k.ArrowDown || k.KeyS || k.ShiftLeft; };
  Input.prototype.release = function () { const s = this.s; s.left = s.right = s.brake = s.fire = s.back = s.cycle = false; s.keys = {}; this.ptr.clear(); };
  Input.prototype.dispose = function (ctl, root) {
    ctl.removeEventListener('pointerdown', this.down); ctl.removeEventListener('pointerup', this.up); ctl.removeEventListener('pointercancel', this.up); ctl.removeEventListener('lostpointercapture', this.up);
    root.removeEventListener('touchmove', this.block); removeEventListener('keydown', this.kd); removeEventListener('keyup', this.ku); removeEventListener('deviceorientation', this.orient);
  };

  // ══ UI ══
  const UI = {
    mount(root, H) {
      this.root = root; this.H = H; root.innerHTML = '';
      this.view = el('div', 'nr-view'); root.appendChild(this.view);
      const hud = (this.hud = el('div', 'nr-hud'));
      hud.innerHTML = '<div class="nr-pos" id="nrPos"><b>8</b><span>/8</span></div><div class="nr-lap" id="nrLap"></div><div class="nr-time" id="nrTime"></div>' +
        '<canvas class="nr-map" id="nrMap" width="132" height="132"></canvas><div class="nr-feed" id="nrFeed"></div><div class="nr-fps" id="nrFps"></div>' +
        '<div class="nr-items" id="nrItems"></div><div class="nr-spd"><b id="nrSpd">0</b><span>km/h</span><div class="nr-hp"><i id="nrHp"></i></div></div>' +
        '<div class="nr-fans" id="nrFans">0 ✦</div><div class="nr-big" id="nrBig"></div><div class="nr-dmg" id="nrDmg"></div>';
      root.appendChild(hud);
      const ctl = (this.ctl = el('div', 'nr-ctl'));
      ctl.innerHTML = '<button class="nr-b nr-l" data-a="left">◀</button><button class="nr-b nr-r" data-a="right">▶</button>' +
        '<button class="nr-b nr-brk" data-a="brake">DRIFT</button><button class="nr-b nr-fire" data-a="fire">FIRE</button><button class="nr-b nr-bk" data-a="back">↶</button>' +
        '<button class="nr-b nr-pz" data-a="pause">❚❚</button><button class="nr-b nr-cam" data-a="cam">🎥</button>';
      root.appendChild(ctl);
      this.menu = el('div', 'nr-menu'); root.appendChild(this.menu);
      this.over = el('div', 'nr-over'); root.appendChild(this.over);
      const $ = (id) => root.querySelector('#' + id);
      this.e = { pos: $('nrPos'), lap: $('nrLap'), time: $('nrTime'), map: $('nrMap'), feed: $('nrFeed'), fps: $('nrFps'), items: $('nrItems'), spd: $('nrSpd'), hp: $('nrHp'), fans: $('nrFans'), big: $('nrBig'), dmg: $('nrDmg') };
      this.mctx = this.e.map.getContext('2d'); this.cache = {};
      this.e.items.addEventListener('pointerdown', (e) => { e.preventDefault(); H.cycle(); });
      this.apply();
    },
    apply() { const s = NR.Save.data.settings; this.root.style.setProperty('--nrb', String(U.clamp(s.btn, 0.7, 1.5))); this.e.fps.style.display = s.fps ? '' : 'none'; this.root.classList.toggle('tilt', s.steer === 'tilt'); },
    playing(on) { this.root.classList.toggle('playing', on); this.menu.classList.toggle('on', !on); },
    set(k, v, fn) { if (this.cache[k] === v) return; this.cache[k] = v; fn(v); },
    hudUpdate(R) {
      const pl = R.player, e = this.e, n = R.cars.length;
      this.set('pos', pl.place + '/' + n, () => (e.pos.innerHTML = '<b>' + pl.place + '</b><span>/' + n + '</span>'));
      this.set('lap', Math.max(1, Math.min(R.laps, pl.lap + 1)), (v) => (e.lap.textContent = 'LAP ' + v + '/' + R.laps));
      this.set('time', Math.floor(pl.lapT * 10), () => (e.time.textContent = U.fmtLap(pl.lapT) + (pl.bestLap ? '  ·  best ' + U.fmtLap(pl.bestLap) : '')));
      this.set('spd', Math.round(Math.abs(pl.v) * 3.6), (v) => (e.spd.textContent = v));
      this.set('hp', Math.ceil(pl.hp / pl.maxHp * 50), () => { e.hp.style.width = (pl.hp / pl.maxHp * 100) + '%'; e.hp.parentNode.classList.toggle('low', pl.hp < pl.maxHp * 0.3); });
      this.set('fans', pl.fans, (v) => (e.fans.textContent = v + ' ✦'));
      this.set('items', pl.items.join(',') + '|' + pl.sel + '|' + (R.mode === 'clean'), () => {
        if (R.mode === 'clean') { e.items.innerHTML = ''; return; }
        let h = ''; for (let i = 0; i < 3; i++) { const k = pl.items[i]; h += '<i class="' + (k ? 'on' : '') + (k && i === pl.sel ? ' sel' : '') + '" style="' + (k ? '--c:' + PU[k].col : '') + '">' + (k ? PU[k].icon : '') + '</i>'; }
        e.items.innerHTML = h + (pl.items.length ? '<span>' + PU[pl.items[pl.sel]].name + '</span>' : '');
      });
      this.drawMap(R);
    },
    drawMap(R) {
      const g = this.mctx, T = R.track, m = (this.mm = this.mm || T.minimap()), W = 132, pad = 10, sc = (W - pad * 2) / m.s;
      if (!this.mapBase || this.mapBase.t !== T) {
        const c = document.createElement('canvas'); c.width = c.height = W; const b = c.getContext('2d');
        b.strokeStyle = 'rgba(255,255,255,.75)'; b.lineWidth = 3; b.lineJoin = 'round'; b.beginPath();
        for (let i = 0; i <= T.M; i += 2) { const k = i % T.M, x = pad + (T.px[k] - m.x0) * sc, y = pad + (T.pz[k] - m.z0) * sc; i ? b.lineTo(x, y) : b.moveTo(x, y); }
        b.closePath(); b.stroke(); this.mapBase = { t: T, c };
      }
      g.clearRect(0, 0, W, W); g.drawImage(this.mapBase.c, 0, 0);
      for (const c of R.cars) {
        const x = pad + (c.x - m.x0) * sc, y = pad + (c.z - m.z0) * sc; g.fillStyle = c === R.player ? '#fff' : '#' + new THREE.Color(c.color).getHexString();
        g.beginPath(); g.arc(x, y, c === R.player ? 4.5 : 3, 0, 7); g.fill(); if (c === R.player) { g.strokeStyle = '#000'; g.lineWidth = 1.5; g.stroke(); }
      }
    },
    fps(v) { this.e.fps.textContent = v + ' FPS'; },
    big(text, dur, cls) { const b = this.e.big; b.innerHTML = text; b.className = 'nr-big on ' + (cls || ''); clearTimeout(this.bigT); if (dur) this.bigT = setTimeout(() => (b.className = 'nr-big'), dur * 1000); },
    feed(text, cls) { const r = el('div', 'nr-fd ' + (cls || ''), text); this.e.feed.prepend(r); while (this.e.feed.children.length > 4) this.e.feed.lastChild.remove(); setTimeout(() => r.remove(), 3200); },
    damage() { const d = this.e.dmg; d.classList.remove('on'); void d.offsetWidth; d.classList.add('on'); },
    toast(t) { const d = el('div', 'nr-toast', esc(t)); this.root.appendChild(d); setTimeout(() => d.remove(), 1600); },
    btn(label, cls, go) { return '<button class="nr-btn ' + (cls || '') + '" data-go="' + go + '">' + label + '</button>'; },
    showMenu(screen) {
      const H = this.H, S = NR.Save.data, L = S.last, m = this.menu; this.playing(false); this.over.className = 'nr-over';
      const back = '<button class="nr-back" data-go="main">‹ Orqaga</button>'; let h = '';
      if (screen === 'main' || !screen) {
        const st = S.stats;
        h = '<div class="nr-logo"><b>NEON</b><span>RUSH</span><i>arcade combat racing</i></div>' +
          '<div class="nr-sel">' + esc(TR[L.track].name) + ' · ' + esc(CARS[L.car].name) + ' · ' + DIFFS[L.diff][0] + ' · ' + MODES[L.mode][0] + '</div>' +
          '<div class="nr-mm">' + this.btn('▶ PLAY', 'play', 'play') + this.btn('TRACK', '', 'track') + this.btn('CAR', '', 'car') + this.btn('MODE', '', 'mode') + this.btn('DIFFICULTY', '', 'diff') +
          this.btn('SETTINGS', '', 'set') + this.btn('HOW TO PLAY', '', 'how') + this.btn('✕ CHIQISH', 'ghost', 'exit') + '</div>' +
          '<div class="nr-stats"><span>Poygalar <b>' + st.races + '</b></span><span>G‘alaba <b>' + st.wins + '</b></span><span>Podium <b>' + st.podiums + '</b></span><span>Fanlar <b>' + st.fans + ' ✦</b></span><span>Rekord <b>' + st.best + '</b></span></div>';
      } else if (screen === 'track') {
        h = back + '<h2>TRACK</h2><div class="nr-cards">' + Object.keys(TR).map((k) => { const o = NR.Save.trackOpen(k), lap = S.laps[k];
          return '<div class="nr-card trk t-' + k + (L.track === k ? ' on' : '') + (o ? '' : ' lock') + '" data-pick="track" data-v="' + k + '"><b>' + TR[k].name + '</b><span>' + TR[k].sub + '</span>' + (lap ? '<span>🏁 Eng yaxshi aylana: ' + U.fmtLap(lap) + '</span>' : '') + (o ? '' : '<em>🔒 ' + NR.Save.TRACK_UNLOCK[k] + ' ta poygadan keyin</em>') + '</div>'; }).join('') + '</div>';
      } else if (screen === 'car') {
        const bar = (v, mx) => '<i style="width:' + Math.round(U.clamp(v / mx, 0.05, 1) * 100) + '%"></i>';
        h = back + '<h2>CAR</h2><div class="nr-cards">' + Object.keys(CARS).map((k) => { const c = CARS[k], o = NR.Save.carOpen(k);
          return '<div class="nr-card car' + (L.car === k ? ' on' : '') + (o ? '' : ' lock') + '" data-pick="car" data-v="' + k + '" style="--cc:#' + new THREE.Color(c.color).getHexString() + '"><b>' + c.name + '</b><span>' + c.d + '</span>' +
            '<div class="nr-st"><span>Tezlik</span><div>' + bar(c.top - 45, 24) + '</div><span>Tezlanish</span><div>' + bar(c.acc - 15, 13) + '</div><span>Boshqaruv</span><div>' + bar(c.grip - 0.8, 0.36) + '</div><span>Zirh</span><div>' + bar(c.hp, 150) + '</div></div>' +
            (o ? '' : '<em>🔒 ' + NR.Save.CAR_UNLOCK[k] + ' ✦ fan kerak</em>') + '</div>'; }).join('') + '</div>';
      } else if (screen === 'mode') {
        h = back + '<h2>MODE</h2><div class="nr-cards">' + Object.keys(MODES).map((k) => '<div class="nr-card' + (L.mode === k ? ' on' : '') + '" data-pick="mode" data-v="' + k + '"><b>' + MODES[k][0] + '</b><span>' + MODES[k][1] + '</span></div>').join('') + '</div>';
      } else if (screen === 'diff') {
        h = back + '<h2>DIFFICULTY</h2><div class="nr-cards">' + Object.keys(DIFFS).map((k) => '<div class="nr-card' + (L.diff === k ? ' on' : '') + '" data-pick="diff" data-v="' + k + '"><b>' + DIFFS[k][0] + '</b><span>' + DIFFS[k][1] + '</span></div>').join('') + '</div>';
      } else if (screen === 'set') {
        const st = S.settings, sl = (k, a, b, p, l) => '<label class="nr-sl"><span>' + l + ' <b data-v="' + k + '">' + st[k] + '</b></span><input type="range" min="' + a + '" max="' + b + '" step="' + p + '" value="' + st[k] + '" data-set="' + k + '"></label>';
        const chip = (k, v, l) => '<button class="nr-chip' + (st[k] === v ? ' on' : '') + '" data-opt="' + k + '" data-v="' + v + '">' + l + '</button>';
        h = back + '<h2>SETTINGS</h2><div class="nr-form">' + sl('music', 0, 1, 0.05, '🎵 Musiqa') + sl('sfx', 0, 1, 0.05, '🔊 Ovozlar') + sl('btn', 0.7, 1.5, 0.05, '🔘 Tugmalar o‘lchami') +
          '<div class="nr-row"><span>🕹 Rul</span>' + chip('steer', 'buttons', 'Tugmalar') + chip('steer', 'tilt', 'Telefonni qiyshaytirish') + '</div>' + sl('tilt', 0.5, 2, 0.05, '📐 Qiyshaytirish sezgirligi') +
          '<div class="nr-row"><span>🎥 Kamera</span>' + chip('cam', 'far', 'Uzoq') + chip('cam', 'near', 'Yaqin') + '</div>' +
          '<div class="nr-row"><span>🖥 Grafika</span>' + ['auto', 'low', 'medium', 'high'].map((q) => chip('quality', q, q.toUpperCase())).join('') + '</div>' +
          '<div class="nr-row"><span>📈 FPS</span><button class="nr-chip' + (st.fps ? ' on' : '') + '" data-fps="1">' + (st.fps ? 'YOQIQ' : 'O‘CHIQ') + '</button></div></div>';
      } else if (screen === 'how') {
        h = back + '<h2>HOW TO PLAY</h2><div class="nr-how">' +
          '<p><b>📱 Telefon</b>: mashina o‘zi gaz beradi. <b>◀ ▶</b> — rul (yoki sozlamalarda telefonni qiyshaytirish). <b>DRIFT</b> — tormoz; burilishda bosib tursangiz drift qilasiz (fan beradi). <b>FIRE</b> — tanlangan power-up oldinga, <b>↶</b> — orqaga. Power-up belgilarini bossangiz — keyingisiga o‘tadi. <b>🎥</b> — kamera.</p>' +
          '<p><b>⌨ Kompyuter</b>: ←/→ yoki A/D — rul, ↓/S/Shift — drift, Space/W/↑ — oldinga otish, E — orqaga, Q/Tab — almashtirish, C — kamera, Esc/P — pauza.</p>' +
          '<p><b>⚡ Power-up’lar</b> (trassadagi belgilarni yig‘ing, 3 tagacha): ' + Object.keys(PU).map((k) => PU[k].icon + ' <b>' + PU[k].name + '</b> — ' + PU[k].d).join('; ') + '.</p>' +
          '<p><b>✦ Fanlar</b>: zarbalar, raqibni sindirish, drift va quvib o‘tish uchun. Fanlar yangi mashinalarni ochadi; poygalar yangi trassalarni.</p></div>';
      }
      m.innerHTML = '<div class="nr-mwrap">' + h + '</div>'; m.classList.add('on');
      m.querySelectorAll('[data-go]').forEach((b) => (b.onclick = () => { A.init(); A.resume(); const g = b.dataset.go; if (g === 'play') H.play(); else if (g === 'exit') H.exit(); else this.showMenu(g); }));
      m.querySelectorAll('[data-pick]').forEach((c) => (c.onclick = () => {
        const k = c.dataset.pick, v = c.dataset.v;
        if ((k === 'track' && !NR.Save.trackOpen(v)) || (k === 'car' && !NR.Save.carOpen(v))) { this.toast('🔒 Hali ochilmagan'); return; }
        L[k] = v; NR.Save.save(); this.showMenu(screen);
      }));
      m.querySelectorAll('[data-set]').forEach((r) => (r.oninput = () => { const k = r.dataset.set; S.settings[k] = parseFloat(r.value); m.querySelector('[data-v="' + k + '"]').textContent = r.value; NR.Save.save(); this.apply(); A.setVol(S.settings.music, S.settings.sfx); }));
      m.querySelectorAll('[data-opt]').forEach((b) => (b.onclick = () => {
        const k = b.dataset.opt; S.settings[k] = b.dataset.v; NR.Save.save(); this.apply();
        if (k === 'steer' && b.dataset.v === 'tilt' && window.DeviceOrientationEvent && DeviceOrientationEvent.requestPermission) DeviceOrientationEvent.requestPermission().catch(() => {});
        if (k === 'quality') H.quality(); this.showMenu('set');
      }));
      const fb = m.querySelector('[data-fps]'); if (fb) fb.onclick = () => { S.settings.fps = !S.settings.fps; NR.Save.save(); this.apply(); this.showMenu('set'); };
    },
    pause(on, H) {
      if (!on) { this.over.className = 'nr-over'; return; }
      this.over.className = 'nr-over on';
      this.over.innerHTML = '<div class="nr-pbox"><h2>PAUZA</h2>' + this.btn('▶ DAVOM ETISH', 'play', 'resume') + this.btn('↻ QAYTA BOSHLASH', '', 'restart') + this.btn('☰ MENYU', '', 'menu') + this.btn('✕ WEB APP’GA QAYTISH', 'ghost', 'exit') + '</div>';
      this.over.querySelectorAll('[data-go]').forEach((b) => (b.onclick = () => H[b.dataset.go]()));
    },
    results(res, order, H) {
      this.over.className = 'nr-over on res ' + (res.place <= 3 ? 'win' : 'lose');
      const medal = ['🥇', '🥈', '🥉'][res.place - 1] || '';
      const rows = order.map((c, i) => '<div class="nr-rr' + (c.bot ? '' : ' me') + '"><span>' + (i + 1) + '</span><b>' + esc(c.name) + '</b><em>' + (c.finished ? U.fmtLap(c.finishT) : 'DNF') + '</em></div>').join('');
      this.over.innerHTML = '<div class="nr-pbox"><div class="nr-banner">' + medal + ' ' + res.place + '-O‘RIN</div><div class="nr-rsub">' + esc(TR[res.track].name) + ' · ' + esc(CARS[res.car].name) + '</div>' +
        '<div class="nr-rlist">' + rows + '</div>' +
        '<div class="nr-rgrid"><span>Eng yaxshi aylana</span><b>' + U.fmtLap(res.bestLap) + (res.lapRecord ? ' 🏆' : '') + '</b><span>Fanlar</span><b>' + res.fans + ' ✦</b><span>Zarbalar</span><b>' + res.hits + '</b><span>Sinishlar</span><b>' + res.wrecks + '</b></div>' +
        '<div class="nr-rscore">SCORE <b>' + res.score + '</b>' + (res.best ? ' · 🏆 yangi rekord!' : '') + '</div>' + (res.unlocks.length ? '<div class="nr-unl">🔓 Ochildi: ' + res.unlocks.map(esc).join(', ') + '</div>' : '') +
        this.btn('↻ YANA POYGA', 'play', 'restart') + this.btn('☰ MENYU', '', 'menu') + this.btn('✕ WEB APP’GA QAYTISH', 'ghost', 'exit') + '</div>';
      this.over.querySelectorAll('[data-go]').forEach((b) => (b.onclick = () => H[b.dataset.go]()));
    },
    error(text) { this.root.innerHTML = '<div class="nr-err"><b>NEON RUSH</b><p>' + esc(text) + '</p><button class="nr-btn">Orqaga</button></div>'; },
  };
  NR.UI = UI;

  // ══ Game ══
  function Game(opts) {
    this.opts = opts || {}; NR.Save.load();
    const root = (this.root = el('div', 'nr3d')); document.body.appendChild(root);
    this.prevOverflow = document.body.style.overflow; document.body.style.overflow = 'hidden';
    const H = (this.H = { play: () => this.start(), exit: () => this.exit(), menu: () => this.toMenu(), restart: () => this.start(), resume: () => this.resume(), cycle: () => this.cycle(), quality: () => this.setQuality() });
    UI.mount(root, H);
    if (!window.THREE || !hasWebGL()) { UI.error('Bu qurilma yoki brauzer WebGL’ni qo‘llab-quvvatlamaydi.'); root.querySelector('button').onclick = () => this.exit(); return; }
    try { this.engine = new Engine(UI.view); } catch (e) { UI.error('3D grafika ishga tushmadi: ' + e.message); root.querySelector('button').onclick = () => this.exit(); return; }
    this.input = new Input(root, UI.ctl);
    const tg = window.Telegram && window.Telegram.WebApp; try { tg && tg.disableVerticalSwipes && tg.disableVerticalSwipes(); } catch (e) { /* */ }
    this.onVis = () => { if (document.hidden && this.race && this.race.state !== 'done' && !this.paused) this.pause(); };
    document.addEventListener('visibilitychange', this.onVis);
    this.alive = true; this.last = performance.now(); this.fpsT = 0; this.fpsN = 0; this.lowT = 0; this.shakeA = 0; this.camMode = NR.Save.data.settings.cam;
    this.loop = (t) => this.frame(t); this.raf = requestAnimationFrame(this.loop);
    UI.showMenu('main');
  }
  const GP = Game.prototype;
  GP.setQuality = function () { const E = this.engine; if (!E) return; const q = NR.Save.data.settings.quality; E.auto = q === 'auto'; E.quality = E.auto ? (weakDevice() ? 'low' : 'medium') : q; E.prScale = 1; E.applyQuality(); E.resize(); };
  GP.start = function () {
    A.init(); A.resume(); this.cleanup();
    const S = NR.Save.data, L = S.last; if (!NR.Save.trackOpen(L.track)) L.track = 'harbor'; if (!NR.Save.carOpen(L.car)) L.car = 'viper';
    try {
      this.scene = new THREE.Scene(); this.track = new NR.World.Track(L.track); this.track.build(this.scene, this.engine.quality);
      this.race = new NR.Race.Race({ scene: this.scene, quality: this.engine.quality, diff: L.diff, mode: L.mode, track: this.track, car: L.car, cars: this.engine.quality === 'low' ? 6 : 8,
        playerName: this.opts.playerName || 'Siz', onEvent: (k, c, a, b) => this.onEvent(k, c, a, b), shake: (v) => (this.shakeA = Math.max(this.shakeA, v)) });
    } catch (e) { console.error(e); UI.toast('⚠️ Poyga ishga tushmadi: ' + e.message); this.cleanup(); UI.showMenu('main'); return; }
    UI.mapBase = null; UI.mm = null; UI.cache = {}; UI.e.feed.innerHTML = '';
    this.paused = false; UI.pause(false); this.input.release(); UI.playing(true); this.camInit = true;
    A.engineStart(); A.music(true); UI.big('3', 0);
  };
  GP.cleanup = function () {
    if (this.race) { this.race.dispose(); this.race = null; }
    if (this.track) { this.track.dispose(); this.track = null; }
    if (this.scene) { this.scene.traverse((o) => { if (o.geometry && o.geometry.dispose && !o.isInstancedMesh) { /* trassa/poyga o'zi tozalaydi */ } }); this.scene = null; }
    A.engineStop(); A.music(false);
  };
  GP.onEvent = function (k, c, a, b) {
    const R = this.race, pl = R && R.player;
    if (k === 'count') { UI.big(String(a), 0.9); A.beep(false); }
    else if (k === 'go') { UI.big('GO!', 0.8, 'go'); A.beep(true); }
    else if (k === 'lap') { A.lap(); const left = R.laps - c.lap; UI.big(left === 1 ? 'OXIRGI AYLANA' : 'LAP ' + (c.lap + 1), 1.4); UI.feed('⏱ ' + U.fmtLap(a), 'lap'); }
    else if (k === 'pickup') UI.feed(PU[a].icon + ' ' + PU[a].name);
    else if (k === 'fans') UI.feed('✦ ' + esc(a), 'fan');
    else if (k === 'hit') { if (c === pl) { UI.damage(); UI.feed('💢 ' + (b ? PU[b] ? PU[b].name : b : '') + (a ? ' — ' + esc(a.name) : ''), 'bad'); } else if (a === pl) UI.feed('🎯 ' + esc(c.name) + ' urildi!', 'good'); }
    else if (k === 'blocked') { if (c === pl) UI.feed('🛡 Hujum qaytarildi', 'good'); }
    else if (k === 'wreck') { if (c === pl) { A.wreck(); UI.big('SINDINGIZ!', 1.5, 'bad'); this.shakeA = 1; } else if (a === pl) { UI.feed('💥 ' + esc(c.name) + ' sindi! +150 ✦', 'good'); } if (c === pl || a === pl) A.hit(true); }
    else if (k === 'finish') { A.finish(c.place <= 3); UI.big(c.place + '-O‘RIN!', 3, c.place <= 3 ? 'go' : ''); }
    else if (k === 'reset') UI.feed('↺ Trassaga qaytarildi');
    else if (k === 'done') this.finish(a);
  };
  GP.finish = function (order) {
    const R = this.race, pl = R.player, n = R.cars.length, S = NR.Save.data, L = S.last;
    const mult = { easy: 0.7, normal: 1, hard: 1.4 }[R.diff] || 1, place = pl.place || n;
    const placeBonus = { 1: 500, 2: 300, 3: 200 }[place] || 50;
    pl.fans += placeBonus;
    const res = { track: L.track, car: L.car, diff: R.diff, mode: R.mode, place, cars: n, laps: R.laps, bestLap: pl.bestLap, fans: pl.fans, hits: pl.hits, wrecks: pl.wrecks, finished: pl.finished };
    res.score = Math.round(((n - place + 1) * 250 + pl.fans + pl.hits * 30) * mult);
    const before = { c: Object.keys(CARS).filter((k) => NR.Save.carOpen(k)), t: Object.keys(TR).filter((k) => NR.Save.trackOpen(k)) };
    res.best = res.score > S.stats.best; NR.Save.record(res);
    res.unlocks = Object.keys(CARS).filter((k) => NR.Save.carOpen(k) && before.c.indexOf(k) < 0).map((k) => CARS[k].name).concat(Object.keys(TR).filter((k) => NR.Save.trackOpen(k) && before.t.indexOf(k) < 0).map((k) => TR[k].name));
    A.engineStop(); A.music(false); this.input.release(); UI.big('', 0.01);
    UI.results(res, order, this.H);
    try { this.opts.onResult && this.opts.onResult(res); } catch (e) { /* */ }
  };
  GP.cycle = function () { const pl = this.race && this.race.player; if (!pl || pl.items.length < 2) return; pl.sel = (pl.sel + 1) % pl.items.length; A.cycle(); };
  GP.pause = function () { if (!this.race || this.race.state === 'done') return; this.paused = true; this.input.release(); UI.pause(true, this.H); A.music(false); A.engineSet(0, 0, false); };
  GP.resume = function () { if (!this.race) return; this.paused = false; UI.pause(false); this.last = performance.now(); A.music(true); };
  GP.toMenu = function () { this.cleanup(); this.paused = false; UI.pause(false); UI.showMenu('main'); };
  GP.updateCamera = function (dt) {
    const pl = this.race.player, cam = this.engine.camera, far = this.camMode !== 'near';
    const dist = far ? 8.2 : 5.6, hgt = far ? 3.1 : 2.2, fwd = Math.max(0, pl.v);
    const back = this.camInit ? 1 : Math.min(1, dt * 7.5);
    this.camYaw = this.camInit ? pl.h : this.camYaw + U.angDiff(this.camYaw, pl.h) * Math.min(1, dt * (pl.stun > 0 || pl.wreck > 0 ? 1.5 : 5.5));
    if (this.race.state === 'count') { const k = U.clamp(this.race.count / 3.6, 0, 1); this.camYaw = pl.h + k * 2.4; }
    const tx = pl.x - Math.sin(this.camYaw) * dist, tz = pl.z - Math.cos(this.camYaw) * dist, ty = pl.y + hgt + pl.air * 0.5;
    if (this.camInit) cam.position.set(tx, ty, tz); else { cam.position.x += (tx - cam.position.x) * back; cam.position.y += (ty - cam.position.y) * back; cam.position.z += (tz - cam.position.z) * back; }
    this.camInit = false;
    const sh = this.shakeA; this.shakeA = Math.max(0, this.shakeA - dt * 1.8);
    cam.lookAt(pl.x + Math.sin(this.camYaw) * 6, pl.y + 1.1 + pl.air * 0.5, pl.z + Math.cos(this.camYaw) * 6);
    if (sh > 0) { cam.position.x += (Math.random() - 0.5) * sh * 0.6; cam.position.y += (Math.random() - 0.5) * sh * 0.4; }
    const fov = 66 + Math.min(16, fwd * 0.2) + (pl.nitro > 0 ? 9 : 0);
    if (Math.abs(cam.fov - fov) > 0.05) { cam.fov = U.lerp(cam.fov, fov, Math.min(1, dt * 4)); cam.updateProjectionMatrix(); }
    if (this.track.sky) this.track.sky.position.copy(cam.position);
  };
  GP.frame = function (t) {
    if (!this.alive) return; this.raf = requestAnimationFrame(this.loop);
    const dt = Math.min(0.05, Math.max(0, (t - this.last) / 1000)); this.last = t;
    const R = this.race; if (!R || document.hidden) return;
    const s = this.input.s;
    if (s.pause) { s.pause = false; if (R.state !== 'done') this.paused ? this.resume() : this.pause(); }
    if (this.paused) return;
    if (s.cam) { s.cam = false; this.camMode = this.camMode === 'far' ? 'near' : 'far'; NR.Save.data.settings.cam = this.camMode; NR.Save.save(); }
    if (s.cycle) { s.cycle = false; this.cycle(); }
    if (R.state === 'race' && !R.player.finished) { if (s.fire) R.use(R.player, false); if (s.back) R.use(R.player, true); }
    s.fire = s.back = false;
    const pin = { steer: this.input.steer(), throttle: 1, brake: this.input.brake() };
    // fizika qadami: katta dt bo'lsa ikkiga bo'linadi (barqarorlik)
    const steps = dt > 0.034 ? 2 : 1; for (let i = 0; i < steps; i++) R.update(dt / steps, pin);
    if (!this.race) return;
    this.updateCamera(dt);
    if (R.state === 'race' && !R.player.finished) { const w = (R.player.wrongT || 0) > 0.8; if (w !== this.wrongShown) { this.wrongShown = w; if (w) UI.big('⚠ TESKARI YO‘NALISH', 0, 'bad'); else UI.big('', 0.01); } }
    if (R.state !== 'done') { UI.hudUpdate(R); const pl = R.player; A.engineSet(U.clamp(Math.abs(pl.v) / pl.def.top, 0, 1.3), pin.throttle * (pl.nitro > 0 ? 1.5 : 1), pl.wreck <= 0); }
    this.engine.renderer.render(this.scene, this.engine.camera);
    this.fpsT += dt; this.fpsN++;
    if (this.fpsT >= 1) {
      const fps = Math.round(this.fpsN / this.fpsT); this.fpsT = 0; this.fpsN = 0; UI.fps(fps); const E = this.engine;
      if (E.auto) {
        if (fps < 28) this.lowT++; else this.lowT = 0;
        if (this.lowT >= 2 && E.prScale > 0.5) { E.prScale = Math.max(0.5, E.prScale - 0.15); E.applyQuality(); E.resize(); this.lowT = 0; }
        else if (fps > 57 && E.prScale < 1) { E.prScale = Math.min(1, E.prScale + 0.05); E.applyQuality(); E.resize(); }
      }
    }
  };
  GP.exit = function () {
    this.alive = false; cancelAnimationFrame(this.raf); this.cleanup();
    if (this.input) this.input.dispose(UI.ctl, this.root);
    if (this.engine) this.engine.dispose();
    NR.Race.disposeShared(); A.dispose();
    document.removeEventListener('visibilitychange', this.onVis);
    const tg = window.Telegram && window.Telegram.WebApp; try { tg && tg.enableVerticalSwipes && tg.enableVerticalSwipes(); } catch (e) { /* */ }
    document.body.style.overflow = this.prevOverflow || ''; this.root.remove(); NR.current = null;
    try { this.opts.onExit && this.opts.onExit(); } catch (e) { /* */ }
  };

  NR.launch = function (opts) { if (NR.current) NR.current.exit(); NR.current = new Game(opts); return NR.current; };
  NR._internal = { Game, Engine, Input };
})();
