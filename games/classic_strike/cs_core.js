/* CLASSIC STRIKE — core: utils, SaveSystem, AudioManager.
   Barcha tovushlar Web Audio orqali sintez qilinadi (tashqi fayl yo'q, original). */
(function () {
  'use strict';
  const CS3D = (window.CS3D = window.CS3D || {});
  CS3D.VERSION = '1.0.0';

  // ── Utils ──
  const U = (CS3D.U = {
    clamp: (v, a, b) => (v < a ? a : v > b ? b : v),
    lerp: (a, b, t) => a + (b - a) * t,
    rand: (a, b) => a + Math.random() * (b - a),
    pick: (arr) => arr[(Math.random() * arr.length) | 0],
    angDiff(a, b) {
      let d = (b - a) % (Math.PI * 2);
      if (d > Math.PI) d -= Math.PI * 2;
      if (d < -Math.PI) d += Math.PI * 2;
      return d;
    },
    dist2: (ax, az, bx, bz) => Math.hypot(ax - bx, az - bz),
    fmtTime(s) {
      s = Math.max(0, Math.ceil(s));
      return ((s / 60) | 0) + ':' + String(s % 60).padStart(2, '0');
    },
  });

  // ── SaveSystem (localStorage — faqat qulaylik uchun, ishonchli ma'lumot serverda) ──
  const KEY = 'classic_strike_v1';
  const DEF = {
    settings: { music: 0.35, sfx: 0.8, sens: 1, btn: 1, quality: 'auto', fps: false },
    stats: { games: 0, wins: 0, losses: 0, kills: 0, deaths: 0, heads: 0, best: 0, survWave: 0, survTime: 0 },
    last: { mode: 'tdm', map: 'desert', diff: 'normal', primary: 'rifle', side: 'attack' },
  };
  function merge(base, over) {
    const out = {};
    for (const k of Object.keys(base)) {
      const b = base[k], o = over && over[k];
      out[k] = b && typeof b === 'object' && !Array.isArray(b) ? merge(b, o || {}) : o !== undefined && typeof o === typeof b ? o : b;
    }
    return out;
  }
  CS3D.Save = {
    data: null,
    load() {
      let d = null;
      try { d = JSON.parse(localStorage.getItem(KEY) || 'null'); } catch (e) { d = null; }
      this.data = merge(DEF, d || {});
      return this.data;
    },
    save() { try { localStorage.setItem(KEY, JSON.stringify(this.data)); } catch (e) { /* xususiy rejim */ } },
    // Qurollar va xaritalar progress bilan ochiladi
    WEAPON_UNLOCK: { rifle: 0, smg: 0, shotgun: 0, deagle: 10, sniper: 30 },
    MAP_UNLOCK: { desert: 0, urban: 1, warehouse: 2 },   // o'ynalgan o'yinlar soni
    weaponOpen(id) { return (this.data.stats.kills | 0) >= (this.WEAPON_UNLOCK[id] || 0); },
    mapOpen(id) { return (this.data.stats.games | 0) >= (this.MAP_UNLOCK[id] || 0); },
    record(res) {
      const s = this.data.stats;
      s.games++; res.win ? s.wins++ : s.losses++;
      s.kills += res.kills; s.deaths += res.deaths; s.heads += res.heads;
      s.best = Math.max(s.best, res.score);
      if (res.mode === 'survival') { s.survWave = Math.max(s.survWave, res.wave || 0); s.survTime = Math.max(s.survTime, Math.round(res.time)); }
      this.save();
    },
  };

  // ── AudioManager ──
  const A = (CS3D.Audio = {
    ctx: null, master: null, sfxG: null, musG: null, noise: null, voices: 0, musicTimer: null, musicOn: false,
    init() {
      if (this.ctx) return true;
      const AC = window.AudioContext || window.webkitAudioContext;
      if (!AC) return false;
      try { this.ctx = new AC(); } catch (e) { return false; }
      const c = this.ctx;
      this.master = c.createGain(); this.master.connect(c.destination);
      const comp = c.createDynamicsCompressor(); comp.threshold.value = -14; comp.ratio.value = 4; comp.connect(this.master);
      this.sfxG = c.createGain(); this.sfxG.connect(comp);
      this.musG = c.createGain(); this.musG.connect(comp);
      const len = c.sampleRate | 0, buf = c.createBuffer(1, len, c.sampleRate), d = buf.getChannelData(0);
      for (let i = 0; i < len; i++) d[i] = Math.random() * 2 - 1;
      this.noise = buf;
      this.setVol(CS3D.Save.data.settings.music, CS3D.Save.data.settings.sfx);
      return true;
    },
    resume() { if (this.ctx && this.ctx.state === 'suspended') this.ctx.resume().catch(() => {}); },
    setVol(m, s) { if (!this.ctx) return; this.musG.gain.value = m * 0.5; this.sfxG.gain.value = s; },
    _voice(dur) {
      if (!this.ctx || this.voices > 20) return false;
      this.voices++; setTimeout(() => { this.voices--; }, dur * 1000 + 60);
      return true;
    },
    _noise(t, dur, freq, q, vol, type, dest) {
      const c = this.ctx, src = c.createBufferSource(), f = c.createBiquadFilter(), g = c.createGain();
      src.buffer = this.noise; src.loop = true;
      f.type = type || 'lowpass'; f.frequency.setValueAtTime(freq, t); f.Q.value = q || 0.7;
      g.gain.setValueAtTime(vol, t); g.gain.exponentialRampToValueAtTime(0.0001, t + dur);
      src.connect(f); f.connect(g); g.connect(dest || this.sfxG);
      src.start(t, Math.random() * 0.5); src.stop(t + dur + 0.02);
      return f;
    },
    _tone(t, f0, f1, dur, vol, type, dest) {
      const c = this.ctx, o = c.createOscillator(), g = c.createGain();
      o.type = type || 'square'; o.frequency.setValueAtTime(f0, t); o.frequency.exponentialRampToValueAtTime(Math.max(20, f1), t + dur);
      g.gain.setValueAtTime(vol, t); g.gain.exponentialRampToValueAtTime(0.0001, t + dur);
      o.connect(g); g.connect(dest || this.sfxG); o.start(t); o.stop(t + dur + 0.02);
    },
    // Qurol ovozlari: masofa bilan pasayadi va bo'g'iladi
    SHOT: {
      pistol: [2600, 0.16, 0.55, 140], deagle: [1500, 0.32, 0.9, 90], smg: [3200, 0.09, 0.4, 170],
      rifle: [2200, 0.15, 0.6, 110], sniper: [1100, 0.55, 1.0, 60], shotgun: [1300, 0.36, 0.95, 70],
    },
    shot(kind, dist) {
      const p = this.SHOT[kind] || this.SHOT.rifle;
      if (!this._voice(p[1])) return;
      const t = this.ctx.currentTime, k = 1 / (1 + (dist || 0) * 0.07), lp = p[0] * (dist ? Math.max(0.25, 1 - dist / 60) : 1);
      this._noise(t, p[1], lp, 0.9, p[2] * k);
      this._tone(t, p[3] * 2.2, p[3] * 0.6, p[1] * 0.7, 0.35 * p[2] * k, 'triangle');
    },
    knife() { if (!this._voice(0.15)) return; const t = this.ctx.currentTime; this._noise(t, 0.14, 5000, 2, 0.25, 'bandpass'); },
    reload(stage) {
      if (!this._voice(0.1)) return;
      const t = this.ctx.currentTime;
      this._noise(t, 0.05, stage ? 2400 : 1400, 6, 0.35, 'bandpass');
      this._tone(t, stage ? 900 : 500, stage ? 700 : 380, 0.05, 0.12, 'square');
    },
    dry() { if (!this._voice(0.05)) return; this._tone(this.ctx.currentTime, 1800, 1500, 0.03, 0.12, 'square'); },
    impact(dist) { if (!this._voice(0.08)) return; const k = 1 / (1 + (dist || 0) * 0.12); this._noise(this.ctx.currentTime, 0.06, 3500, 3, 0.25 * k, 'bandpass'); },
    flesh() { if (!this._voice(0.1)) return; this._noise(this.ctx.currentTime, 0.09, 700, 1.5, 0.35); },
    hit() { if (!this._voice(0.06)) return; this._tone(this.ctx.currentTime, 2400, 2200, 0.05, 0.12, 'sine'); },
    hurt() { if (!this._voice(0.25)) return; const t = this.ctx.currentTime; this._noise(t, 0.2, 500, 1, 0.5); this._tone(t, 160, 80, 0.2, 0.25, 'sawtooth'); },
    step(run) { if (!this._voice(0.07)) return; this._noise(this.ctx.currentTime, 0.06, run ? 600 : 420, 1.2, run ? 0.22 : 0.13); },
    jump() { if (!this._voice(0.1)) return; this._noise(this.ctx.currentTime, 0.1, 380, 1, 0.2); },
    spotted() { if (!this._voice(0.3)) return; const t = this.ctx.currentTime; this._tone(t, 1320, 1320, 0.07, 0.08, 'square'); this._tone(t + 0.1, 990, 990, 0.09, 0.08, 'square'); },
    beep(hi) { if (!this._voice(0.08)) return; this._tone(this.ctx.currentTime, hi ? 2200 : 1700, hi ? 2200 : 1700, 0.06, 0.1, 'square'); },
    seq(notes, gap, dur, vol, type) {
      if (!this.ctx) return;
      const t = this.ctx.currentTime;
      notes.forEach((f, i) => this._tone(t + i * gap, f, f * 0.98, dur, vol || 0.12, type || 'triangle'));
    },
    roundStart() { this.seq([523, 659, 784], 0.11, 0.12, 0.12); },
    roundEnd(win) { win ? this.seq([784, 988, 1175], 0.12, 0.18, 0.13) : this.seq([440, 370, 294], 0.14, 0.2, 0.13); },
    victory() { this.seq([523, 659, 784, 1046, 784, 1046, 1318], 0.13, 0.25, 0.14); },
    defeat() { this.seq([392, 349, 311, 262, 196], 0.18, 0.35, 0.14, 'sawtooth'); },
    explode() { if (!this._voice(1.4)) return; const t = this.ctx.currentTime; this._noise(t, 1.3, 400, 0.6, 1.2); this._tone(t, 90, 30, 1.2, 0.6, 'sawtooth'); },
    // Fon musiqasi: sokin "taktik" pad + bas puls (lookahead scheduler)
    music(on) {
      if (!this.ctx) return;
      if (!on) { this.musicOn = false; clearInterval(this.musicTimer); this.musicTimer = null; return; }
      if (this.musicOn) return;
      this.musicOn = true;
      const chords = [[110, 164.8, 220], [98, 146.8, 196], [87.3, 130.8, 174.6], [103.8, 155.6, 207.7]];
      let next = this.ctx.currentTime + 0.1, step = 0;
      const beat = 0.5;
      const sched = () => {
        if (!this.ctx) return;
        while (next < this.ctx.currentTime + 0.4) {
          const ch = chords[((step / 8) | 0) % chords.length];
          if (step % 8 === 0) ch.forEach((f) => this._pad(next, f, beat * 8));
          if (step % 2 === 0) this._tone(next, ch[0] / 2, ch[0] / 2.2, 0.25, 0.22, 'sine', this.musG);
          if (step % 4 === 3) this._noise(next, 0.04, 7000, 1, 0.05, 'highpass', this.musG);
          next += beat; step++;
        }
      };
      sched(); this.musicTimer = setInterval(sched, 120);
    },
    _pad(t, f, dur) {
      const c = this.ctx, g = c.createGain(), lp = c.createBiquadFilter();
      lp.type = 'lowpass'; lp.frequency.value = 900;
      g.gain.setValueAtTime(0.0001, t); g.gain.linearRampToValueAtTime(0.06, t + 0.8); g.gain.linearRampToValueAtTime(0.0001, t + dur);
      for (const d of [-6, 6]) { const o = c.createOscillator(); o.type = 'sawtooth'; o.frequency.value = f; o.detune.value = d; o.connect(lp); o.start(t); o.stop(t + dur + 0.05); }
      lp.connect(g); g.connect(this.musG);
    },
    dispose() {
      this.music(false);
      if (this.ctx) { try { this.ctx.close(); } catch (e) { /* allaqachon yopilgan */ } }
      this.ctx = null; this.voices = 0;
    },
  });
  void A;
})();
