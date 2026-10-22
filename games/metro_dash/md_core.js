/* METRO DASH — core: utils, SaveSystem (localStorage — faqat qulaylik), AudioManager (Web Audio sintez, tashqi fayl yo'q).
   Original endless-runner: nom, personaj tanlovi, tovushlar o'zimizniki; 3D modellar — Kenney (CC0). */
(function () {
  'use strict';
  const MD = (window.MDASH = window.MDASH || {});
  MD.VERSION = '1.0.0';

  const U = (MD.U = {
    clamp: (v, a, b) => (v < a ? a : v > b ? b : v),
    lerp: (a, b, t) => a + (b - a) * t,
    rand: (a, b) => a + Math.random() * (b - a),
    irand: (a, b) => (a + Math.random() * (b - a + 1)) | 0,
    pick: (arr) => arr[(Math.random() * arr.length) | 0],
    fmt: (n) => String(Math.floor(n)).replace(/\B(?=(\d{3})+(?!\d))/g, ' '),
  });

  // Personajlar (Kenney Mini Characters, CC0) — narxi tangalarda
  MD.SKINS = [
    { id: 'mb', name: 'Bek', cost: 0 }, { id: 'fc', name: 'Lola', cost: 0 }, { id: 'ma', name: 'Timur', cost: 500 }, { id: 'fa', name: 'Nilu', cost: 500 },
    { id: 'mc', name: 'Rustam', cost: 1200 }, { id: 'fb', name: 'Zara', cost: 1200 }, { id: 'me', name: 'Jasur', cost: 2500 }, { id: 'fd', name: 'Mira', cost: 2500 },
    { id: 'mf', name: 'Sardor', cost: 4000 }, { id: 'fe', name: 'Dina', cost: 4000 }, { id: 'md', name: 'Boss', cost: 7000 }, { id: 'ff', name: 'Malika', cost: 7000 },
  ];
  MD.BOARD_COST = 300;     // 1 ta uchar taxta narxi

  const KEY = 'metro_dash_v1';
  const DEF = {
    settings: { music: 0.4, sfx: 0.85, quality: 'auto', fps: false },
    stats: { runs: 0, best: 0, bestDist: 0, coins: 0, totalCoins: 0, boards: 3 },
    owned: ['mb', 'fc'], skin: 'mb',
  };
  function merge(base, over) {
    const out = {};
    for (const k of Object.keys(base)) {
      const b = base[k], o = over && over[k];
      if (Array.isArray(b)) out[k] = Array.isArray(o) ? o.filter((x) => typeof x === 'string').slice(0, 40) : b.slice();
      else if (b && typeof b === 'object') out[k] = merge(b, o || {});
      else out[k] = o !== undefined && typeof o === typeof b ? o : b;
    }
    return out;
  }
  MD.Save = {
    data: null,
    load() {
      let d = null; try { d = JSON.parse(localStorage.getItem(KEY) || 'null'); } catch (e) { d = null; }
      this.data = merge(DEF, d || {}); if (!this.data.owned.includes(this.data.skin)) this.data.skin = 'mb';
      return this.data;
    },
    save() { try { localStorage.setItem(KEY, JSON.stringify(this.data)); } catch (e) { /* xususiy rejim */ } },
    buySkin(id) {
      const s = MD.SKINS.find((x) => x.id === id), st = this.data.stats; if (!s || this.data.owned.includes(id)) return 'owned';
      if (st.coins < s.cost) return 'coins'; st.coins -= s.cost; this.data.owned.push(id); this.save(); return 'ok';
    },
    buyBoard() { const st = this.data.stats; if (st.coins < MD.BOARD_COST) return 'coins'; st.coins -= MD.BOARD_COST; st.boards++; this.save(); return 'ok'; },
    record(res) {
      const st = this.data.stats; st.runs++; st.coins += res.coins; st.totalCoins += res.coins;
      res.best = res.score > st.best; st.best = Math.max(st.best, res.score); st.bestDist = Math.max(st.bestDist, Math.floor(res.distance)); this.save();
    },
  };

  // ── AudioManager ──
  const A = (MD.Audio = {
    ctx: null, sfxG: null, musG: null, noise: null, voices: 0, musicOn: false, musicTimer: null, coinStep: 0, coinT: 0, jet: null,
    init() {
      if (this.ctx) return; const AC = window.AudioContext || window.webkitAudioContext; if (!AC) return;
      try { this.ctx = new AC(); } catch (e) { return; }
      const c = this.ctx, comp = c.createDynamicsCompressor(); comp.connect(c.destination);
      this.sfxG = c.createGain(); this.sfxG.connect(comp); this.musG = c.createGain(); this.musG.connect(comp);
      const len = c.sampleRate, buf = c.createBuffer(1, len, c.sampleRate), d = buf.getChannelData(0); for (let i = 0; i < len; i++) d[i] = Math.random() * 2 - 1;
      this.noise = buf; this.setVol(MD.Save.data.settings.music, MD.Save.data.settings.sfx);
    },
    resume() { if (this.ctx && this.ctx.state === 'suspended') this.ctx.resume().catch(() => {}); },
    setVol(m, s) { if (!this.ctx) return; this.musG.gain.value = m * 0.45; this.sfxG.gain.value = s; },
    tone(f, dur, vol, type, slide, delay) {
      if (!this.ctx || this.voices > 24) return; const c = this.ctx, t = c.currentTime + (delay || 0);
      const o = c.createOscillator(), g = c.createGain(); o.type = type || 'sine'; o.frequency.setValueAtTime(f, t);
      if (slide) o.frequency.exponentialRampToValueAtTime(Math.max(20, f * slide), t + dur);
      g.gain.setValueAtTime(0.0001, t); g.gain.exponentialRampToValueAtTime(vol, t + 0.006); g.gain.exponentialRampToValueAtTime(0.0001, t + dur);
      o.connect(g); g.connect(this.sfxG); o.start(t); o.stop(t + dur + 0.03); this.voices++; o.onended = () => this.voices--;
    },
    burst(dur, vol, freq, q, type, delay, dest) {
      if (!this.ctx || this.voices > 24) return; const c = this.ctx, t = c.currentTime + (delay || 0);
      const s = c.createBufferSource(); s.buffer = this.noise; const f = c.createBiquadFilter(); f.type = type || 'bandpass'; f.frequency.value = freq; f.Q.value = q || 1;
      const g = c.createGain(); g.gain.setValueAtTime(0.0001, t); g.gain.exponentialRampToValueAtTime(vol, t + 0.005); g.gain.exponentialRampToValueAtTime(0.0001, t + dur);
      s.connect(f); f.connect(g); g.connect(dest || this.sfxG); s.start(t, Math.random() * 0.5); s.stop(t + dur + 0.03); this.voices++; s.onended = () => this.voices--;
    },
    coin() {    // ketma-ket tangalar — ohang ko'tariladi
      const now = performance.now(); this.coinStep = now - this.coinT < 350 ? Math.min(this.coinStep + 1, 10) : 0; this.coinT = now;
      const f = 1046 * Math.pow(2, (this.coinStep % 6) / 12); this.tone(f, 0.09, 0.08, 'square'); this.tone(f * 1.5, 0.12, 0.05, 'triangle', 1, 0.04);
    },
    jump() { this.tone(300, 0.18, 0.1, 'triangle', 2.2); this.burst(0.12, 0.05, 1500, 1); },
    roll() { this.burst(0.25, 0.12, 600, 0.8, 'lowpass'); },
    swipe() { this.burst(0.09, 0.07, 2600, 1.5); },
    land() { this.burst(0.08, 0.08, 300, 0.8, 'lowpass'); },
    stumble() { this.tone(180, 0.25, 0.15, 'square', 0.5); this.burst(0.2, 0.15, 800, 1); },
    crash() { this.burst(0.7, 0.4, 200, 0.6, 'lowpass'); this.tone(90, 0.6, 0.25, 'sawtooth', 0.4); this.burst(0.35, 0.2, 3000, 1, 'highpass', 0.05); },
    power() { [523, 659, 784, 1046].forEach((f, i) => this.tone(f, 0.14, 0.08, 'triangle', 1, i * 0.06)); },
    board() { this.tone(200, 0.4, 0.1, 'sawtooth', 3); this.burst(0.4, 0.1, 1200, 0.7); },
    beep() { this.tone(880, 0.1, 0.08, 'square'); },
    over() { [392, 330, 262, 196].forEach((f, i) => this.tone(f, 0.25, 0.12, 'triangle', 1, i * 0.14)); },
    jetStart() {
      if (!this.ctx || this.jet) return; const c = this.ctx, s = c.createBufferSource(); s.buffer = this.noise; s.loop = true;
      const f = c.createBiquadFilter(); f.type = 'lowpass'; f.frequency.value = 700; const g = c.createGain(); g.gain.value = 0.12;
      s.connect(f); f.connect(g); g.connect(this.sfxG); s.start(); this.jet = { s, g };
    },
    jetStop() { if (!this.jet) return; try { this.jet.s.stop(); } catch (e) { /* */ } this.jet = null; },
    // Fon musiqasi — quvnoq hip-hop/chiptune ritm (lookahead scheduler)
    music(on) {
      if (!this.ctx) return;
      if (!on) { this.musicOn = false; clearInterval(this.musicTimer); this.musicTimer = null; return; }
      if (this.musicOn) return; this.musicOn = true;
      const c = this.ctx, st = 60 / 100 / 4; let step = 0, next = c.currentTime + 0.08;
      const bass = [55, 55, 0, 55, 65.4, 0, 49, 0, 55, 55, 0, 73.4, 65.4, 0, 49, 0], lead = [0, 659, 0, 784, 0, 659, 587, 0, 0, 523, 0, 587, 659, 0, 0, 0];
      const note = (f, t, d, v, type, cut) => {
        const o = c.createOscillator(), g = c.createGain(), fl = c.createBiquadFilter(); o.type = type; o.frequency.value = f; fl.type = 'lowpass'; fl.frequency.value = cut;
        g.gain.setValueAtTime(0.0001, t); g.gain.exponentialRampToValueAtTime(v, t + 0.008); g.gain.exponentialRampToValueAtTime(0.0001, t + d);
        o.connect(fl); fl.connect(g); g.connect(this.musG); o.start(t); o.stop(t + d + 0.02);
      };
      const tick = () => {
        while (next < c.currentTime + 0.2) {
          const s = step % 16, bar = ((step / 16) | 0) % 4;
          if (s % 8 === 0 || s === 11) note(60, next, 0.16, 0.5, 'sine', 300);               // kik
          if (s % 8 === 4) this.burst(0.14, 0.1, 1800, 0.7, 'bandpass', next - c.currentTime, this.musG);   // snare
          if (s % 2 === 1) this.burst(0.03, 0.035, 9000, 1, 'highpass', next - c.currentTime, this.musG);   // hat
          if (bass[s]) note(bass[s] * (bar === 3 ? 1.19 : 1), next, st * 1.6, 0.18, 'square', 600);
          if (lead[s] && bar % 2 === 1) note(lead[s], next, st * 1.4, 0.045, 'square', 3000);
          next += st; step++;
        }
      };
      tick(); this.musicTimer = setInterval(tick, 40);
    },
    dispose() { this.music(false); this.jetStop(); },
  });
  void A; void U;
})();
