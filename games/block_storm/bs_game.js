/* BLOCK STORM — presentation, input, audio, screens. Requires bs_core.js loaded first.
   API: window.BSTORM = { launch(opts), current, VERSION } */
(function () {
  'use strict';
  var B = window.BSTORM = window.BSTORM || {};
  var Core = B._Core;
  if (!Core) throw new Error('BLOCK STORM: bs_core.js must be loaded before bs_game.js');
  var VERSION = '1.0.0';
  var STORE_KEY = 'block_storm_v1';
  var W = Core.W, H = Core.H, HID = Core.HID, CELLS = Core.CELLS;
  var STEP = 1 / 120;

  // ---------- palette (original "storm gem" palette) ----------
  var COLORS = [null, '#38bdf8', '#6d7cff', '#ff9b3d', '#ffd23f', '#3ee089', '#d16bff', '#ff5f7e', '#6b7591'];
  var GLOW = [null, '#7dd3fc', '#a5b4fc', '#fdba74', '#fde68a', '#86efac', '#f0abfc', '#fda4af', '#94a3b8'];
  var MODES = {
    marathon: { t: 'Marathon', d: "Har 10 qatorda daraja oshadi, tezlik ortadi. Maqsad: 15-daraja yoki cheksiz." },
    sprint: { t: 'Sprint 40', d: "40 qatorni imkon qadar tez tozalang. Natija — vaqt." },
    zen: { t: 'Zen', d: "Tezlashuvsiz, xotirjam o'yin. Maydon to'lsa — tozalanadi, o'yin davom etadi." }
  };
  var DAS_OPTS = [[0.21, 0.05], [0.15, 0.033], [0.1, 0.0]];
  var BTN_SIZES = [50, 60, 72];
  var DEF_SET = { music: 40, sfx: 75, buttons: false, btnSize: 1, ghost: true, smooth: true, shake: true, haptic: true, das: 1, goal: 15, mode: 'marathon' };

  function clone(o) { return JSON.parse(JSON.stringify(o)); }
  function loadStore() {
    var d = { v: 1, set: clone(DEF_SET), best: { marathon: 0, sprint: 0, zen: 0 }, stats: { games: 0, lines: 0, pieces: 0, time: 0 } };
    try {
      var raw = window.localStorage.getItem(STORE_KEY);
      if (raw) {
        var o = JSON.parse(raw);
        if (o && typeof o === 'object') {
          var k;
          if (o.set) for (k in DEF_SET) if (o.set[k] !== undefined && typeof o.set[k] === typeof DEF_SET[k]) d.set[k] = o.set[k];
          if (o.best) for (k in d.best) if (typeof o.best[k] === 'number' && isFinite(o.best[k])) d.best[k] = o.best[k];
          if (o.stats) for (k in d.stats) if (typeof o.stats[k] === 'number' && isFinite(o.stats[k])) d.stats[k] = o.stats[k];
        }
      }
    } catch (e) { /* storage unavailable */ }
    if (!MODES[d.set.mode]) d.set.mode = 'marathon';
    d.set.btnSize = Math.max(0, Math.min(2, d.set.btnSize | 0));
    d.set.das = Math.max(0, Math.min(2, d.set.das | 0));
    d.set.music = Math.max(0, Math.min(100, +d.set.music || 0));
    d.set.sfx = Math.max(0, Math.min(100, +d.set.sfx || 0));
    if (d.set.goal !== 0 && d.set.goal !== 15) d.set.goal = 15;
    return d;
  }
  function saveStore(st) { try { window.localStorage.setItem(STORE_KEY, JSON.stringify(st)); } catch (e) { /* ignore */ } }

  function esc(s) { return String(s).replace(/[&<>"']/g, function (c) { return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]; }); }
  function fmt(n) { n = Math.floor(n) || 0; return String(n).replace(/\B(?=(\d{3})+(?!\d))/g, ' '); }
  function fmtTime(t) {
    t = Math.max(0, t || 0);
    var m = Math.floor(t / 60), s = t - m * 60;
    var ss = s.toFixed(2); if (s < 10) ss = '0' + ss;
    return m + ':' + ss;
  }
  function hexRgb(h) { var n = parseInt(h.slice(1), 16); return [(n >> 16) & 255, (n >> 8) & 255, n & 255]; }
  function shade(h, f) {
    var c = hexRgb(h);
    for (var i = 0; i < 3; i++) c[i] = f >= 0 ? Math.round(c[i] + (255 - c[i]) * f) : Math.round(c[i] * (1 + f));
    return 'rgb(' + c[0] + ',' + c[1] + ',' + c[2] + ')';
  }
  function rgba(h, a) { var c = hexRgb(h); return 'rgba(' + c[0] + ',' + c[1] + ',' + c[2] + ',' + a + ')'; }
  function mkCanvas(w, h) { var c = document.createElement('canvas'); c.width = Math.max(1, w); c.height = Math.max(1, h); return c; }
  function rrect(x, ctx, X, Y, w, h, r) {
    ctx.beginPath();
    ctx.moveTo(X + r, Y); ctx.lineTo(X + w - r, Y); ctx.quadraticCurveTo(X + w, Y, X + w, Y + r);
    ctx.lineTo(X + w, Y + h - r); ctx.quadraticCurveTo(X + w, Y + h, X + w - r, Y + h);
    ctx.lineTo(X + r, Y + h); ctx.quadraticCurveTo(X, Y + h, X, Y + h - r);
    ctx.lineTo(X, Y + r); ctx.quadraticCurveTo(X, Y, X + r, Y); ctx.closePath();
  }
  function rr(ctx, X, Y, w, h, r) { rrect(null, ctx, X, Y, w, h, r); }

  // ---------- sprites ----------
  function blockSprite(col, s) {
    var cv = mkCanvas(s, s), x = cv.getContext('2d');
    var r = s * 0.17, b = Math.max(1, s * 0.13);
    x.save();
    rr(x, 0.5, 0.5, s - 1, s - 1, r); x.clip();
    var g = x.createLinearGradient(0, 0, s, s);
    g.addColorStop(0, shade(col, 0.42)); g.addColorStop(0.45, col); g.addColorStop(1, shade(col, -0.45));
    x.fillStyle = g; x.fillRect(0, 0, s, s);
    // bevel faces
    x.fillStyle = 'rgba(255,255,255,0.38)';
    x.beginPath(); x.moveTo(0, 0); x.lineTo(s, 0); x.lineTo(s - b, b); x.lineTo(b, b); x.closePath(); x.fill();
    x.fillStyle = 'rgba(255,255,255,0.18)';
    x.beginPath(); x.moveTo(0, 0); x.lineTo(b, b); x.lineTo(b, s - b); x.lineTo(0, s); x.closePath(); x.fill();
    x.fillStyle = 'rgba(0,0,0,0.22)';
    x.beginPath(); x.moveTo(s, 0); x.lineTo(s, s); x.lineTo(s - b, s - b); x.lineTo(s - b, b); x.closePath(); x.fill();
    x.fillStyle = 'rgba(0,0,0,0.36)';
    x.beginPath(); x.moveTo(0, s); x.lineTo(s, s); x.lineTo(s - b, s - b); x.lineTo(b, s - b); x.closePath(); x.fill();
    // inner face
    var gi = x.createLinearGradient(0, b, 0, s - b);
    gi.addColorStop(0, shade(col, 0.22)); gi.addColorStop(1, shade(col, -0.18));
    x.fillStyle = gi; rr(x, b, b, s - 2 * b, s - 2 * b, r * 0.5); x.fill();
    // gloss
    var gg = x.createLinearGradient(0, b, 0, s * 0.55);
    gg.addColorStop(0, 'rgba(255,255,255,0.55)'); gg.addColorStop(1, 'rgba(255,255,255,0)');
    x.fillStyle = gg;
    x.beginPath(); x.ellipse(s * 0.5, b, (s - 2 * b) * 0.48, s * 0.36, 0, 0, Math.PI); x.fill();
    // spark
    x.fillStyle = 'rgba(255,255,255,0.9)';
    x.beginPath(); x.arc(b * 1.55, b * 1.55, Math.max(0.8, s * 0.05), 0, Math.PI * 2); x.fill();
    x.restore();
    x.strokeStyle = 'rgba(0,0,0,0.45)'; x.lineWidth = Math.max(1, s * 0.035);
    rr(x, 0.5, 0.5, s - 1, s - 1, r); x.stroke();
    return cv;
  }
  function ghostSprite(col, s) {
    var cv = mkCanvas(s, s), x = cv.getContext('2d');
    var lw = Math.max(1.5, s * 0.075), i = s * 0.08;
    x.fillStyle = rgba(col, 0.13); rr(x, i, i, s - 2 * i, s - 2 * i, s * 0.14); x.fill();
    x.strokeStyle = rgba(col, 0.8); x.lineWidth = lw; x.stroke();
    return cv;
  }
  function flashSprite(s) {
    var cv = mkCanvas(s, s), x = cv.getContext('2d');
    x.fillStyle = '#fff'; rr(x, 0, 0, s, s, s * 0.17); x.fill();
    return cv;
  }
  function blobSprite(col) {
    var cv = mkCanvas(256, 256), x = cv.getContext('2d');
    var g = x.createRadialGradient(128, 128, 0, 128, 128, 128);
    g.addColorStop(0, rgba(col, 0.55)); g.addColorStop(0.5, rgba(col, 0.18)); g.addColorStop(1, rgba(col, 0));
    x.fillStyle = g; x.fillRect(0, 0, 256, 256);
    return cv;
  }

  // preview geometry per type (spawn orientation)
  var PREV = [null];
  for (var pt = 1; pt <= 7; pt++) {
    var c0 = CELLS[pt][0], mnx = 9, mxx = -9, mny = 9, mxy = -9;
    for (var q = 0; q < 8; q += 2) { mnx = Math.min(mnx, c0[q]); mxx = Math.max(mxx, c0[q]); mny = Math.min(mny, c0[q + 1]); mxy = Math.max(mxy, c0[q + 1]); }
    PREV.push({ c: c0, x0: mnx, y0: mny, w: mxx - mnx + 1, h: mxy - mny + 1 });
  }

  // ---------- audio (Web Audio synthesis) ----------
  function Snd(game) { this.g = game; this.ctx = null; this.dead = false; this.timer = 0; this.musicOn = false; this.lastSoft = 0; this.lastMove = 0; }
  Snd.prototype.unlock = function () {
    if (this.dead) return;
    try {
      if (!this.ctx) {
        var AC = window.AudioContext || window.webkitAudioContext;
        if (!AC) return;
        var c = this.ctx = new AC();
        this.master = c.createGain(); this.master.gain.value = 0.9;
        var comp = c.createDynamicsCompressor();
        comp.threshold.value = -14; comp.ratio.value = 4;
        this.master.connect(comp); comp.connect(c.destination);
        this.sfx = c.createGain(); this.sfx.connect(this.master);
        this.mus = c.createGain(); this.mus.connect(this.master);
        this.echo = c.createDelay(1); this.echo.delayTime.value = 0.39;
        var fb = c.createGain(); fb.gain.value = 0.32;
        var ef = c.createBiquadFilter(); ef.type = 'lowpass'; ef.frequency.value = 2200;
        this.echo.connect(ef); ef.connect(fb); fb.connect(this.echo); ef.connect(this.mus);
        var len = c.sampleRate, buf = c.createBuffer(1, len, c.sampleRate), d = buf.getChannelData(0);
        for (var i = 0; i < len; i++) d[i] = Math.random() * 2 - 1;
        this.noiseBuf = buf;
        this.vol();
        if (this.wantMusic) this.musicStart();
      }
      if (this.ctx.state === 'suspended') this.ctx.resume();
    } catch (e) { /* audio unavailable */ }
  };
  Snd.prototype.vol = function () {
    if (!this.ctx) return;
    var s = this.g.set;
    this.sfx.gain.value = (s.sfx / 100) * 0.9;
    this.mus.gain.value = (s.music / 100) * 0.55;
  };
  Snd.prototype.tone = function (f, t0, dur, type, v, f2, out) {
    var c = this.ctx, o = c.createOscillator(), g = c.createGain();
    o.type = type || 'sine'; o.frequency.setValueAtTime(f, t0);
    if (f2) o.frequency.exponentialRampToValueAtTime(f2, t0 + dur);
    g.gain.setValueAtTime(0.0001, t0);
    g.gain.exponentialRampToValueAtTime(v, t0 + 0.006);
    g.gain.exponentialRampToValueAtTime(0.0001, t0 + dur);
    o.connect(g); g.connect(out || this.sfx);
    o.start(t0); o.stop(t0 + dur + 0.02);
  };
  Snd.prototype.noise = function (t0, dur, v, freq, type, q, f2) {
    var c = this.ctx, s = c.createBufferSource(), f = c.createBiquadFilter(), g = c.createGain();
    s.buffer = this.noiseBuf;
    f.type = type || 'lowpass'; f.frequency.setValueAtTime(freq, t0); if (q) f.Q.value = q;
    if (f2) f.frequency.exponentialRampToValueAtTime(f2, t0 + dur);
    g.gain.setValueAtTime(v, t0); g.gain.exponentialRampToValueAtTime(0.0001, t0 + dur);
    s.connect(f); f.connect(g); g.connect(this.sfx);
    s.start(t0, Math.random() * 0.5); s.stop(t0 + dur + 0.02);
  };
  Snd.prototype.play = function (name, n) {
    if (!this.ctx || this.dead || this.g.set.sfx <= 0) return;
    var t = this.ctx.currentTime + 0.005, i;
    try {
      switch (name) {
        case 'move':
          if (t - this.lastMove < 0.025) return; this.lastMove = t;
          this.tone(1250, t, 0.035, 'triangle', 0.05); break;
        case 'rotate': this.tone(700, t, 0.07, 'triangle', 0.07, 1050); break;
        case 'soft':
          if (t - this.lastSoft < 0.045) return; this.lastSoft = t;
          this.tone(330, t, 0.03, 'sine', 0.04); break;
        case 'hard':
          this.noise(t, 0.16, 0.45, 2400, 'lowpass', 0, 300);
          this.tone(170, t, 0.2, 'sine', 0.5, 50); break;
        case 'lock': this.tone(230, t, 0.07, 'triangle', 0.13, 160); this.noise(t, 0.035, 0.08, 4000, 'highpass'); break;
        case 'hold': this.tone(520, t, 0.09, 'sine', 0.1, 780); this.tone(780, t + 0.05, 0.09, 'sine', 0.07, 520); break;
        case 'clear':
          var base = [0, 523.25, 587.33, 659.25, 783.99][n] || 523.25, steps = [1, 1.25, 1.5, 2, 2.5];
          for (i = 0; i <= n; i++) this.tone(base * steps[i], t + i * 0.055, 0.32, 'triangle', 0.1 + n * 0.015);
          this.noise(t, 0.35 + n * 0.08, 0.12 + n * 0.03, 1200, 'bandpass', 0.8, 7000);
          if (n >= 4) {
            this.tone(65, t, 0.9, 'sine', 0.55, 32);
            this.noise(t, 1.1, 0.35, 900, 'lowpass', 0, 120);
            [523.25, 659.25, 783.99, 1046.5].forEach(function (f, k) { this.tone(f, t + 0.25 + k * 0.03, 0.9, 'sawtooth', 0.04); }, this);
          }
          break;
        case 'combo': var f0 = 660 * Math.pow(2, Math.min(n, 14) / 12); this.tone(f0, t + 0.12, 0.14, 'square', 0.04); this.tone(f0 * 1.5, t + 0.18, 0.16, 'square', 0.035); break;
        case 'b2b': this.tone(1318.5, t + 0.1, 0.25, 'triangle', 0.08); this.tone(1975.5, t + 0.16, 0.3, 'triangle', 0.06); break;
        case 'spin': this.tone(400, t, 0.25, 'sawtooth', 0.05, 1600); break;
        case 'level':
          [523.25, 659.25, 783.99, 1046.5, 1318.5].forEach(function (f, k) { this.tone(f, t + k * 0.07, 0.35, 'triangle', 0.09); }, this);
          break;
        case 'over':
          [392, 329.6, 261.6, 196].forEach(function (f, k) { this.tone(f, t + k * 0.18, 0.5, 'sawtooth', 0.06, f * 0.96); }, this);
          this.noise(t, 1.2, 0.15, 600, 'lowpass', 0, 80);
          break;
        case 'win':
          [523.25, 659.25, 783.99, 1046.5, 783.99, 1046.5, 1318.5].forEach(function (f, k) { this.tone(f, t + k * 0.09, 0.4, 'triangle', 0.09); }, this);
          break;
        case 'count': this.tone(n ? 1046.5 : 784, t, n ? 0.35 : 0.14, 'triangle', 0.1); break;
        case 'click': this.tone(900, t, 0.04, 'sine', 0.06, 1300); break;
        case 'zen': this.noise(t, 1.2, 0.15, 3000, 'bandpass', 0.6, 200); this.tone(392, t, 1, 'sine', 0.1); this.tone(587.3, t + 0.1, 1, 'sine', 0.07); break;
      }
    } catch (e) { /* ignore */ }
  };
  // calm synth music: i - VI - III - VII in A minor, 74 BPM
  var CHORDS = [[57, 60, 64], [53, 57, 60], [48, 52, 55], [55, 59, 62]];
  function mtof(m) { return 440 * Math.pow(2, (m - 69) / 12); }
  Snd.prototype.musicStart = function () {
    this.wantMusic = true;
    if (!this.ctx || this.dead || this.musicOn) return;
    this.musicOn = true;
    this.mStep = 0; this.mT = this.ctx.currentTime + 0.12;
    var self = this;
    this.timer = setInterval(function () { self.musicTick(); }, 60);
    this.musicTick();
  };
  Snd.prototype.musicStop = function () {
    this.wantMusic = false;
    if (this.timer) clearInterval(this.timer);
    this.timer = 0; this.musicOn = false;
  };
  Snd.prototype.musicTick = function () {
    if (!this.ctx || this.dead) return;
    var c = this.ctx, e8 = 60 / 74 / 2;
    if (this.mT < c.currentTime) this.mT = c.currentTime + 0.05;
    while (this.mT < c.currentTime + 0.35) {
      var st = this.mStep, bar = Math.floor(st / 8) % 4, k = st % 8, ch = CHORDS[bar], t = this.mT;
      if (this.g.set.music > 0) {
        if (k === 0) for (var i = 0; i < 3; i++) this.pad(mtof(ch[i]), t, e8 * 8);
        if (k === 0 || k === 4) this.tone(mtof(ch[0] - 12), t, e8 * 3.6, 'sine', 0.16, 0, this.mus);
        var pat = [0, 1, 2, 1, 2, 0, 1, 2], up = (st >> 3) % 2 ? 12 : 0;
        if (k !== 7 || bar % 2) this.pluck(mtof(ch[pat[k]] + 12 + up), t);
      }
      this.mStep++; this.mT += e8;
    }
  };
  Snd.prototype.pad = function (f, t, dur) {
    var c = this.ctx, o = c.createOscillator(), o2 = c.createOscillator(), fl = c.createBiquadFilter(), g = c.createGain();
    o.type = 'sawtooth'; o2.type = 'sawtooth'; o.frequency.value = f; o2.frequency.value = f; o2.detune.value = 9;
    fl.type = 'lowpass'; fl.frequency.value = 700;
    g.gain.setValueAtTime(0.0001, t); g.gain.linearRampToValueAtTime(0.022, t + dur * 0.35); g.gain.linearRampToValueAtTime(0.0001, t + dur * 1.05);
    o.connect(fl); o2.connect(fl); fl.connect(g); g.connect(this.mus);
    o.start(t); o2.start(t); o.stop(t + dur * 1.1); o2.stop(t + dur * 1.1);
  };
  Snd.prototype.pluck = function (f, t) {
    var c = this.ctx, o = c.createOscillator(), g = c.createGain();
    o.type = 'triangle'; o.frequency.value = f;
    g.gain.setValueAtTime(0.0001, t); g.gain.exponentialRampToValueAtTime(0.05, t + 0.01); g.gain.exponentialRampToValueAtTime(0.0001, t + 0.45);
    o.connect(g); g.connect(this.mus); g.connect(this.echo);
    o.start(t); o.stop(t + 0.5);
  };
  Snd.prototype.close = function () {
    this.musicStop(); this.dead = true;
    if (this.ctx) { try { this.ctx.close(); } catch (e) { /* ignore */ } }
    this.ctx = null;
  };

  // ---------- game ----------
  var PARTS = 640, TRAILS = 6, POPS = 8;

  function Game(opts) {
    var self = this;
    this.opts = opts || {};
    this.name = String(this.opts.playerName || "O'yinchi").slice(0, 32);
    this.store = loadStore(); this.set = this.store.set;
    this.state = 'menu'; this.screen = ''; this.engine = null; this.dead = false;
    this.runId = 0; this.resultSent = -1; this.lastRes = null; this.acc = 0; this.clock = 0;
    this.ls = [];
    this.prevOverflow = document.body.style.overflow;
    document.body.style.overflow = 'hidden';

    var root = this.root = document.createElement('div');
    root.className = 'bstorm';
    root.innerHTML =
      '<canvas class="bs-cv"></canvas>' +
      '<div class="bs-ctrl"></div>' +
      '<button class="bs-pbtn" data-act="pause" aria-label="Pauza"><i></i><i></i></button>' +
      '<div class="bs-scr"></div>';
    this.cv = root.querySelector('.bs-cv');
    this.ctx = this.cv.getContext('2d');
    this.ctrl = root.querySelector('.bs-ctrl');
    this.pbtn = root.querySelector('.bs-pbtn');
    this.scr = root.querySelector('.bs-scr');
    document.body.appendChild(root);

    this.snd = new Snd(this);
    // fx pools
    this.parts = []; for (var i = 0; i < PARTS; i++) this.parts.push({ on: false, x: 0, y: 0, vx: 0, vy: 0, life: 0, max: 1, s: 1, col: '#fff', g: 1 });
    this.trails = []; for (i = 0; i < TRAILS; i++) this.trails.push({ on: false, t: 0, col: '#fff', n: 0, xs: new Int8Array(4), ys: new Int8Array(4), y0: 0 });
    this.pops = []; for (i = 0; i < POPS; i++) this.pops.push({ on: false, t: 0, life: 1, text: '', sub: '', col: '#fff', size: 1, y: 0 });
    this.rain = new Float32Array(48 * 4);
    for (i = 0; i < 48; i++) { this.rain[i * 4] = Math.random(); this.rain[i * 4 + 1] = Math.random(); this.rain[i * 4 + 2] = 0.4 + Math.random() * 0.8; this.rain[i * 4 + 3] = 0.5 + Math.random(); }
    this.deco = []; for (i = 0; i < 12; i++) this.deco.push(this.newDeco(true));
    this.shakeT = 0; this.shakeA = 0; this.bounceY = 0; this.bounceV = 0; this.flashA = 0;
    this.lockFxT = 0; this.lockFx = new Int8Array(8); this.lockFxType = 1;
    this.ringT = 0; this.endT = 0; this.countT = 0; this.danger = 0;
    this.gest = { id: null };
    this.keysDown = {};
    this.btnPtr = {};
    this.blobs = [blobSprite('#5b6bff'), blobSprite('#c040ff'), blobSprite('#18c8ff')];

    // listeners
    this.on(window, 'resize', function () { self.needResize = true; });
    this.on(window, 'orientationchange', function () { self.needResize = true; });
    this.on(document, 'visibilitychange', function () { if (document.hidden && (self.state === 'play' || self.state === 'count')) self.pause(); });
    this.on(window, 'keydown', function (e) { self.onKey(e, true); });
    this.on(window, 'keyup', function (e) { self.onKey(e, false); });
    this.on(this.cv, 'pointerdown', function (e) { self.gDown(e); });
    this.on(window, 'pointermove', function (e) { self.gMove(e); });
    this.on(window, 'pointerup', function (e) { self.gUp(e, false); self.btnUp(e); });
    this.on(window, 'pointercancel', function (e) { self.gUp(e, true); self.btnUp(e); });
    this.on(root, 'pointerdown', function () { self.snd.unlock(); }, true);
    this.on(root, 'click', function (e) { self.onClick(e); });
    this.on(root, 'input', function (e) { self.onInput(e); });
    this.on(root, 'contextmenu', function (e) { e.preventDefault(); });
    this.on(this.ctrl, 'pointerdown', function (e) { self.btnDown(e); });

    try { var tw = window.Telegram && window.Telegram.WebApp; if (tw && tw.disableVerticalSwipes) tw.disableVerticalSwipes(); } catch (e) { /* ignore */ }

    this.resize();
    this.show('menu');
    this.last = performance.now();
    this.frameFn = function (now) { self.frame(now); };
    this.raf = requestAnimationFrame(this.frameFn);
  }
  var G = Game.prototype;

  G.on = function (t, type, fn, cap) { t.addEventListener(type, fn, cap || false); this.ls.push([t, type, fn, cap || false]); };

  // ---------- layout ----------
  G.resize = function () {
    this.needResize = false;
    var Wp = this.root.clientWidth || window.innerWidth || 360, Hp = this.root.clientHeight || window.innerHeight || 640;
    var dpr = Math.min(2, window.devicePixelRatio || 1);
    this.dpr = dpr; this.W = Wp; this.H = Hp;
    this.cv.width = Math.round(Wp * dpr); this.cv.height = Math.round(Hp * dpr);
    this.cv.style.width = Wp + 'px'; this.cv.style.height = Hp + 'px';
    var land = Wp > Hp * 1.05, btn = this.set.buttons ? BTN_SIZES[this.set.btnSize] : 0, g = 8, c, L = { land: land };
    if (!land) {
      var top = 56; // room for the pause button row
      var ctrlH = btn ? btn * 2 + 26 : 10;
      c = Math.floor(Math.min((Wp - 2 * g - 8) / 13.2, (Hp - top - ctrlH - 12) / 20.2, 44));
      // HUD row (hold + stats) sits above the board inside "top"
      var hudH = Math.max(46, Math.round(c * 2.6));
      c = Math.floor(Math.min(c, (Hp - 10 - hudH - 10 - ctrlH) / 20.2));
      c = Math.max(8, c);
      var side = Math.round(c * 3.1), bw = c * 10, tot = bw + 8 + side;
      var y0 = Math.max(10, Math.round((Hp - ctrlH - (hudH + 8 + c * 20)) / 2));
      L.bx = Math.round((Wp - tot) / 2); L.by = y0 + hudH + 8;
      L.hold = { x: L.bx, y: y0, w: Math.round(c * 3.6), h: hudH };
      L.stats = { x: L.bx + L.hold.w + 10, y: y0, w: Math.max(40, Wp - 60 - (L.bx + L.hold.w + 10)), h: hudH };
      L.next = { x: L.bx + bw + 8, y: L.by, w: side, h: Math.round(c * 13) };
    } else {
      c = Math.floor(Math.min((Hp - 16) / 20.4, (Wp - 24) / 22, 44));
      c = Math.max(8, c);
      var bw2 = c * 10;
      L.bx = Math.round((Wp - bw2) / 2); L.by = Math.round((Hp - c * 20) / 2);
      var pw = Math.round(c * 4.6);
      L.hold = { x: L.bx - 12 - pw, y: L.by, w: pw, h: Math.round(c * 3.6) };
      L.stats = { x: L.bx - 12 - pw, y: L.by + L.hold.h + 12, w: pw, h: Math.round(c * 9) };
      L.next = { x: L.bx + bw2 + 12, y: L.by, w: Math.round(c * 4), h: Math.round(c * 14) };
    }
    L.c = c; L.bw = c * 10; L.bh = c * 20; L.btn = btn;
    this.L = L;
    this.buildSprites();
    this.buildBg();
    this.layoutButtons();
  };

  G.buildSprites = function () {
    var dpr = this.dpr, c = this.L.c;
    var s1 = Math.round(c * dpr), s2 = Math.round(c * 0.62 * dpr), s3 = Math.round(c * 0.5 * dpr);
    this.spr = []; this.sprM = []; this.sprS = []; this.gho = [];
    for (var t = 0; t <= 8; t++) {
      if (!t) { this.spr.push(null); this.sprM.push(null); this.sprS.push(null); this.gho.push(null); continue; }
      this.spr.push(blockSprite(COLORS[t], s1));
      this.sprM.push(blockSprite(COLORS[t], s2));
      this.sprS.push(blockSprite(COLORS[t], s3));
      this.gho.push(ghostSprite(COLORS[t], s1));
    }
    this.flashSpr = flashSprite(s1);
    this.buildPanel();
  };

  G.panelColors = function () {
    var lv = this.engine ? this.engine.level : 1;
    var pal = [['#38bdf8', '#a855f7'], ['#22d3ee', '#6366f1'], ['#f472b6', '#8b5cf6'], ['#34d399', '#3b82f6'], ['#fbbf24', '#ef4444'], ['#a78bfa', '#ec4899']];
    return pal[Math.floor((lv - 1) / 3) % pal.length];
  };

  G.buildPanel = function () {
    var L = this.L, dpr = this.dpr, c = L.c, p = Math.max(4, Math.round(c * 0.3)), m = 18;
    var w = L.bw + 2 * p + 2 * m, h = L.bh + 2 * p + 2 * m;
    var cv = mkCanvas(Math.round(w * dpr), Math.round(h * dpr)), x = cv.getContext('2d');
    x.scale(dpr, dpr);
    var col = this.panelColors();
    this.panelCol = col;
    x.save();
    x.shadowColor = rgba(col[1], 0.7); x.shadowBlur = 16;
    var gb = x.createLinearGradient(0, m, 0, h - m);
    gb.addColorStop(0, rgba(col[0], 0.95)); gb.addColorStop(1, rgba(col[1], 0.95));
    x.fillStyle = gb; rr(x, m, m, w - 2 * m, h - 2 * m, p + 4); x.fill();
    x.restore();
    // gloss on frame (under the well so it only tints the rim)
    var gg = x.createLinearGradient(0, m, 0, m + p * 1.2);
    gg.addColorStop(0, 'rgba(255,255,255,0.45)'); gg.addColorStop(1, 'rgba(255,255,255,0)');
    x.fillStyle = gg; rr(x, m + 2, m + 1, w - 2 * m - 4, p * 1.2, p * 0.6); x.fill();
    var gi = x.createLinearGradient(0, m + p, 0, h - m - p);
    gi.addColorStop(0, 'rgba(14,16,40,0.96)'); gi.addColorStop(1, 'rgba(6,7,20,0.97)');
    x.fillStyle = gi; rr(x, m + p - 1, m + p - 1, L.bw + 2, L.bh + 2, 4); x.fill();
    x.strokeStyle = 'rgba(255,255,255,0.05)'; x.lineWidth = 1;
    x.beginPath();
    for (var i = 1; i < 10; i++) { x.moveTo(m + p + i * c + 0.5, m + p); x.lineTo(m + p + i * c + 0.5, m + p + L.bh); }
    for (i = 1; i < 20; i++) { x.moveTo(m + p, m + p + i * c + 0.5); x.lineTo(m + p + L.bw, m + p + i * c + 0.5); }
    x.stroke();
    this.panel = cv; this.panelOff = p + m; this.panelW = w; this.panelH = h;
    this.panelLevel = this.engine ? this.engine.level : 1;
  };

  G.buildBg = function () {
    var cv = mkCanvas(Math.max(1, Math.round(this.W * this.dpr / 2)), Math.max(1, Math.round(this.H * this.dpr / 2))), x = cv.getContext('2d');
    var w = cv.width, h = cv.height;
    var g = x.createLinearGradient(0, 0, w * 0.3, h);
    g.addColorStop(0, '#0b0c26'); g.addColorStop(0.55, '#110a2c'); g.addColorStop(1, '#050611');
    x.fillStyle = g; x.fillRect(0, 0, w, h);
    var v = x.createRadialGradient(w / 2, h * 0.45, Math.min(w, h) * 0.2, w / 2, h / 2, Math.max(w, h) * 0.75);
    v.addColorStop(0, 'rgba(0,0,0,0)'); v.addColorStop(1, 'rgba(0,0,0,0.55)');
    x.fillStyle = v; x.fillRect(0, 0, w, h);
    this.bg = cv;
  };

  G.layoutButtons = function () {
    var L = this.L, b = L.btn, html = '';
    if (!b) { this.ctrl.innerHTML = ''; this.ctrl.style.display = 'none'; return; }
    var g = 10, gap = 8, Hp = this.H, Wp = this.W;
    var r2 = Hp - g - b, r1 = r2 - gap - b;
    function k(id, label, x, y, w, cls) {
      return '<div class="bs-k' + (cls ? ' ' + cls : '') + '" data-b="' + id + '" style="left:' + x + 'px;top:' + y + 'px;width:' + (w || b) + 'px;height:' + b + 'px;font-size:' + Math.round(b * 0.42) + 'px">' + label + '</div>';
    }
    html += k('hard', '⤓', g + b + gap, r1, 0, 'bs-k2');
    html += k('left', '◀', g, r2);
    html += k('soft', '▼', g + b + gap, r2);
    html += k('right', '▶', g + 2 * (b + gap), r2);
    var rx = Wp - g - 2 * b - gap;
    html += k('ccw', '⟲', rx, r1);
    html += k('hold', '<span>HOLD</span>', rx + b + gap, r1, 0, 'bs-k3');
    html += k('cw', '⟳', rx, r2, 2 * b + gap, 'bs-k1');
    this.ctrl.innerHTML = html;
    this.ctrl.style.display = this.state === 'play' || this.state === 'count' ? 'block' : 'none';
  };

  // ---------- screens ----------
  G.show = function (name) {
    var s = this.set, st = this.store, h = '', self = this;
    this.screen = name;
    this.pbtn.style.display = (name === '' && (this.state === 'play' || this.state === 'count')) ? 'flex' : 'none';
    if (this.ctrl) this.ctrl.style.display = (name === '' && this.L.btn && (this.state === 'play' || this.state === 'count')) ? 'block' : 'none';
    if (!name) { this.scr.className = 'bs-scr'; this.scr.innerHTML = ''; return; }
    var bestLine = s.mode === 'sprint' ? (st.best.sprint ? fmtTime(st.best.sprint) : '—') : fmt(st.best[s.mode] || 0);
    function tog(k, label) { return '<div class="bs-row"><span>' + label + '</span><button class="bs-tog' + (s[k] ? ' on' : '') + '" data-act="tog" data-k="' + k + '"><i></i></button></div>'; }
    function seg(k, label, opts) {
      var o = '<div class="bs-row"><span>' + label + '</span><div class="bs-seg">';
      opts.forEach(function (p) { o += '<button data-act="seg" data-k="' + k + '" data-v="' + p[0] + '"' + (s[k] === p[0] ? ' class="on"' : '') + '>' + p[1] + '</button>'; });
      return o + '</div></div>';
    }
    function rng(k, label) { return '<div class="bs-row"><span>' + label + '</span><input type="range" min="0" max="100" step="5" value="' + s[k] + '" data-k="' + k + '"><b class="bs-rv" data-rv="' + k + '">' + s[k] + '</b></div>'; }
    if (name === 'menu') {
      h = '<div class="bs-menu">' +
        '<button class="bs-x" data-act="exit" aria-label="Chiqish">✕</button>' +
        '<div class="bs-logo"><div class="bs-cubes"><i style="--c:' + COLORS[1] + '"></i><i style="--c:' + COLORS[6] + '"></i><i style="--c:' + COLORS[4] + '"></i><i style="--c:' + COLORS[7] + '"></i></div>' +
        '<h1><span>BLOCK</span><b>STORM</b></h1></div>' +
        '<div class="bs-hi">Salom, <b>' + esc(this.name) + '</b></div>' +
        '<button class="bs-btn bs-main" data-act="play">▶ PLAY<small>O\'ynash</small></button>' +
        '<button class="bs-btn" data-act="mode">MODE · <b>' + MODES[s.mode].t + (s.mode === 'marathon' ? (s.goal ? ' 15' : ' ∞') : '') + '</b></button>' +
        '<button class="bs-btn" data-act="settings">SETTINGS<small>Sozlamalar</small></button>' +
        '<button class="bs-btn" data-act="help">HOW TO PLAY<small>Qanday o\'ynash</small></button>' +
        '<div class="bs-best">Rekord (' + MODES[s.mode].t + '): <b>' + bestLine + '</b></div>' +
        '<div class="bs-foot">O\'yinlar: ' + fmt(st.stats.games) + ' · Qatorlar: ' + fmt(st.stats.lines) + ' · v' + VERSION + '</div>' +
        '</div>';
    } else if (name === 'mode') {
      h = '<div class="bs-panel"><div class="bs-head"><button class="bs-back" data-act="back">‹</button><h2>MODE</h2></div><div class="bs-scroll">';
      ['marathon', 'sprint', 'zen'].forEach(function (m) {
        var b = m === 'sprint' ? (st.best.sprint ? fmtTime(st.best.sprint) : '—') : fmt(st.best[m] || 0);
        h += '<button class="bs-card' + (s.mode === m ? ' on' : '') + '" data-act="setmode" data-v="' + m + '"><b>' + MODES[m].t + '</b><span>' + MODES[m].d + '</span><em>Rekord: ' + b + '</em></button>';
      });
      h += seg('goal', 'Marafon maqsadi', [[15, '15-daraja'], [0, 'Cheksiz']]);
      h += '</div><button class="bs-btn bs-main" data-act="play">▶ PLAY</button></div>';
    } else if (name === 'settings') {
      h = '<div class="bs-panel"><div class="bs-head"><button class="bs-back" data-act="back">‹</button><h2>SETTINGS</h2></div><div class="bs-scroll">' +
        rng('music', 'Musiqa') + rng('sfx', 'Effektlar') +
        tog('buttons', 'Ekran tugmalari') +
        seg('btnSize', 'Tugma o\'lchami', [[0, 'Kichik'], [1, 'O\'rta'], [2, 'Katta']]) +
        seg('das', 'Surish tezligi', [[0, 'Sekin'], [1, 'O\'rta'], [2, 'Tez']]) +
        tog('ghost', 'Soya (tushish joyi)') + tog('smooth', 'Silliq tushish') +
        tog('shake', 'Ekran silkinishi') + tog('haptic', 'Tebranish') +
        '</div></div>';
    } else if (name === 'help') {
      h = '<div class="bs-panel"><div class="bs-head"><button class="bs-back" data-act="back">‹</button><h2>HOW TO PLAY</h2></div><div class="bs-scroll bs-help">' +
        '<p>Tushayotgan bo\'laklarni joylashtirib, to\'liq gorizontal qatorlarni hosil qiling — ular yo\'qoladi. Bo\'laklar tepaga yetib qolsa, o\'yin tugaydi.</p>' +
        '<h3>Imo-ishoralar</h3><ul>' +
        '<li><b>Bosish</b> — soat yo\'nalishida burish</li>' +
        '<li><b>Chapga / o\'ngga surish</b> — barmoq ortidan katakma-katak siljiydi</li>' +
        '<li><b>Pastga sekin tortish</b> — yumshoq tushirish</li>' +
        '<li><b>Pastga tez silkitish</b> — darhol tushirish</li>' +
        '<li><b>Yuqoriga silkitish</b> — HOLD (saqlab qo\'yish)</li></ul>' +
        '<h3>Klaviatura</h3><ul><li>← → siljitish, ↓ yumshoq tushirish</li><li>↑ / X burish, Z teskari burish</li><li>Space — darhol tushirish, C / Shift — HOLD</li><li>P / Esc — pauza</li></ul>' +
        '<h3>Ochkolar</h3><ul><li>1 / 2 / 3 / 4 qator: 100 / 300 / 500 / 800 × daraja</li><li>Ketma-ket tozalash (kombo): 50 × kombo × daraja</li><li>Ketma-ket 4 qator yoki spin (B2B): × 1.5</li><li>T-spin: 800 / 1200 / 1600 × daraja</li><li>Yumshoq tushirish: 1, darhol tushirish: 2 (har katak)</li></ul>' +
        '<p class="bs-dim">Har 10 qatorda daraja oshadi. 4 qatorni birdan tozalash — <b>STORM!</b></p>' +
        '</div></div>';
    } else if (name === 'pause') {
      h = '<div class="bs-panel bs-small"><h2 class="bs-big">PAUZA</h2>' +
        '<button class="bs-btn bs-main" data-act="resume">▶ Davom etish</button>' +
        '<button class="bs-btn" data-act="restart">↻ Qayta boshlash</button>' +
        (this.engine && this.engine.mode === 'zen' ? '<button class="bs-btn" data-act="finish">✔ Yakunlash</button>' : '') +
        '<button class="bs-btn" data-act="settings">Sozlamalar</button>' +
        '<button class="bs-btn" data-act="menu">Bosh menyu</button></div>';
    } else if (name === 'over') {
      var r = this.lastRes || {}, e = this.engine, title = "O'YIN TUGADI";
      if (e && e.won) title = e.mode === 'sprint' ? 'SPRINT YAKUNLANDI!' : 'MARAFON YAKUNLANDI!';
      else if (e && e.mode === 'zen') title = 'ZEN YAKUNLANDI';
      var main = r.mode === 'sprint' && e && e.won ? fmtTime(r.time) : fmt(r.score);
      var best = r.mode === 'sprint' ? (st.best.sprint ? fmtTime(st.best.sprint) : '—') : fmt(st.best[r.mode] || 0);
      h = '<div class="bs-panel bs-small bs-res"><h2 class="bs-big">' + title + '</h2>' +
        (this.newRecord ? '<div class="bs-rec">★ YANGI REKORD! ★</div>' : '') +
        '<div class="bs-score">' + main + '</div>' +
        '<div class="bs-grid">' +
        '<div><small>Ochko</small><b>' + fmt(r.score) + '</b></div>' +
        '<div><small>Qatorlar</small><b>' + fmt(r.lines) + '</b></div>' +
        '<div><small>Daraja</small><b>' + (r.maxLevel || 1) + '</b></div>' +
        '<div><small>Vaqt</small><b>' + fmtTime(r.time) + '</b></div>' +
        '<div><small>Bo\'laklar</small><b>' + fmt(r.pieces) + '</b></div>' +
        '<div><small>Rekord</small><b>' + best + '</b></div></div>' +
        '<button class="bs-btn bs-main" data-act="again">↻ Yana o\'ynash</button>' +
        '<button class="bs-btn" data-act="menu">Bosh menyu</button></div>';
    }
    this.scr.innerHTML = h;
    this.scr.className = 'bs-scr on bs-s-' + name;
    void self;
  };

  G.onInput = function (e) {
    var t = e.target;
    if (!t || t.type !== 'range') return;
    var k = t.getAttribute('data-k');
    if (k !== 'music' && k !== 'sfx') return;
    this.set[k] = Math.max(0, Math.min(100, +t.value || 0));
    var rv = this.scr.querySelector('[data-rv="' + k + '"]'); if (rv) rv.textContent = this.set[k];
    this.snd.vol(); saveStore(this.store);
  };

  G.onClick = function (e) {
    var t = e.target && e.target.closest ? e.target.closest('[data-act]') : null;
    if (!t || !this.root.contains(t) || this.dead) return;
    var a = t.getAttribute('data-act'), v = t.getAttribute('data-v'), k = t.getAttribute('data-k');
    this.snd.unlock();
    if (a !== 'pause') this.snd.play('click');
    switch (a) {
      case 'play': this.start(this.set.mode); break;
      case 'again': this.start(this.engine ? this.engine.mode : this.set.mode); break;
      case 'restart': this.start(this.engine ? this.engine.mode : this.set.mode); break;
      case 'mode': this.backTo = 'menu'; this.show('mode'); break;
      case 'setmode': if (MODES[v]) { this.set.mode = v; saveStore(this.store); } this.show('mode'); break;
      case 'settings': this.backTo = this.state === 'pause' ? 'pause' : 'menu'; this.show('settings'); break;
      case 'help': this.backTo = 'menu'; this.show('help'); break;
      case 'back': this.show(this.backTo || 'menu'); break;
      case 'exit': this.exit(); break;
      case 'pause': this.pause(); break;
      case 'resume': this.resume(); break;
      case 'finish':
        if (this.engine && !this.engine.over) { this.engine.finish(false); this.state = 'play'; this.show(''); this.endGame(); }
        break;
      case 'menu': this.toMenu(); break;
      case 'tog':
        this.set[k] = !this.set[k]; saveStore(this.store);
        if (k === 'buttons') this.resize();
        this.show('settings'); break;
      case 'seg':
        this.set[k] = +v; saveStore(this.store);
        if (k === 'btnSize') this.resize();
        if (k === 'das') this.applyDas();
        this.show(this.screen); break;
    }
  };

  G.applyDas = function () {
    if (!this.engine) return;
    var d = DAS_OPTS[this.set.das] || DAS_OPTS[1];
    this.engine.das = d[0]; this.engine.arr = d[1];
  };

  // ---------- flow ----------
  G.start = function (mode) {
    var self = this;
    this.releaseAll();
    this.runId++;
    var d = DAS_OPTS[this.set.das] || DAS_OPTS[1];
    this.engine = new Core.Engine({
      mode: mode || 'marathon', goal: mode === 'marathon' ? this.set.goal : 0,
      das: d[0], arr: d[1], seed: B._internal && B._internal.seed != null ? B._internal.seed : undefined,
      onEvent: function (t, a, b) { self.onEv(t, a, b); }
    });
    this.newRecord = false; this.lastRes = null;
    this.acc = 0; this.clearFx();
    this.buildPanel();
    var fast = B._internal && B._internal.fast;
    this.state = fast ? 'play' : 'count';
    this.countT = fast ? 0 : 1.9; this.countLast = 4;
    this.show('');
    this.snd.unlock();
    if (this.set.music > 0) this.snd.musicStart();
    return this.engine;
  };
  G.clearFx = function () {
    var i;
    for (i = 0; i < PARTS; i++) this.parts[i].on = false;
    for (i = 0; i < TRAILS; i++) this.trails[i].on = false;
    for (i = 0; i < POPS; i++) this.pops[i].on = false;
    this.shakeT = 0; this.bounceY = 0; this.bounceV = 0; this.flashA = 0; this.lockFxT = 0; this.ringT = 0;
  };
  G.pause = function () {
    if (this.state !== 'play' && this.state !== 'count') return;
    this.pausedFrom = this.state;
    this.state = 'pause';
    this.releaseAll();
    this.snd.musicStop();
    this.show('pause');
  };
  G.resume = function () {
    if (this.state !== 'pause') return;
    this.state = this.pausedFrom === 'count' ? 'count' : 'play';
    if (this.state === 'play') { this.state = 'count'; this.countT = 0.9; this.countLast = 4; if (B._internal && B._internal.fast) { this.state = 'play'; this.countT = 0; } }
    this.show('');
    if (this.set.music > 0) this.snd.musicStart();
  };
  G.toMenu = function () {
    this.releaseAll();
    this.state = 'menu'; this.engine = null;
    this.snd.musicStop();
    this.show('menu');
  };
  G.releaseAll = function () {
    if (this.engine) { this.engine.input('left', false); this.engine.input('right', false); this.engine.input('soft', false); }
    this.keysDown = {};
    for (var id in this.btnPtr) { var el = this.ctrl.querySelector('[data-b="' + this.btnPtr[id] + '"]'); if (el) el.classList.remove('on'); }
    this.btnPtr = {};
    this.gest.id = null;
  };
  G.endGame = function () {
    var e = this.engine;
    if (!e || this.resultSent === this.runId) return;
    this.resultSent = this.runId;
    var res = e.result();
    this.lastRes = res;
    var st = this.store;
    st.stats.games++; st.stats.lines += res.lines; st.stats.pieces += res.pieces; st.stats.time = Math.round((st.stats.time + res.time) * 100) / 100;
    this.newRecord = false;
    if (res.mode === 'sprint') { if (e.won && (!st.best.sprint || res.time < st.best.sprint)) { st.best.sprint = res.time; this.newRecord = true; } }
    else if (res.score > (st.best[res.mode] || 0)) { st.best[res.mode] = res.score; this.newRecord = res.score > 0; }
    saveStore(st);
    this.releaseAll();
    this.snd.musicStop();
    this.state = 'end'; this.endT = 1.1;
    this.pbtn.style.display = 'none'; this.ctrl.style.display = 'none';
    this.snd.play(e.won ? 'win' : 'over');
    this.hap(e.won ? 'success' : 'error');
    var cb = this.opts.onResult;
    if (typeof cb === 'function') { try { cb(res); } catch (err) { if (window.console) console.error(err); } }
  };

  G.exit = function () {
    if (this.dead) return;
    this.dead = true;
    cancelAnimationFrame(this.raf);
    for (var i = 0; i < this.ls.length; i++) { var l = this.ls[i]; l[0].removeEventListener(l[1], l[2], l[3]); }
    this.ls.length = 0;
    this.snd.close();
    try { var tw = window.Telegram && window.Telegram.WebApp; if (tw && tw.enableVerticalSwipes) tw.enableVerticalSwipes(); } catch (e) { /* ignore */ }
    this.cv.width = 1; this.cv.height = 1;
    this.spr = this.sprM = this.sprS = this.gho = null; this.panel = this.bg = this.blobs = null;
    if (this.root.parentNode) this.root.parentNode.removeChild(this.root);
    document.body.style.overflow = this.prevOverflow;
    this.engine = null;
    if (B.current === this) B.current = null;
    var cb = this.opts.onExit;
    if (typeof cb === 'function') { try { cb(); } catch (err) { if (window.console) console.error(err); } }
  };

  G.hap = function (kind) {
    if (!this.set.haptic) return;
    try {
      var h = window.Telegram && window.Telegram.WebApp && window.Telegram.WebApp.HapticFeedback;
      if (!h) return;
      if (kind === 'success' || kind === 'error' || kind === 'warning') h.notificationOccurred(kind);
      else h.impactOccurred(kind);
    } catch (e) { /* ignore */ }
  };

  // ---------- engine events -> fx ----------
  G.onEv = function (type, a, b) {
    var e = this.engine, L = this.L, i;
    switch (type) {
      case 'move': this.snd.play('move'); break;
      case 'rotate': this.snd.play('rotate'); break;
      case 'soft': this.snd.play('soft'); break;
      case 'hold': this.snd.play('hold'); break;
      case 'hard':
        if (a > 0) {
          var tr = this.trailSlot(), cl = CELLS[e.pt][e.pr];
          tr.on = true; tr.t = 0.32; tr.col = GLOW[e.pt]; tr.n = 0; tr.y0 = b;
          for (i = 0; i < 8; i += 2) {
            var cx = e.px + cl[i], cy = e.py + cl[i + 1], k, found = -1;
            for (k = 0; k < tr.n; k++) if (tr.xs[k] === cx) found = k;
            if (found < 0) { tr.xs[tr.n] = cx; tr.ys[tr.n] = cy; tr.n++; }
            else if (cy < tr.ys[found]) tr.ys[found] = cy;
          }
          this.bounceV += Math.min(5, 1.5 + a * 0.12) * L.c * 0.06 * 10;
        }
        this.snd.play('hard'); this.hap('light');
        break;
      case 'lock':
        for (i = 0; i < 8; i++) this.lockFx[i] = e.lockCells[i];
        this.lockFxT = 0.2; this.lockFxType = a;
        this.bounceV += L.c * 0.6;
        this.snd.play('lock');
        if (b) { this.popup(b === 2 ? 'T-SPIN' : 'MINI T-SPIN', '', '#f0abfc', 0.8); this.snd.play('spin'); }
        break;
      case 'clear':
        var info = b, n = a;
        for (i = 0; i < n; i++) this.burstRow(e.clearRows[i]);
        this.snd.play('clear', n);
        if (n === 4) {
          this.popup('STORM!', info.b2b ? 'B2B ×1.5' : '', '#7dd3fc', 1.6);
          if (this.set.shake) { this.shakeT = 0.55; this.shakeA = L.c * 0.45; }
          this.flashA = 0.55; this.hap('heavy');
        } else if (info.spin) {
          this.popup(['', 'SINGLE', 'DOUBLE', 'TRIPLE'][n] || '', info.b2b ? 'B2B ×1.5' : '', '#f0abfc', 1);
        } else if (n >= 2) {
          this.popup(['', '', 'DOUBLE', 'TRIPLE'][n], '', '#fde68a', 0.9); this.hap('medium');
        }
        if (info.combo > 0) { this.popup('KOMBO ×' + info.combo, '+' + fmt(info.comboPts), '#86efac', 0.75); this.snd.play('combo', info.combo); }
        if (info.b2b) this.snd.play('b2b');
        break;
      case 'levelup':
        this.popup('DARAJA ' + a, 'LEVEL UP', '#fde68a', 1.2);
        this.ringT = 1; this.snd.play('level'); this.hap('medium');
        this.buildPanel();
        break;
      case 'zenclear':
        this.popup('TOZA!', 'Zen davom etadi', '#a5f3fc', 1.1);
        this.snd.play('zen');
        for (i = 0; i < 60; i++) this.spark(L.bx + Math.random() * L.bw, L.by + Math.random() * L.bh, '#a5f3fc', 1);
        break;
      case 'gameover': case 'finish':
        break;
    }
  };
  G.trailSlot = function () {
    var best = this.trails[0];
    for (var i = 0; i < TRAILS; i++) { var t = this.trails[i]; if (!t.on) return t; if (t.t < best.t) best = t; }
    return best;
  };
  G.popup = function (text, sub, col, size) {
    var slot = null, i;
    for (i = 0; i < POPS; i++) if (!this.pops[i].on) { slot = this.pops[i]; break; }
    if (!slot) slot = this.pops[0];
    var stack = 0;
    for (i = 0; i < POPS; i++) if (this.pops[i].on && this.pops[i] !== slot) stack++;
    slot.on = true; slot.t = 0; slot.life = 1.3; slot.text = text; slot.sub = sub; slot.col = col; slot.size = size; slot.y = stack;
  };
  G.spark = function (x, y, col, pw) {
    for (var i = 0; i < PARTS; i++) {
      var p = this.parts[i];
      if (p.on) continue;
      var a = Math.random() * Math.PI * 2, sp = (40 + Math.random() * 260) * pw;
      p.on = true; p.x = x; p.y = y; p.vx = Math.cos(a) * sp; p.vy = Math.sin(a) * sp - 80 * pw;
      p.max = p.life = 0.45 + Math.random() * 0.6; p.s = this.L.c * (0.12 + Math.random() * 0.22); p.col = col; p.g = 520;
      return;
    }
  };
  G.burstRow = function (row) {
    var e = this.engine, L = this.L, c = L.c, vy = row - HID;
    for (var x = 0; x < W; x++) {
      var t = e.board[row * W + x] || 8, cx = L.bx + x * c + c / 2, cy = L.by + vy * c + c / 2;
      for (var k = 0; k < 6; k++) this.spark(cx + (Math.random() - 0.5) * c, cy + (Math.random() - 0.5) * c, Math.random() < 0.3 ? '#ffffff' : GLOW[t], 1);
    }
  };

  // ---------- input: keyboard ----------
  G.onKey = function (e, down) {
    if (this.dead) return;
    var k = e.key, code = e.code;
    var gameKeys = { ArrowLeft: 1, ArrowRight: 1, ArrowDown: 1, ArrowUp: 1, ' ': 1, Spacebar: 1 };
    if (gameKeys[k] && this.state !== 'menu') e.preventDefault();
    if (down) this.snd.unlock();
    if (this.state === 'pause') { if (down && !e.repeat && (k === 'p' || k === 'P' || k === 'Escape')) this.resume(); return; }
    if (this.state !== 'play') {
      if (down && !e.repeat && this.state === 'count' && (k === 'p' || k === 'P' || k === 'Escape')) this.pause();
      if (down && !e.repeat && k === 'Enter' && this.screen === 'menu') this.start(this.set.mode);
      return;
    }
    var en = this.engine; if (!en) return;
    if (k === 'ArrowLeft' || k === 'ArrowRight' || k === 'ArrowDown') {
      var name = k === 'ArrowLeft' ? 'left' : k === 'ArrowRight' ? 'right' : 'soft';
      if (down) { if (this.keysDown[name]) return; this.keysDown[name] = 1; en.input(name, true); }
      else { if (!this.keysDown[name]) return; this.keysDown[name] = 0; en.input(name, false); }
      return;
    }
    if (!down || e.repeat) return;
    if (k === 'ArrowUp' || k === 'x' || k === 'X') this.act('cw');
    else if (k === 'z' || k === 'Z' || k === 'Control') this.act('ccw');
    else if (k === ' ' || k === 'Spacebar' || code === 'Space') this.act('hard');
    else if (k === 'c' || k === 'C' || k === 'Shift') this.act('hold');
    else if (k === 'p' || k === 'P' || k === 'Escape') this.pause();
  };
  G.act = function (a) {
    var en = this.engine;
    if (!en || this.state !== 'play') return false;
    switch (a) {
      case 'cw': return en.rotate(1);
      case 'ccw': return en.rotate(-1);
      case 'hard': return en.hardDrop();
      case 'hold': return en.doHold();
      case 'left': return en.shift(-1);
      case 'right': return en.shift(1);
      case 'soft': return en.softStep();
    }
    return false;
  };

  // ---------- input: on-screen buttons ----------
  G.btnDown = function (e) {
    var t = e.target && e.target.closest ? e.target.closest('[data-b]') : null;
    if (!t) return;
    e.preventDefault(); e.stopPropagation();
    this.snd.unlock();
    var b = t.getAttribute('data-b');
    t.classList.add('on');
    this.btnPtr[e.pointerId] = b;
    if (this.state !== 'play' || !this.engine) return;
    if (b === 'left' || b === 'right' || b === 'soft') this.engine.input(b, true);
    else this.act(b);
  };
  G.btnUp = function (e) {
    var b = this.btnPtr[e.pointerId];
    if (!b) return;
    delete this.btnPtr[e.pointerId];
    var el = this.ctrl.querySelector('[data-b="' + b + '"]'); if (el) el.classList.remove('on');
    if (this.engine && (b === 'left' || b === 'right' || b === 'soft')) {
      var still = false; for (var id in this.btnPtr) if (this.btnPtr[id] === b) still = true;
      if (!still) this.engine.input(b, false);
    }
  };

  // ---------- input: gestures ----------
  G.gDown = function (e) {
    if (this.state !== 'play' || !this.engine) return;
    var g = this.gest;
    if (g.id !== null) return;
    e.preventDefault();
    try { this.cv.setPointerCapture(e.pointerId); } catch (err) { /* synthetic pointer */ }
    var now = e.timeStamp || performance.now();
    g.id = e.pointerId; g.sx = g.ax = g.lx = e.clientX; g.sy = g.ay = g.ly = e.clientY;
    g.t0 = g.lt = now; g.moved = false; g.h = 0; g.v = 0; g.done = false; g.vy = 0;
  };
  G.gMove = function (e) {
    var g = this.gest;
    if (g.id === null || e.pointerId !== g.id) return;
    if (this.state !== 'play' || !this.engine) { g.id = null; return; }
    var x = e.clientX, y = e.clientY, now = e.timeStamp || performance.now(), dt = now - g.lt;
    if (dt > 0) { var inst = (y - g.ly) / dt; g.vy = dt > 60 ? inst : g.vy * 0.4 + inst * 0.6; }
    g.lx = x; g.ly = y; g.lt = now;
    if (g.done) return;
    var cell = Math.max(14, this.L.c * 0.95), dx = x - g.sx, dy = y - g.sy;
    if (!g.moved && dx * dx + dy * dy > 100) g.moved = true;
    if (!g.moved) return;
    if (-dy > cell * 1.6 && Math.abs(dx) < -dy * 0.7 && g.h === 0 && g.v === 0) { g.done = true; this.act('hold'); return; }
    if (dy > cell * 1.3 && g.vy > 1.2 && Math.abs(dx) < dy * 0.8) { g.done = true; this.act('hard'); return; }
    while (x - g.ax >= cell) { g.ax += cell; this.act('right'); g.h++; }
    while (g.ax - x >= cell) { g.ax -= cell; this.act('left'); g.h++; }
    if (y < g.ay) g.ay = y;
    if (g.vy < 1.0) { while (y - g.ay >= cell) { g.ay += cell; this.act('soft'); g.v++; } }
  };
  G.gUp = function (e, cancel) {
    var g = this.gest;
    if (g.id === null || e.pointerId !== g.id) return;
    g.id = null;
    if (cancel || g.done || this.state !== 'play') return;
    var now = e.timeStamp || performance.now(), dur = now - g.t0, dy = e.clientY - g.sy, dx = e.clientX - g.sx;
    var cell = Math.max(14, this.L.c * 0.95);
    if (!g.moved && dur < 400) { this.act('cw'); return; }
    if (dy > cell * 1.0 && g.vy > 0.7 && g.h === 0 && Math.abs(dx) < dy) { this.act('hard'); return; }
    if (-dy > cell * 1.2 && dur < 500 && g.h === 0 && g.v === 0) { this.act('hold'); }
  };

  // ---------- main loop ----------
  G.frame = function (now) {
    if (this.dead) return;
    this.raf = requestAnimationFrame(this.frameFn);
    var dt = (now - this.last) / 1000; this.last = now;
    if (!(dt > 0)) dt = 0; if (dt > 0.1) dt = 0.1;
    this.update(dt);
    this.render(dt);
  };
  G.update = function (dt) {
    if (this.needResize) this.resize();
    this.clock += dt;
    var e = this.engine;
    if (this.state === 'count') {
      this.countT -= dt;
      var n = Math.ceil(this.countT / 0.6);
      if (n !== this.countLast && n > 0 && n <= 3) { this.countLast = n; this.snd.play('count', 0); }
      if (this.countT <= 0) { this.state = 'play'; this.snd.play('count', 1); this.popup('BOSHLA!', '', '#ffffff', 1.1); }
    } else if (this.state === 'play' && e) {
      this.acc += dt;
      while (this.acc >= STEP) {
        e.step(STEP); this.acc -= STEP;
        if (e.over) break;
      }
      if (e.over) this.endGame();
    } else if (this.state === 'end') {
      this.endT -= dt;
      if (this.endT <= 0) { this.state = 'over'; this.show('over'); }
    }
    if (this.state !== 'pause') this.updateFx(dt);
  };
  G.manualStep = function (n) { // test helper: advance logic deterministically
    var e = this.engine;
    for (var i = 0; i < n && e && !e.over; i++) e.step(STEP);
    if (e && e.over && this.state === 'play') this.endGame();
  };

  G.updateFx = function (dt) {
    var i;
    for (i = 0; i < PARTS; i++) {
      var p = this.parts[i]; if (!p.on) continue;
      p.life -= dt; if (p.life <= 0) { p.on = false; continue; }
      p.vy += p.g * dt; p.vx *= (1 - 1.8 * dt); p.x += p.vx * dt; p.y += p.vy * dt;
    }
    for (i = 0; i < TRAILS; i++) { var t = this.trails[i]; if (t.on) { t.t -= dt; if (t.t <= 0) t.on = false; } }
    for (i = 0; i < POPS; i++) { var q = this.pops[i]; if (q.on) { q.t += dt; if (q.t >= q.life) q.on = false; } }
    if (this.shakeT > 0) this.shakeT -= dt;
    if (this.flashA > 0) this.flashA = Math.max(0, this.flashA - dt * 1.6);
    if (this.lockFxT > 0) this.lockFxT -= dt;
    if (this.ringT > 0) this.ringT -= dt * 1.1;
    // damped spring for landing bounce
    var k = 380, d = 22;
    this.bounceV += (-k * this.bounceY - d * this.bounceV) * dt;
    this.bounceY += this.bounceV * dt;
    if (Math.abs(this.bounceY) < 0.01 && Math.abs(this.bounceV) < 0.01) { this.bounceY = 0; this.bounceV = 0; }
    // menu deco
    if (!this.engine) {
      for (i = 0; i < this.deco.length; i++) {
        var o = this.deco[i]; o.y += o.v * dt; o.a += o.va * dt;
        if (o.y > this.H + 80) this.deco[i] = this.newDeco(false);
      }
    }
  };
  G.newDeco = function (init) {
    var Wp = this.W || 400, Hp = this.H || 700;
    return { t: 1 + Math.floor(Math.random() * 7), x: Math.random() * Wp, y: init ? Math.random() * Hp : -80 - Math.random() * 200, v: 18 + Math.random() * 40, a: Math.random() * 6.28, va: (Math.random() - 0.5) * 0.6, s: 0.6 + Math.random() * 0.8, al: 0.12 + Math.random() * 0.25 };
  };

  // ---------- rendering ----------
  G.render = function () {
    var ctx = this.ctx, L = this.L, dpr = this.dpr, Wp = this.W, Hp = this.H, i;
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    ctx.globalAlpha = 1;
    ctx.drawImage(this.bg, 0, 0, Wp, Hp);
    // drifting blobs
    var tt = this.clock, m = Math.max(Wp, Hp);
    ctx.globalCompositeOperation = 'lighter';
    for (i = 0; i < 3; i++) {
      var bx = Wp * (0.5 + 0.42 * Math.sin(tt * (0.05 + i * 0.023) + i * 2.1)), by = Hp * (0.5 + 0.4 * Math.cos(tt * (0.04 + i * 0.017) + i * 1.3));
      var sz = m * (0.75 + 0.15 * Math.sin(tt * 0.1 + i));
      ctx.globalAlpha = 0.55; ctx.drawImage(this.blobs[i], bx - sz / 2, by - sz / 2, sz, sz);
    }
    ctx.globalCompositeOperation = 'source-over';
    // storm rain
    var rn = this.rain; ctx.globalAlpha = 1; ctx.strokeStyle = 'rgba(160,190,255,0.10)'; ctx.lineWidth = 1; ctx.beginPath();
    for (i = 0; i < 48; i++) {
      var o = i * 4, sp = rn[o + 3];
      var ry = ((rn[o + 1] + tt * 0.25 * sp) % 1.2 - 0.1) * Hp, rx = ((rn[o] + tt * 0.04 * sp) % 1.1 - 0.05) * Wp, ln = rn[o + 2] * 26;
      ctx.moveTo(rx, ry); ctx.lineTo(rx - ln * 0.25, ry + ln);
    }
    ctx.stroke();
    if (this.flashA > 0) { ctx.fillStyle = 'rgba(200,225,255,' + (this.flashA * 0.35).toFixed(3) + ')'; ctx.fillRect(0, 0, Wp, Hp); }

    if (!this.engine) { this.renderDeco(); return; }
    var e = this.engine, c = L.c;
    ctx.save();
    var sx = 0, sy = 0;
    if (this.shakeT > 0) { var a = this.shakeA * Math.min(1, this.shakeT / 0.55); sx = (Math.random() - 0.5) * 2 * a; sy = (Math.random() - 0.5) * 2 * a; }
    ctx.translate(Math.round(sx), Math.round(sy + this.bounceY));
    if (this.panelLevel !== e.level) this.buildPanel();
    ctx.drawImage(this.panel, L.bx - this.panelOff, L.by - this.panelOff, this.panelW, this.panelH);
    // danger glow
    var hi = this.stackTop(e);
    var dangerT = hi < HID + 4 ? 1 : 0;
    this.danger += (dangerT - this.danger) * 0.08;
    if (this.danger > 0.02) {
      ctx.globalAlpha = this.danger * (0.45 + 0.25 * Math.sin(tt * 7));
      ctx.strokeStyle = '#ff3b5c'; ctx.lineWidth = 3; rr(ctx, L.bx - 3, L.by - 3, L.bw + 6, L.bh + 6, 6); ctx.stroke();
      ctx.globalAlpha = 1;
    }
    // level ring
    if (this.ringT > 0) {
      var rp = 1 - this.ringT;
      ctx.globalAlpha = this.ringT * 0.8; ctx.strokeStyle = '#fde68a'; ctx.lineWidth = 3 + 6 * this.ringT;
      ctx.beginPath(); ctx.arc(L.bx + L.bw / 2, L.by + L.bh / 2, L.bh * 0.1 + rp * L.bh * 0.7, 0, Math.PI * 2); ctx.stroke();
      ctx.globalAlpha = 1;
    }
    var spr = this.spr, b = e.board, over = this.state === 'end' || this.state === 'over';
    var greyRows = over ? Math.min(20, Math.floor((1 - Math.max(0, this.endT) / 1.1) * 26)) : 0;
    // locked cells
    var clearing = e.clearT > 0, cf = clearing ? e.clearT / e.clearDelay : 0;
    for (var y = HID; y < H; y++) {
      var isClr = false;
      if (clearing) for (var q = 0; q < e.clearN; q++) if (e.clearRows[q] === y) isClr = true;
      var py = L.by + (y - HID) * c;
      var grey = over && (H - 1 - y) < greyRows;
      for (var x = 0; x < W; x++) {
        var v = b[y * W + x]; if (!v) continue;
        var px = L.bx + x * c;
        if (isClr) {
          var s = c * cf, off = (c - s) / 2;
          if (s > 0.5) ctx.drawImage(spr[v], px + off, py + off, s, s);
          continue;
        }
        ctx.drawImage(spr[grey ? 8 : v], px, py, c, c);
      }
      if (isClr) {
        ctx.globalAlpha = Math.min(1, cf * 1.6) * 0.9; ctx.fillStyle = '#ffffff';
        ctx.fillRect(L.bx, py + c * (1 - cf) * 0.5, L.bw, c * cf); ctx.globalAlpha = 1;
      }
    }
    // hard drop trails
    for (i = 0; i < TRAILS; i++) {
      var tr = this.trails[i]; if (!tr.on) continue;
      var al = tr.t / 0.32;
      for (var k = 0; k < tr.n; k++) {
        var ty0 = L.by + (Math.max(tr.y0, HID - 1) - HID) * c, ty1 = L.by + (tr.ys[k] - HID) * c;
        if (ty1 <= ty0) continue;
        var gr = ctx.createLinearGradient(0, ty0, 0, ty1);
        gr.addColorStop(0, rgba(tr.col, 0)); gr.addColorStop(1, rgba(tr.col, 0.55 * al));
        ctx.fillStyle = gr; ctx.fillRect(L.bx + tr.xs[k] * c + c * 0.12, ty0, c * 0.76, ty1 - ty0);
      }
    }
    // ghost + active piece
    if (e.pt && !over) {
      var cl = CELLS[e.pt][e.pr];
      if (this.set.ghost && e.ghostY > e.py) {
        for (i = 0; i < 8; i += 2) {
          var gy = e.ghostY + cl[i + 1]; if (gy < HID) continue;
          ctx.drawImage(this.gho[e.pt], L.bx + (e.px + cl[i]) * c, L.by + (gy - HID) * c, c, c);
        }
      }
      var fy = this.set.smooth ? e.fallFrac() * c : 0;
      var lockGlow = e.landed && e.grounded() ? Math.min(1, e.lockT / e.lockDelay) : 0;
      for (i = 0; i < 8; i += 2) {
        var ay = e.py + cl[i + 1]; if (ay < HID) continue;
        var ax = L.bx + (e.px + cl[i]) * c, ayy = L.by + (ay - HID) * c + fy;
        ctx.drawImage(spr[e.pt], ax, ayy, c, c);
        if (lockGlow > 0) { ctx.globalAlpha = lockGlow * 0.35; ctx.drawImage(this.flashSpr, ax, ayy, c, c); ctx.globalAlpha = 1; }
      }
    }
    // lock flash ("landing squash" pop)
    if (this.lockFxT > 0 && !over) {
      var lf = this.lockFxT / 0.2;
      ctx.globalAlpha = lf * 0.55;
      for (i = 0; i < 8; i += 2) {
        var ly = this.lockFx[i + 1]; if (ly < HID) continue;
        var ex = (1 - lf) * c * 0.12;
        ctx.drawImage(this.flashSpr, L.bx + this.lockFx[i] * c - ex, L.by + (ly - HID) * c + ex * 1.5, c + ex * 2, c - ex * 1.5);
      }
      ctx.globalAlpha = 1;
    }
    ctx.restore();
    this.renderHud(e);
    // particles
    for (i = 0; i < PARTS; i++) {
      var p = this.parts[i]; if (!p.on) continue;
      var pa = p.life / p.max;
      ctx.globalAlpha = pa; ctx.fillStyle = p.col;
      var ps = p.s * (0.5 + pa * 0.5);
      ctx.fillRect(p.x - ps / 2, p.y - ps / 2, ps, ps);
    }
    ctx.globalAlpha = 1;
    this.renderPops();
    if (this.state === 'count') {
      var nn = Math.ceil(this.countT / 0.6), fr = (this.countT / 0.6) % 1;
      if (nn >= 1 && nn <= 3) {
        ctx.save(); ctx.globalAlpha = Math.min(1, fr * 2.5);
        ctx.font = '900 ' + Math.round(c * 4 * (0.8 + fr * 0.4)) + 'px system-ui,-apple-system,Segoe UI,Roboto,sans-serif';
        ctx.textAlign = 'center'; ctx.textBaseline = 'middle';
        ctx.shadowColor = '#7dd3fc'; ctx.shadowBlur = 24; ctx.fillStyle = '#fff';
        ctx.fillText(String(nn), L.bx + L.bw / 2, L.by + L.bh * 0.42);
        ctx.restore();
      }
    }
    if (this.state === 'pause' || this.state === 'over') { ctx.fillStyle = 'rgba(4,5,14,0.45)'; ctx.fillRect(0, 0, Wp, Hp); }
  };
  G.stackTop = function (e) {
    var b = e.board;
    for (var y = 0; y < H; y++) for (var x = 0; x < W; x++) if (b[y * W + x]) return y;
    return H;
  };
  G.renderDeco = function () {
    var ctx = this.ctx, s0 = Math.max(16, Math.min(this.W, this.H) / 16), i, k;
    for (i = 0; i < this.deco.length; i++) {
      var o = this.deco[i], cl = CELLS[o.t][0], n = Core.BOXN[o.t], s = s0 * o.s;
      ctx.save(); ctx.globalAlpha = o.al; ctx.translate(o.x, o.y); ctx.rotate(o.a);
      for (k = 0; k < 8; k += 2) ctx.drawImage(this.spr[o.t], (cl[k] - n / 2) * s, (cl[k + 1] - n / 2) * s, s, s);
      ctx.restore();
    }
  };
  G.renderPiece = function (t, cx, cy, sz, sprs, alpha) {
    var pv = PREV[t], ctx = this.ctx;
    var ox = cx - pv.w * sz / 2, oy = cy - pv.h * sz / 2;
    if (alpha < 1) ctx.globalAlpha = alpha;
    for (var i = 0; i < 8; i += 2) ctx.drawImage(sprs[t], Math.round(ox + (pv.c[i] - pv.x0) * sz), Math.round(oy + (pv.c[i + 1] - pv.y0) * sz), sz, sz);
    ctx.globalAlpha = 1;
  };
  G.box = function (r, label) {
    var ctx = this.ctx;
    ctx.fillStyle = 'rgba(14,16,40,0.72)'; rr(ctx, r.x, r.y, r.w, r.h, 10); ctx.fill();
    ctx.strokeStyle = 'rgba(160,180,255,0.18)'; ctx.lineWidth = 1; ctx.stroke();
    if (label) {
      ctx.fillStyle = 'rgba(200,210,255,0.62)';
      ctx.font = '800 ' + Math.max(9, Math.round(this.L.c * 0.42)) + 'px system-ui,-apple-system,Segoe UI,Roboto,sans-serif';
      ctx.textAlign = 'left'; ctx.textBaseline = 'top';
      ctx.fillText(label, r.x + 8, r.y + 6);
    }
  };
  G.renderHud = function (e) {
    var ctx = this.ctx, L = this.L, c = L.c, F = 'system-ui,-apple-system,Segoe UI,Roboto,sans-serif';
    // hold
    var h = L.hold;
    this.box(h, 'HOLD');
    if (e.hold) {
      var hs = Math.round(c * 0.62), cy = h.y + h.h / 2 + c * 0.32;
      this.renderPiece(e.hold, h.x + h.w / 2, cy, Math.min(hs, Math.floor((h.h - c * 0.7) / 2.2)), this.sprM, e.holdUsed ? 0.3 : 1);
    }
    // next
    var nx = L.next, sz1 = Math.round(c * 0.62), sz2 = Math.round(c * 0.5);
    var lab = Math.round(c * 0.9), slot1 = c * 2.4, slot = c * 1.85;
    nx.h = Math.round(lab + slot1 + slot * 4 + c * 0.3);
    this.box(nx, 'NEXT');
    for (var i = 0; i < 5; i++) {
      var t = e.queue[i]; if (!t) continue;
      var yy = i === 0 ? nx.y + lab + slot1 / 2 : nx.y + lab + slot1 + slot * (i - 1) + slot / 2;
      this.renderPiece(t, nx.x + nx.w / 2, yy, i === 0 ? sz1 : sz2, i === 0 ? this.sprM : this.sprS, i === 0 ? 1 : 0.85);
    }
    // stats
    var s = L.stats, sprint = e.mode === 'sprint';
    ctx.textBaseline = 'alphabetic';
    if (!L.land) {
      ctx.textAlign = 'left';
      var big = Math.max(16, Math.round(Math.min(c * 1.05, s.h * 0.42)));
      ctx.fillStyle = 'rgba(200,210,255,0.6)'; ctx.font = '800 ' + Math.max(9, Math.round(c * 0.4)) + 'px ' + F;
      ctx.fillText(sprint ? 'VAQT' : 'OCHKO', s.x, s.y + Math.round(c * 0.5));
      ctx.fillStyle = '#fff'; ctx.font = '900 ' + big + 'px ' + F;
      ctx.shadowColor = rgba(this.panelCol[0], 0.8); ctx.shadowBlur = 10;
      ctx.fillText(sprint ? fmtTime(e.time) : fmt(e.score), s.x, s.y + Math.round(c * 0.5) + big);
      ctx.shadowBlur = 0;
      ctx.font = '700 ' + Math.max(10, Math.round(c * 0.46)) + 'px ' + F; ctx.fillStyle = 'rgba(220,228,255,0.85)';
      var line2 = sprint ? ('QATOR ' + e.lines + '/40 · ' + fmt(e.score)) : ('DARAJA ' + e.level + ' · QATOR ' + e.lines + (e.mode === 'zen' ? ' · ' + fmtTime(e.time) : ''));
      ctx.fillText(line2, s.x, s.y + h.h - Math.round(c * 0.2));
    } else {
      this.box(s, '');
      var rows = sprint ? [['VAQT', fmtTime(e.time)], ['QATOR', e.lines + '/40'], ['OCHKO', fmt(e.score)]]
        : [['OCHKO', fmt(e.score)], ['DARAJA', String(e.level)], ['QATOR', String(e.lines)], ['VAQT', fmtTime(e.time)]];
      var yy2 = s.y + c * 0.5, lsz = Math.max(9, Math.round(c * 0.42)), vsz = Math.max(12, Math.round(c * 0.85));
      ctx.textAlign = 'left';
      for (var r = 0; r < rows.length; r++) {
        ctx.fillStyle = 'rgba(200,210,255,0.6)'; ctx.font = '800 ' + lsz + 'px ' + F; ctx.fillText(rows[r][0], s.x + 10, yy2 + lsz);
        ctx.fillStyle = '#fff'; ctx.font = '900 ' + vsz + 'px ' + F; ctx.fillText(rows[r][1], s.x + 10, yy2 + lsz + vsz * 1.05);
        yy2 += lsz + vsz * 1.5;
      }
      s.h = Math.round(yy2 - s.y);
    }
  };
  G.renderPops = function () {
    var ctx = this.ctx, L = this.L, c = L.c, F = 'system-ui,-apple-system,Segoe UI,Roboto,sans-serif';
    ctx.save(); ctx.textAlign = 'center'; ctx.textBaseline = 'middle';
    for (var i = 0; i < POPS; i++) {
      var p = this.pops[i]; if (!p.on) continue;
      var k = p.t / p.life, a = k < 0.12 ? k / 0.12 : (k > 0.7 ? (1 - k) / 0.3 : 1);
      var sc = k < 0.12 ? 0.6 + 0.6 * (k / 0.12) : 1.2 - Math.min(0.2, (k - 0.12) * 0.5);
      var sz = Math.round(c * 1.25 * p.size * sc), x = L.bx + L.bw / 2, y = L.by + L.bh * 0.3 + p.y * c * 1.9 - k * c * 0.8;
      ctx.globalAlpha = Math.max(0, a);
      ctx.font = '900 italic ' + sz + 'px ' + F;
      var tw = ctx.measureText(p.text).width;
      if (tw > L.bw * 0.9) { sz = Math.floor(sz * L.bw * 0.9 / tw); ctx.font = '900 italic ' + sz + 'px ' + F; }
      ctx.shadowColor = p.col; ctx.shadowBlur = 18;
      ctx.lineWidth = Math.max(2, sz * 0.09); ctx.strokeStyle = 'rgba(10,8,30,0.85)';
      ctx.strokeText(p.text, x, y);
      ctx.fillStyle = p.col; ctx.fillText(p.text, x, y);
      if (p.sub) {
        ctx.shadowBlur = 8; ctx.font = '800 ' + Math.round(c * 0.55) + 'px ' + F; ctx.fillStyle = '#ffffff';
        ctx.fillText(p.sub, x, y + sz * 0.72);
      }
    }
    ctx.restore();
  };

  // ---------- public API ----------
  B.VERSION = VERSION;
  B.current = B.current || null;
  B.launch = function (opts) {
    if (B.current) { try { B.current.exit(); } catch (e) { /* ignore */ } }
    var g = new Game(opts || {});
    B.current = g;
    return g;
  };
  B._internal = {
    fast: false, seed: null, Core: Core, Engine: Core.Engine, STEP: STEP,
    game: function () { return B.current; },
    load: loadStore, KEY: STORE_KEY
  };
})();
