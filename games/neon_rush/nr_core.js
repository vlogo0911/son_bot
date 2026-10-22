/* NEON RUSH — core: utils, SaveSystem (localStorage), AudioManager (Web Audio sintez, tashqi fayl yo'q).
   Original arkada poyga: nomlar, mashinalar, trassalar va tovushlar o'zimizniki. */
(function () {
  'use strict';
  const NR = (window.NR3D = window.NR3D || {});
  NR.VERSION = '1.0.0';

  const U = (NR.U = {
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
    fmtLap(s) {
      if (!isFinite(s) || s <= 0) return '—';
      const m = (s / 60) | 0, r = s - m * 60;
      return m + ':' + (r < 10 ? '0' : '') + r.toFixed(2);
    },
    ord(n) { return n + (n === 1 ? '-o‘rin' : '-o‘rin'); },
  });

  // ── SaveSystem: faqat qulaylik (sozlamalar/ochilishlar). Reyting serverda saqlanadi. ──
  const KEY = 'neon_rush_v1';
  const DEF = {
    settings: { music: 0.35, sfx: 0.8, steer: 'buttons', tilt: 1, btn: 1, quality: 'auto', fps: false, cam: 'far' },
    stats: { races: 0, wins: 0, podiums: 0, fans: 0, best: 0, wrecks: 0, hits: 0 },
    laps: { harbor: 0, canyon: 0, downtown: 0 },
    last: { track: 'harbor', car: 'viper', diff: 'normal', mode: 'race' },
  };
  function merge(base, over) {
    const out = {};
    for (const k of Object.keys(base)) {
      const b = base[k], o = over && over[k];
      out[k] = b && typeof b === 'object' && !Array.isArray(b) ? merge(b, o || {}) : o !== undefined && typeof o === typeof b ? o : b;
    }
    return out;
  }
  NR.Save = {
    data: null,
    CAR_UNLOCK: { viper: 0, hornet: 0, bulldog: 2500, phantom: 7000 },   // to'plangan fanlar
    TRACK_UNLOCK: { harbor: 0, canyon: 1, downtown: 2 },                 // yakunlangan poygalar
    load() {
      let d = null;
      try { d = JSON.parse(localStorage.getItem(KEY) || 'null'); } catch (e) { d = null; }
      this.data = merge(DEF, d || {});
      return this.data;
    },
    save() { try { localStorage.setItem(KEY, JSON.stringify(this.data)); } catch (e) { /* xususiy rejim */ } },
    carOpen(id) { return (this.data.stats.fans | 0) >= (this.CAR_UNLOCK[id] || 0); },
    trackOpen(id) { return (this.data.stats.races | 0) >= (this.TRACK_UNLOCK[id] || 0); },
    record(res) {
      const s = this.data.stats;
      s.races++; if (res.place === 1) s.wins++; if (res.place <= 3) s.podiums++;
      s.fans += res.fans; s.best = Math.max(s.best, res.score); s.wrecks += res.wrecks; s.hits += res.hits;
      if (res.bestLap > 0 && (!this.data.laps[res.track] || res.bestLap < this.data.laps[res.track])) { this.data.laps[res.track] = res.bestLap; res.lapRecord = true; }
      this.save();
    },
  };

  // ── AudioManager ──
  const A = (NR.Audio = {
    ctx: null, master: null, sfxG: null, musG: null, noise: null, voices: 0, eng: null, musicOn: false, musicTimer: null,
    init() {
      if (this.ctx) return;
      const AC = window.AudioContext || window.webkitAudioContext; if (!AC) return;
      try { this.ctx = new AC(); } catch (e) { return; }
      const c = this.ctx;
      this.master = c.createDynamicsCompressor(); this.master.connect(c.destination);
      this.sfxG = c.createGain(); this.sfxG.connect(this.master);
      this.musG = c.createGain(); this.musG.connect(this.master);
      const len = c.sampleRate, buf = c.createBuffer(1, len, c.sampleRate), d = buf.getChannelData(0);
      for (let i = 0; i < len; i++) d[i] = Math.random() * 2 - 1;
      this.noise = buf;
      this.setVol(NR.Save.data.settings.music, NR.Save.data.settings.sfx);
    },
    resume() { if (this.ctx && this.ctx.state === 'suspended') this.ctx.resume().catch(() => {}); },
    setVol(m, s) { if (!this.ctx) return; this.musG.gain.value = m * 0.5; this.sfxG.gain.value = s; },
    env(g, t, a, peak, d) { g.gain.cancelScheduledValues(t); g.gain.setValueAtTime(0.0001, t); g.gain.exponentialRampToValueAtTime(peak, t + a); g.gain.exponentialRampToValueAtTime(0.0001, t + a + d); },
    tone(f, dur, vol, type, slide, delay) {
      if (!this.ctx || this.voices > 22) return; const c = this.ctx, t = c.currentTime + (delay || 0);
      const o = c.createOscillator(), g = c.createGain(); o.type = type || 'sine'; o.frequency.setValueAtTime(f, t);
      if (slide) o.frequency.exponentialRampToValueAtTime(Math.max(20, f * slide), t + dur);
      this.env(g, t, 0.006, vol, dur); o.connect(g); g.connect(this.sfxG); o.start(t); o.stop(t + dur + 0.05);
      this.voices++; o.onended = () => this.voices--;
    },
    burst(dur, vol, freq, q, type, delay) {
      if (!this.ctx || this.voices > 22) return; const c = this.ctx, t = c.currentTime + (delay || 0);
      const s = c.createBufferSource(); s.buffer = this.noise; s.playbackRate.value = 0.6 + Math.random() * 0.8;
      const f = c.createBiquadFilter(); f.type = type || 'bandpass'; f.frequency.value = freq; f.Q.value = q || 1;
      const g = c.createGain(); this.env(g, t, 0.004, vol, dur);
      s.connect(f); f.connect(g); g.connect(this.sfxG); s.start(t, Math.random() * 0.5); s.stop(t + dur + 0.05);
      this.voices++; s.onended = () => this.voices--;
    },
    // Dvigatel (o'yinchi mashinasi) — doimiy, aylanish bo'yicha chastota
    engineStart() {
      if (!this.ctx || this.eng) return; const c = this.ctx;
      const o1 = c.createOscillator(), o2 = c.createOscillator(), f = c.createBiquadFilter(), g = c.createGain();
      o1.type = 'sawtooth'; o2.type = 'square'; o1.frequency.value = 60; o2.frequency.value = 30.5;
      f.type = 'lowpass'; f.frequency.value = 600; f.Q.value = 4; g.gain.value = 0;
      const g2 = c.createGain(); g2.gain.value = 0.35;
      o1.connect(f); o2.connect(g2); g2.connect(f); f.connect(g); g.connect(this.sfxG); o1.start(); o2.start();
      this.eng = { o1, o2, f, g };
    },
    engineSet(rpm, load, on) {
      const e = this.eng; if (!e) return; const t = this.ctx.currentTime;
      const fr = 45 + rpm * 150;
      e.o1.frequency.setTargetAtTime(fr, t, 0.05); e.o2.frequency.setTargetAtTime(fr * 0.5 + 0.7, t, 0.05);
      e.f.frequency.setTargetAtTime(400 + rpm * 1800 + load * 600, t, 0.08);
      e.g.gain.setTargetAtTime(on ? 0.05 + load * 0.05 : 0, t, 0.1);
    },
    engineStop() { const e = this.eng; if (!e) return; try { e.o1.stop(); e.o2.stop(); } catch (x) { /* */ } this.eng = null; },
    pickup() { this.tone(880, 0.08, 0.12, 'triangle'); this.tone(1320, 0.12, 0.1, 'triangle', 1, 0.06); },
    cycle() { this.tone(660, 0.05, 0.07, 'square'); },
    seeker() { this.burst(0.5, 0.25, 900, 2, 'bandpass'); this.tone(300, 0.45, 0.12, 'sawtooth', 3); },
    volt() { for (let i = 0; i < 3; i++) { this.tone(1600, 0.12, 0.1, 'square', 0.3, i * 0.08); } },
    blast() { this.burst(0.6, 0.45, 180, 0.8, 'lowpass'); this.tone(90, 0.5, 0.22, 'sine', 0.4); },
    mine() { this.tone(220, 0.15, 0.12, 'square', 0.6); this.burst(0.08, 0.1, 2000, 3); },
    shield() { this.tone(440, 0.35, 0.1, 'sine', 2); this.tone(660, 0.35, 0.08, 'sine', 1.5, 0.05); },
    nitro() { this.burst(1.0, 0.3, 700, 0.7, 'bandpass'); this.tone(120, 0.9, 0.12, 'sawtooth', 2.5); },
    repair() { [784, 988, 1175, 1568].forEach((f, i) => this.tone(f, 0.15, 0.09, 'triangle', 1, i * 0.07)); },
    storm() { this.burst(1.2, 0.4, 120, 0.5, 'lowpass'); this.tone(2000, 0.3, 0.08, 'sawtooth', 0.1, 0.05); },
    hit(big) { this.burst(big ? 0.45 : 0.2, big ? 0.45 : 0.25, big ? 300 : 900, 1); this.tone(big ? 110 : 220, 0.25, 0.15, 'square', 0.5); },
    bump() { this.burst(0.12, 0.2, 400, 1.2); },
    scrape() { this.burst(0.25, 0.12, 2500, 2); },
    wreck() { this.burst(1.2, 0.6, 150, 0.6, 'lowpass'); this.tone(70, 1.0, 0.25, 'sine', 0.3); this.burst(0.5, 0.25, 3000, 1, 'highpass', 0.1); },
    beep(go) { this.tone(go ? 1046 : 523, go ? 0.5 : 0.18, 0.18, 'square'); },
    lap() { [659, 880].forEach((f, i) => this.tone(f, 0.15, 0.12, 'triangle', 1, i * 0.1)); },
    finish(win) { (win ? [523, 659, 784, 1046, 1318] : [523, 494, 440, 392]).forEach((f, i) => this.tone(f, 0.3, 0.13, 'triangle', 1, i * 0.13)); },
    // Fon musiqasi — synthwave (lookahead scheduler)
    music(on) {
      if (!this.ctx) return;
      if (!on) { this.musicOn = false; clearInterval(this.musicTimer); this.musicTimer = null; return; }
      if (this.musicOn) return; this.musicOn = true;
      const c = this.ctx, bpm = 112, st = 60 / bpm / 4; let step = 0, next = c.currentTime + 0.1;
      const roots = [41.2, 41.2, 36.7, 49.0], arp = [0, 7, 12, 15, 12, 7, 3, 7];
      const note = (f, t, d, v, type, cut) => {
        const o = c.createOscillator(), g = c.createGain(), fl = c.createBiquadFilter();
        o.type = type; o.frequency.value = f; fl.type = 'lowpass'; fl.frequency.value = cut;
        g.gain.setValueAtTime(0.0001, t); g.gain.exponentialRampToValueAtTime(v, t + 0.01); g.gain.exponentialRampToValueAtTime(0.0001, t + d);
        o.connect(fl); fl.connect(g); g.connect(this.musG); o.start(t); o.stop(t + d + 0.02);
      };
      const tick = () => {
        while (next < c.currentTime + 0.2) {
          const bar = ((step / 16) | 0) % 4, r = roots[bar], s = step % 16;
          if (s % 2 === 0) note(r * 2, next, st * 1.8, 0.16, 'sawtooth', 500);
          note(r * 4 * Math.pow(2, arp[s % 8] / 12), next, st * 0.9, 0.05, 'square', 2400);
          if (s % 4 === 0) { note(55, next, 0.18, 0.35, 'sine', 200); }
          if (s % 8 === 4) this.burst(0.12, 0.08, 1800, 0.8, 'bandpass', next - c.currentTime);
          if (s % 2 === 1) this.burst(0.03, 0.03, 8000, 1, 'highpass', next - c.currentTime);
          next += st; step++;
        }
      };
      tick(); this.musicTimer = setInterval(tick, 40);
    },
    dispose() { this.music(false); this.engineStop(); },
  });
  void A;
})();
