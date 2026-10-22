/* NEON SNAKE — game, renderer, audio and UI. Requires ns_core.js. Original game. */
(function () {
  'use strict';
  var C = window.NSNK_CORE;
  if (!C) { throw new Error('NEON SNAKE: ns_core.js must be loaded first'); }
  var VERSION = '1.0.0';
  var W = C.W, H = C.H, DX = C.DX, DY = C.DY, MODES = C.MODES;
  var LS_KEY = 'neon_snake_v1';
  var MODE_NAME = { classic: 'Classic', portal: 'Portal', maze: 'Maze' };
  var PU_NAME = ['SEKIN VAQT', 'ARVOH', 'MAGNIT'];
  var PU_ICON = ['⏱', '\u{1F47B}', '\u{1F9F2}'];
  // palette indices: 0 cyan 1 magenta 2 lime 3 gold 4 blue 5 violet 6 red 7 white
  var COLORS = ['#22f3ff', '#ff2bd6', '#9dff3a', '#ffd34d', '#4db8ff', '#b892ff', '#ff4d6d', '#ffffff'];
  var PU_COL = [4, 5, 6];
  var current = null;

  function esc(s) {
    return String(s == null ? '' : s).replace(/[&<>"']/g, function (c) {
      return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c];
    });
  }
  function clamp(v, a, b) { return v < a ? a : v > b ? b : v; }
  function fmtTime(sec) { sec = Math.floor(sec); var m = Math.floor(sec / 60), s = sec % 60; return m + ':' + (s < 10 ? '0' : '') + s; }
  function hexRgb(h) { return [parseInt(h.substr(1, 2), 16), parseInt(h.substr(3, 2), 16), parseInt(h.substr(5, 2), 16)]; }

  // ---------- storage ----------
  function defaults() {
    return { v: 2, mode: 'classic', music: 50, sfx: 80, dpad: true, haptics: true, shake: true,
      best: { classic: 0, portal: 0, maze: 0 }, stats: { games: 0, foods: 0, golds: 0, time: 0 }, mazeMax: 1 };
  }
  function loadStore() {
    var d = defaults();
    try {
      var raw = window.localStorage.getItem(LS_KEY);
      if (raw) {
        var o = JSON.parse(raw);
        if (o && typeof o === 'object') {
          if (MODES.indexOf(o.mode) >= 0) d.mode = o.mode;
          if (typeof o.music === 'number') d.music = clamp(Math.round(o.music), 0, 100);
          if (typeof o.sfx === 'number') d.sfx = clamp(Math.round(o.sfx), 0, 100);
          d.dpad = (+o.v || 1) >= 2 ? o.dpad !== false : true;   // v2: tugmalar standart yoniq (eski saqlanganlar ham) d.haptics = o.haptics !== false; d.shake = o.shake !== false;
          if (o.best) for (var i = 0; i < MODES.length; i++) d.best[MODES[i]] = Math.max(0, +o.best[MODES[i]] || 0);
          if (o.stats) { d.stats.games = +o.stats.games || 0; d.stats.foods = +o.stats.foods || 0; d.stats.golds = +o.stats.golds || 0; d.stats.time = +o.stats.time || 0; }
          d.mazeMax = Math.max(1, +o.mazeMax || 1);
        }
      }
    } catch (e) { /* storage unavailable */ }
    return d;
  }
  function saveStore(d) { try { window.localStorage.setItem(LS_KEY, JSON.stringify(d)); } catch (e) { /* ignore */ } }

  // ---------- audio (Web Audio synthesis) ----------
  function Sound(store) {
    this.store = store; this.ctx = null; this.master = null; this.sfx = null; this.mus = null;
    this.noise = null; this.timer = 0; this.nextT = 0; this.stepI = 0; this.duck = 1; this.closed = false;
  }
  Sound.prototype.unlock = function () {
    if (this.closed) return;
    try {
      if (!this.ctx) {
        var AC = window.AudioContext || window.webkitAudioContext;
        if (!AC) return;
        var ctx = this.ctx = new AC();
        this.master = ctx.createGain(); this.master.gain.value = 0.9;
        var comp = ctx.createDynamicsCompressor();
        this.master.connect(comp); comp.connect(ctx.destination);
        this.sfx = ctx.createGain(); this.sfx.connect(this.master);
        this.mus = ctx.createGain(); this.mus.connect(this.master);
        this.musLp = ctx.createBiquadFilter(); this.musLp.type = 'lowpass'; this.musLp.frequency.value = 2400;
        this.musLp.connect(this.mus);
        this.dly = ctx.createDelay(1); this.dly.delayTime.value = 0.39;
        this.fb = ctx.createGain(); this.fb.gain.value = 0.32;
        this.dly.connect(this.fb); this.fb.connect(this.dly); this.dly.connect(this.musLp);
        var len = (ctx.sampleRate * 0.5) | 0, buf = ctx.createBuffer(1, len, ctx.sampleRate), ch = buf.getChannelData(0);
        for (var i = 0; i < len; i++) ch[i] = Math.random() * 2 - 1;
        this.noise = buf;
        this.applyVol();
        var self = this;
        this.timer = setInterval(function () { self.sched(); }, 100);
      }
      if (this.ctx.state === 'suspended') this.ctx.resume();
    } catch (e) { /* audio unavailable */ }
  };
  Sound.prototype.applyVol = function () {
    if (!this.ctx) return;
    var t = this.ctx.currentTime;
    this.sfx.gain.setTargetAtTime(this.store.sfx / 100 * 0.9, t, 0.02);
    this.mus.gain.setTargetAtTime(this.store.music / 100 * 0.6 * this.duck, t, 0.15);
  };
  Sound.prototype.setDuck = function (d) { this.duck = d; this.applyVol(); };
  Sound.prototype.suspend = function () { try { if (this.ctx && this.ctx.state === 'running') this.ctx.suspend(); } catch (e) {} };
  Sound.prototype.resume = function () { try { if (this.ctx && this.ctx.state === 'suspended') this.ctx.resume(); } catch (e) {} };
  Sound.prototype.close = function () {
    this.closed = true;
    if (this.timer) { clearInterval(this.timer); this.timer = 0; }
    try { if (this.ctx) this.ctx.close(); } catch (e) {}
    this.ctx = null;
  };
  Sound.prototype.tone = function (type, f0, f1, dur, vol, delay, dest) {
    var ctx = this.ctx; if (!ctx || ctx.state !== 'running') return;
    var t = ctx.currentTime + (delay || 0);
    var o = ctx.createOscillator(), g = ctx.createGain();
    o.type = type; o.frequency.setValueAtTime(f0, t);
    if (f1) o.frequency.exponentialRampToValueAtTime(f1, t + dur);
    g.gain.setValueAtTime(0.0001, t);
    g.gain.exponentialRampToValueAtTime(vol, t + 0.008);
    g.gain.exponentialRampToValueAtTime(0.0001, t + dur);
    o.connect(g); g.connect(dest || this.sfx);
    o.start(t); o.stop(t + dur + 0.03);
  };
  Sound.prototype.burst = function (dur, vol, f) {
    var ctx = this.ctx; if (!ctx || ctx.state !== 'running' || !this.noise) return;
    var t = ctx.currentTime, s = ctx.createBufferSource(), g = ctx.createGain(), bq = ctx.createBiquadFilter();
    s.buffer = this.noise; bq.type = 'lowpass'; bq.frequency.setValueAtTime(f || 2000, t);
    bq.frequency.exponentialRampToValueAtTime(120, t + dur);
    g.gain.setValueAtTime(vol, t); g.gain.exponentialRampToValueAtTime(0.0001, t + dur);
    s.connect(bq); bq.connect(g); g.connect(this.sfx); s.start(t); s.stop(t + dur + 0.02);
  };
  Sound.prototype.play = function (name, v) {
    if (!this.ctx || this.store.sfx <= 0) return;
    var k;
    switch (name) {
      case 'eat': k = 520 * Math.pow(2, ((v || 1) - 1) / 12);
        this.tone('sine', k, k * 1.6, 0.11, 0.3); this.tone('triangle', k * 2, k * 2.4, 0.07, 0.08, 0.02); break;
      case 'gold': this.tone('triangle', 784, 0, 0.14, 0.2); this.tone('triangle', 988, 0, 0.14, 0.2, 0.07);
        this.tone('triangle', 1319, 0, 0.25, 0.22, 0.14); this.tone('sine', 2637, 0, 0.3, 0.05, 0.14); break;
      case 'pu': this.tone('square', 260, 1100, 0.28, 0.07); this.tone('sine', 520, 2100, 0.3, 0.15, 0.03); break;
      case 'mult': this.tone('sine', 880 + v * 60, 0, 0.08, 0.08, 0.05); break;
      case 'tick': this.tone('sine', 1650, 0, 0.025, 0.035); break;
      case 'die': this.tone('sawtooth', 420, 55, 0.7, 0.2); this.tone('square', 210, 40, 0.5, 0.08, 0.05); this.burst(0.45, 0.35, 2600); break;
      case 'level': this.tone('square', 523, 0, 0.12, 0.08); this.tone('square', 659, 0, 0.12, 0.08, 0.09);
        this.tone('square', 784, 0, 0.12, 0.08, 0.18); this.tone('triangle', 1047, 0, 0.4, 0.2, 0.27); break;
      case 'gone': this.tone('sine', 700, 300, 0.18, 0.06); break;
      case 'ui': this.tone('sine', 880, 1320, 0.06, 0.07); break;
      case 'go': this.tone('triangle', 660, 0, 0.1, 0.15); this.tone('triangle', 990, 0, 0.18, 0.15, 0.08); break;
      case 'count': this.tone('sine', 440, 0, 0.09, 0.12); break;
    }
  };
  // calm synth loop: Am - F - C - G
  var CHORDS = [[57, 60, 64], [53, 57, 60], [55, 60, 64], [55, 59, 62]];
  var ROOTS = [33, 29, 36, 31];
  var ARP = [0, 1, 2, 1, 0, 2, 1, 2];
  var EIGHTH = 60 / 92 / 2;
  function mtof(m) { return 440 * Math.pow(2, (m - 69) / 12); }
  Sound.prototype.sched = function () {
    var ctx = this.ctx;
    if (!ctx || ctx.state !== 'running' || this.store.music <= 0) { if (ctx) this.nextT = 0; return; }
    var now = ctx.currentTime;
    if (this.nextT < now) this.nextT = now + 0.06;
    while (this.nextT < now + 0.35) { this.musicStep(this.stepI, this.nextT); this.stepI = (this.stepI + 1) % 32; this.nextT += EIGHTH; }
  };
  Sound.prototype.note = function (type, f, t, dur, vol, att, toDelay) {
    var ctx = this.ctx, o = ctx.createOscillator(), g = ctx.createGain();
    o.type = type; o.frequency.value = f;
    g.gain.setValueAtTime(0.0001, t);
    g.gain.linearRampToValueAtTime(vol, t + att);
    g.gain.exponentialRampToValueAtTime(0.0001, t + dur);
    o.connect(g); g.connect(this.musLp); if (toDelay) g.connect(this.dly);
    o.start(t); o.stop(t + dur + 0.05);
  };
  Sound.prototype.musicStep = function (i, t) {
    var ci = (i >> 3) & 3, ch = CHORDS[ci], j = i & 7;
    if (j === 0) {
      for (var k = 0; k < 3; k++) { this.note('triangle', mtof(ch[k]), t, EIGHTH * 8.2, 0.035, 0.5, false); this.note('sine', mtof(ch[k]) * 1.005, t, EIGHTH * 8.2, 0.02, 0.7, false); }
    }
    if (j === 0 || j === 4) this.note('sine', mtof(ROOTS[ci]), t, EIGHTH * 3.5, 0.11, 0.02, false);
    if (j !== 3 && j !== 7) this.note('sine', mtof(ch[ARP[j]] + 12), t, 0.32, 0.03, 0.01, true);
  };

  // ---------- sprites ----------
  function mkCanvas(w, h) { var c = document.createElement('canvas'); c.width = Math.max(1, w | 0); c.height = Math.max(1, h | 0); return c; }
  function glowSprite(col) {
    var s = 64, c = mkCanvas(s, s), x = c.getContext('2d'), rgb = hexRgb(col);
    var g = x.createRadialGradient(32, 32, 0, 32, 32, 32);
    g.addColorStop(0, 'rgba(' + rgb + ',0.9)'); g.addColorStop(0.25, 'rgba(' + rgb + ',0.45)');
    g.addColorStop(1, 'rgba(' + rgb + ',0)');
    x.fillStyle = g; x.fillRect(0, 0, s, s);
    return c;
  }
  function itemSprite(kind, cs) {
    var S = Math.ceil(cs * 2.4), c = mkCanvas(S, S), x = c.getContext('2d'), m = S / 2, r = cs * 0.36;
    var col = kind === 'food' ? COLORS[2] : kind === 'gold' ? COLORS[3] : COLORS[PU_COL[kind]];
    var rgb = hexRgb(col);
    var g = x.createRadialGradient(m, m, 0, m, m, m);
    g.addColorStop(0, 'rgba(' + rgb + ',0.55)'); g.addColorStop(0.35, 'rgba(' + rgb + ',0.18)'); g.addColorStop(1, 'rgba(' + rgb + ',0)');
    x.fillStyle = g; x.fillRect(0, 0, S, S);
    x.shadowColor = col; x.shadowBlur = cs * 0.4;
    if (kind === 'gold') {
      x.beginPath();
      for (var i = 0; i < 10; i++) { var a = -Math.PI / 2 + i * Math.PI / 5, rr = i & 1 ? r * 0.5 : r * 1.15; x.lineTo(m + Math.cos(a) * rr, m + Math.sin(a) * rr); }
      x.closePath();
      var gg = x.createLinearGradient(m - r, m - r, m + r, m + r); gg.addColorStop(0, '#fff6c2'); gg.addColorStop(0.5, '#ffd34d'); gg.addColorStop(1, '#ff9d1c');
      x.fillStyle = gg; x.fill();
    } else if (kind === 'food') {
      x.beginPath(); x.arc(m, m, r, 0, Math.PI * 2);
      var fg = x.createRadialGradient(m - r * 0.35, m - r * 0.35, r * 0.1, m, m, r); fg.addColorStop(0, '#f4ffd8'); fg.addColorStop(0.45, '#9dff3a'); fg.addColorStop(1, '#3fae00');
      x.fillStyle = fg; x.fill();
      x.shadowBlur = 0; x.strokeStyle = '#d6ff9c'; x.lineWidth = Math.max(1, cs * 0.07);
      x.beginPath(); x.moveTo(m, m - r); x.quadraticCurveTo(m + r * 0.2, m - r * 1.45, m + r * 0.6, m - r * 1.35); x.stroke();
    } else {
      x.beginPath(); x.arc(m, m, r * 1.05, 0, Math.PI * 2); x.fillStyle = 'rgba(10,14,30,0.9)'; x.fill();
      x.lineWidth = Math.max(1.5, cs * 0.1); x.strokeStyle = col; x.stroke();
      x.shadowBlur = 0; x.fillStyle = col; x.strokeStyle = col; x.lineCap = 'round';
      if (kind === 0) { // clock
        x.lineWidth = Math.max(1, cs * 0.08);
        x.beginPath(); x.moveTo(m, m); x.lineTo(m, m - r * 0.6); x.moveTo(m, m); x.lineTo(m + r * 0.45, m + r * 0.1); x.stroke();
      } else if (kind === 1) { // ghost
        x.beginPath(); x.arc(m, m - r * 0.1, r * 0.5, Math.PI, 0);
        x.lineTo(m + r * 0.5, m + r * 0.5); x.lineTo(m + r * 0.25, m + r * 0.32); x.lineTo(m, m + r * 0.5); x.lineTo(m - r * 0.25, m + r * 0.32); x.lineTo(m - r * 0.5, m + r * 0.5);
        x.closePath(); x.fill();
        x.fillStyle = '#0a0e1e'; x.beginPath(); x.arc(m - r * 0.18, m - r * 0.1, r * 0.1, 0, 7); x.arc(m + r * 0.18, m - r * 0.1, r * 0.1, 0, 7); x.fill();
      } else { // magnet
        x.lineWidth = Math.max(2, cs * 0.16);
        x.beginPath(); x.arc(m, m, r * 0.45, Math.PI, 0, true); x.stroke();
        x.beginPath(); x.moveTo(m - r * 0.45, m); x.lineTo(m - r * 0.45, m - r * 0.45); x.moveTo(m + r * 0.45, m); x.lineTo(m + r * 0.45, m - r * 0.45);
        x.strokeStyle = '#ffffff'; x.stroke();
      }
    }
    return c;
  }
  function mixHex(a, b, t) {
    var A = hexRgb(a), B = hexRgb(b);
    return 'rgb(' + Math.round(A[0] + (B[0] - A[0]) * t) + ',' + Math.round(A[1] + (B[1] - A[1]) * t) + ',' + Math.round(A[2] + (B[2] - A[2]) * t) + ')';
  }
  var BODY_PAL = []; (function () { for (var i = 0; i < 32; i++) BODY_PAL.push(i < 16 ? mixHex('#3ff8ff', '#4d8dff', i / 15) : mixHex('#4d8dff', '#ff2bd6', (i - 16) / 15)); })();
  var GHOST_PAL = []; (function () { for (var i = 0; i < 32; i++) GHOST_PAL.push(mixHex('#d8ccff', '#8a5cff', i / 31)); })();

  // ---------- game ----------
  function createGame(opts) {
    opts = opts || {};
    var G = {}, store = loadStore(), snd = new Sound(store);
    var listeners = [], raf = 0, exited = false, resultSent = false;
    var prevOverflow = document.body.style.overflow;
    document.body.style.overflow = 'hidden';
    try { var tw = window.Telegram && window.Telegram.WebApp; if (tw && tw.disableVerticalSwipes) tw.disableVerticalSwipes(); } catch (e) {}

    function on(t, type, fn, o) { t.addEventListener(type, fn, o); listeners.push([t, type, fn, o]); }

    var root = document.createElement('div');
    root.className = 'nsnk';
    root.innerHTML =
      '<div class="ns-bgw"><div class="ns-bg"></div></div><canvas class="ns-cv"></canvas>' +
      '<div class="ns-safe"></div>' +
      '<div class="ns-hud">' +
        '<div class="ns-hb ns-hs"><small>BALL</small><b data-h="score">0</b></div>' +
        '<div class="ns-hb ns-hm"><small>KOMBO</small><b data-h="mult">x1</b><i><u data-h="combo"></u></i></div>' +
        '<div class="ns-hb"><small>UZUNLIK</small><b data-h="len">4</b></div>' +
        '<div class="ns-hb"><small>REKORD</small><b data-h="best">0</b></div>' +
        '<button class="ns-pbtn" data-act="pause" aria-label="Pauza">&#10073;&#10073;</button>' +
      '</div>' +
      '<div class="ns-pw"><span data-pw="0"></span><span data-pw="1"></span><span data-pw="2"></span><em data-h="lvl"></em></div>' +
      '<div class="ns-banner"></div>' +
      '<div class="ns-pad"><button data-dir="0">&#9650;</button><button data-dir="3">&#9664;</button><button data-dir="1">&#9654;</button><button data-dir="2">&#9660;</button></div>' +
      '<div class="ns-layer"></div>';
    document.body.appendChild(root);
    var cv = root.querySelector('.ns-cv'), ctx = cv.getContext('2d');
    var hud = root.querySelector('.ns-hud'), pwRow = root.querySelector('.ns-pw'), pad = root.querySelector('.ns-pad');
    var layer = root.querySelector('.ns-layer'), banner = root.querySelector('.ns-banner'), safeEl = root.querySelector('.ns-safe');
    var hEl = {}; ['score', 'mult', 'combo', 'len', 'best', 'lvl'].forEach(function (k) { hEl[k] = root.querySelector('[data-h="' + k + '"]'); });
    var pwEl = [0, 1, 2].map(function (i) { return root.querySelector('[data-pw="' + i + '"]'); });

    // state
    var state = 'menu', screen = 'menu', prevState = 'play', countdown = 0, lastCount = -1;
    var sim = null, demo = null, demoDeadT = 0, acc = 0, lastTs = 0, now = 0, deathT = 0, shakeT = 0, auto = false;
    var lastRes = null, newRecord = false;

    // layout / render resources
    var dpr = 1, cw = 1, ch = 1, cs = 10, bx = 0, by = 0, bw = 10, bh = 10, margin = 10;
    var boardLayer = null, boardKey = '', glow = COLORS.map(glowSprite), spr = {}, scan = null;
    var RP = new Float32Array(W * H * 2 + 8);
    // particles
    var PN = 320, px = new Float32Array(PN), py = new Float32Array(PN), pvx = new Float32Array(PN), pvy = new Float32Array(PN),
      pl = new Float32Array(PN), pm = new Float32Array(PN), pc = new Uint8Array(PN), pi = 0;
    // debris (death)
    var DN = 120, dn = 0, dx_ = new Float32Array(DN), dy_ = new Float32Array(DN), dvx = new Float32Array(DN), dvy = new Float32Array(DN), dr = new Float32Array(DN), dcol = [];
    // popups
    var UN = 16, ux = new Float32Array(UN), uy = new Float32Array(UN), ul = new Float32Array(UN), ut = new Array(UN), uc = new Uint8Array(UN), ui = 0;
    for (var q = 0; q < UN; q++) ut[q] = '';
    var hudCache = { score: -1, mult: -1, combo: -1, len: -1, best: -1, lvl: '', pw: [-1, -1, -1] };

    function S() { return state === 'menu' ? demo : sim; }

    // ----- layout -----
    function safeInsets() {
      var cs_ = getComputedStyle(safeEl);
      return { t: parseFloat(cs_.paddingTop) || 0, r: parseFloat(cs_.paddingRight) || 0, b: parseFloat(cs_.paddingBottom) || 0, l: parseFloat(cs_.paddingLeft) || 0 };
    }
    function layout() {
      if (exited) return;
      root.scrollTop = 0; root.scrollLeft = 0;
      var rw = root.clientWidth || window.innerWidth, rh = root.clientHeight || window.innerHeight;
      dpr = Math.min(2, window.devicePixelRatio || 1);
      cw = Math.round(rw * dpr); ch = Math.round(rh * dpr);
      if (cv.width !== cw || cv.height !== ch) { cv.width = cw; cv.height = ch; }
      var land = rw > rh * 1.15;
      root.classList.toggle('ns-land', land);
      root.classList.toggle('ns-dpad', !!store.dpad);
      var si = safeInsets();
      var top = pwRow.getBoundingClientRect().bottom + 6;
      var left = 16 + si.l, right = rw - 16 - si.r, bottom = rh - 16 - si.b;
      if (store.dpad) {
        var pr = pad.getBoundingClientRect();
        if (land) right = Math.min(right, pr.left - 12); else bottom = Math.min(bottom, pr.top - 10);
      }
      var aw = Math.max(80, right - left), ah = Math.max(80, bottom - top);
      cs = Math.max(6, Math.floor(Math.min(aw / W, ah / H) * dpr));
      bw = cs * W; bh = cs * H;
      bx = Math.round(((left + right) / 2) * dpr - bw / 2);
      by = Math.round(top * dpr + Math.max(0, (bottom - top) * dpr - bh) * (land || store.dpad ? 0.5 : 0.3));
      margin = Math.ceil(cs * 0.8);
      spr.food = itemSprite('food', cs); spr.gold = itemSprite('gold', cs);
      spr.pu = [itemSprite(0, cs), itemSprite(1, cs), itemSprite(2, cs)];
      scan = mkCanvas(4, 64);
      var sx = scan.getContext('2d'), sg = sx.createLinearGradient(0, 0, 0, 64);
      sg.addColorStop(0, 'rgba(34,243,255,0)'); sg.addColorStop(0.5, 'rgba(34,243,255,0.07)'); sg.addColorStop(1, 'rgba(34,243,255,0)');
      sx.fillStyle = sg; sx.fillRect(0, 0, 4, 64);
      boardKey = '';
      buildBoard();
    }
    function buildBoard() {
      var s = S(); if (!s) return;
      var key = cs + '|' + s.mode + '|' + s.level;
      if (key === boardKey && boardLayer) return;
      boardKey = key;
      var c = boardLayer && boardLayer.width === bw + margin * 2 ? boardLayer : mkCanvas(bw + margin * 2, bh + margin * 2);
      boardLayer = c;
      var x = c.getContext('2d'), m = margin;
      x.setTransform(1, 0, 0, 1, 0, 0); x.clearRect(0, 0, c.width, c.height);
      var bgc = x.createLinearGradient(0, m, 0, m + bh); bgc.addColorStop(0, 'rgba(10,14,34,0.92)'); bgc.addColorStop(1, 'rgba(18,8,34,0.92)');
      x.fillStyle = bgc; x.fillRect(m, m, bw, bh);
      // grid
      x.strokeStyle = 'rgba(80,200,255,0.07)'; x.lineWidth = 1;
      x.beginPath();
      for (var i = 1; i < W; i++) { x.moveTo(m + i * cs + 0.5, m); x.lineTo(m + i * cs + 0.5, m + bh); }
      for (i = 1; i < H; i++) { x.moveTo(m, m + i * cs + 0.5); x.lineTo(m + bw, m + i * cs + 0.5); }
      x.stroke();
      x.fillStyle = 'rgba(120,220,255,0.16)';
      for (i = 1; i < W; i++) for (var j = 1; j < H; j++) if (((i + j) & 3) === 0) x.fillRect(m + i * cs - 1, m + j * cs - 1, 2, 2);
      // walls
      if (s.mode === 'maze') {
        x.save(); x.shadowColor = '#ff2bd6'; x.shadowBlur = cs * 0.6;
        for (var y = 0; y < H; y++) for (var xx = 0; xx < W; xx++) {
          if (!s.walls[y * W + xx]) continue;
          var wx = m + xx * cs + 1, wy = m + y * cs + 1, ww = cs - 2;
          var wg = x.createLinearGradient(wx, wy, wx, wy + ww); wg.addColorStop(0, '#ff5ae0'); wg.addColorStop(1, '#7a2bff');
          x.fillStyle = wg; rrect(x, wx, wy, ww, ww, cs * 0.18); x.fill();
        }
        x.restore();
        x.fillStyle = 'rgba(255,255,255,0.22)';
        for (y = 0; y < H; y++) for (xx = 0; xx < W; xx++) if (s.walls[y * W + xx]) x.fillRect(m + xx * cs + cs * 0.2, m + y * cs + cs * 0.16, cs * 0.6, Math.max(1, cs * 0.08));
      }
      // border
      x.save();
      var bc = s.mode === 'portal' ? '#9dff3a' : s.mode === 'maze' ? '#ff2bd6' : '#22f3ff';
      x.strokeStyle = bc; x.lineWidth = Math.max(2, cs * 0.12); x.shadowColor = bc; x.shadowBlur = cs * 0.7;
      if (s.mode === 'portal') x.setLineDash([cs * 0.6, cs * 0.4]);
      rrect(x, m - 2, m - 2, bw + 4, bh + 4, cs * 0.3); x.stroke();
      x.restore();
    }
    function rrect(x, a, b, w, h, r) {
      x.beginPath(); x.moveTo(a + r, b); x.lineTo(a + w - r, b); x.quadraticCurveTo(a + w, b, a + w, b + r);
      x.lineTo(a + w, b + h - r); x.quadraticCurveTo(a + w, b + h, a + w - r, b + h); x.lineTo(a + r, b + h);
      x.quadraticCurveTo(a, b + h, a, b + h - r); x.lineTo(a, b + r); x.quadraticCurveTo(a, b, a + r, b); x.closePath();
    }

    // ----- effects -----
    function cellX(c) { return bx + ((c % W) + 0.5) * cs; }
    function cellY(c) { return by + (((c / W) | 0) + 0.5) * cs; }
    function burst(x, y, col, n, sp) {
      for (var k = 0; k < n; k++) {
        var a = Math.random() * 6.283, v = (0.3 + Math.random()) * sp * cs;
        px[pi] = x; py[pi] = y; pvx[pi] = Math.cos(a) * v; pvy[pi] = Math.sin(a) * v;
        pm[pi] = pl[pi] = 0.35 + Math.random() * 0.45; pc[pi] = col; pi = (pi + 1) % PN;
      }
    }
    function popup(x, y, text, col) { ux[ui] = x; uy[ui] = y; ul[ui] = 1; ut[ui] = text; uc[ui] = col; ui = (ui + 1) % UN; }
    function showBanner(text, cls) {
      banner.textContent = text;
      banner.className = 'ns-banner';
      void banner.offsetWidth;
      banner.className = 'ns-banner on ' + (cls || '');
    }
    function haptic(kind) {
      if (!store.haptics) return;
      try {
        var hf = window.Telegram && window.Telegram.WebApp && window.Telegram.WebApp.HapticFeedback;
        if (hf) { if (kind === 'error' || kind === 'success') hf.notificationOccurred(kind); else hf.impactOccurred(kind); return; }
      } catch (e) {}
      try { if (navigator.vibrate) navigator.vibrate(kind === 'error' ? [40, 30, 60] : kind === 'heavy' ? 25 : 8); } catch (e) {}
    }
    function onEv(t, c, v) {
      if (exited) return;
      switch (t) {
        case 'eat': burst(cellX(c), cellY(c), 2, 16, 5); popup(cellX(c), cellY(c) - cs * 0.4, '+' + v, 2); snd.play('eat', sim.mult); haptic('light'); break;
        case 'gold': burst(cellX(c), cellY(c), 3, 30, 7); popup(cellX(c), cellY(c) - cs * 0.4, '+' + v, 3); snd.play('gold'); haptic('medium'); break;
        case 'mult': popup(cellX(c) + cs * 0.9, cellY(c) - cs * 1.2, 'x' + v, 1); snd.play('mult', v); if (v === 5 || v === 10) showBanner('x' + v + ' KOMBO!', 'mg'); break;
        case 'pu': burst(cellX(c), cellY(c), PU_COL[v], 26, 6); snd.play('pu'); haptic('medium'); showBanner(PU_ICON[v] + ' ' + PU_NAME[v] + '!', 'p' + v); break;
        case 'goldgone': case 'pugone': burst(cellX(c), cellY(c), t === 'goldgone' ? 3 : 5, 8, 2); snd.play('gone'); break;
        case 'level': snd.play('level'); haptic('success'); break;
        case 'die': break;
      }
    }

    // ----- game flow -----
    function newDemo() { demo = new C.Sim('portal', {}); demoDeadT = 0; }
    function startGame() {
      sim = new C.Sim(store.mode, { ev: onEv });
      state = 'ready'; countdown = 1500; lastCount = -1; acc = 0; dn = 0; shakeT = 0;
      resultSent = false; lastRes = null; newRecord = false;
      for (var k = 0; k < PN; k++) pl[k] = 0;
      for (k = 0; k < UN; k++) ul[k] = 0;
      setScreen(null); boardKey = ''; buildBoard();
      hudCache.score = -1; hudCache.lvl = '';
      root.classList.add('ns-playing');
      snd.setDuck(1);
    }
    function pause() {
      if (state !== 'play' && state !== 'ready') return;
      prevState = state; state = 'paused'; setScreen('pause'); snd.setDuck(0.35);
    }
    function resume() {
      if (state !== 'paused') return;
      state = 'ready'; countdown = 900; lastCount = -1; setScreen(null); snd.setDuck(1);
    }
    function toMenu() {
      state = 'menu'; sim = null; root.classList.remove('ns-playing'); setScreen('menu'); boardKey = ''; buildBoard(); snd.setDuck(1);
    }
    function afterStep() {
      if (sim.leveled) {
        boardKey = ''; buildBoard(); state = 'ready'; countdown = 1300; lastCount = -1; acc = 0;
        showBanner('LEVEL ' + sim.level, 'lv');
        if (sim.level > store.mazeMax) { store.mazeMax = sim.level; saveStore(store); }
      }
      if (sim.dead) beginDeath();
    }
    function beginDeath() {
      state = 'dying'; deathT = 0; shakeT = 450;
      var b = sim.body, n = b.length, cnt = Math.min(n, DN); dn = cnt; dcol.length = 0;
      for (var k = 0; k < cnt; k++) {
        var i = Math.floor(k * n / cnt), c = b[i];
        dx_[k] = cellX(c); dy_[k] = cellY(c);
        var a = Math.random() * 6.283, v = (1.5 + Math.random() * 4) * cs;
        dvx[k] = Math.cos(a) * v; dvy[k] = Math.sin(a) * v - cs * 2; dr[k] = cs * (0.42 - 0.2 * i / Math.max(1, n - 1));
        dcol.push(BODY_PAL[Math.min(31, Math.floor(i / Math.max(1, n - 1) * 31))]);
      }
      burst(cellX(b[0]), cellY(b[0]), 6, 40, 8);
      snd.play('die'); haptic('error'); snd.setDuck(0.4);
    }
    function finish() {
      state = 'over';
      var res = {
        score: sim.score | 0, foods: sim.foods | 0, golds: sim.golds | 0, maxMult: sim.maxMult | 0,
        level: sim.resLevel() | 0, mode: sim.mode, time: Math.round(sim.timeMs / 100) / 10
      };
      lastRes = res;
      var m = sim.mode;
      newRecord = res.score > (store.best[m] || 0);
      if (newRecord) store.best[m] = res.score;
      store.stats.games++; store.stats.foods += res.foods; store.stats.golds += res.golds; store.stats.time += res.time;
      saveStore(store);
      setScreen('over');
      if (newRecord && res.score > 0) snd.play('gold');
      if (!resultSent) {
        resultSent = true;
        if (typeof opts.onResult === 'function') { try { opts.onResult(res); } catch (e) { setTimeout(function () { throw e; }); } }
      }
    }
    function turn(d) {
      if (!sim || (state !== 'play' && state !== 'ready')) return false;
      var ok = sim.turn(d);
      if (ok) snd.play('tick');
      return ok;
    }
    function exit() {
      if (exited) return;
      exited = true;
      if (raf) cancelAnimationFrame(raf); raf = 0;
      for (var i = 0; i < listeners.length; i++) { var L = listeners[i]; try { L[0].removeEventListener(L[1], L[2], L[3]); } catch (e) {} }
      listeners.length = 0;
      snd.close();
      if (root.parentNode) root.parentNode.removeChild(root);
      if (boardLayer) { boardLayer.width = boardLayer.height = 1; }
      cv.width = cv.height = 1;
      document.body.style.overflow = prevOverflow;
      try { var tw = window.Telegram && window.Telegram.WebApp; if (tw && tw.enableVerticalSwipes) tw.enableVerticalSwipes(); } catch (e) {}
      if (current === G) current = null;
      if (typeof opts.onExit === 'function') { try { opts.onExit(); } catch (e) { setTimeout(function () { throw e; }); } }
    }

    // ----- screens -----
    function btn(act, label, cls, extra) { return '<button class="ns-btn ' + (cls || '') + '" data-act="' + act + '"' + (extra || '') + '>' + label + '</button>'; }
    function setScreen(name) {
      screen = name;
      if (!name) { layer.innerHTML = ''; layer.className = 'ns-layer'; return; }
      var h = '', m = store.mode;
      if (name === 'menu') {
        var nm = opts.playerName ? 'Salom, ' + esc(opts.playerName) + '!' : 'Salom!';
        h = '<button class="ns-x" data-act="exit" aria-label="Chiqish">&#10005;</button>' +
          '<div class="ns-card ns-menu">' +
          '<div class="ns-logo"><span>NEON</span><b>SNAKE</b></div>' +
          '<p class="ns-sub">' + nm + ' Ilonni boshqar, neon mevalarni yig\', kombo yig\'ib x10 gacha chiq.</p>' +
          '<div class="ns-chip">' + MODE_NAME[m] + ' &middot; Rekord: <b>' + (store.best[m] || 0) + '</b></div>' +
          btn('play', '&#9654; PLAY', 'ns-pri') +
          btn('mode', 'MODE <em>' + MODE_NAME[m] + '</em>') +
          btn('settings', 'SETTINGS') +
          btn('howto', 'HOW TO PLAY') +
          btn('exit', 'WEB APP\'GA QAYTISH', 'ns-ghost') +
          '<div class="ns-foot">O\'yinlar: ' + store.stats.games + ' &middot; Mevalar: ' + store.stats.foods + ' &middot; Oltin: ' + store.stats.golds + '</div>' +
          '</div>';
      } else if (name === 'mode') {
        var D = { classic: 'Devorga tegsang — o\'yin tugaydi. Toza klassika.', portal: 'Chetdan chiqsang, qarama-qarshi tomondan kirasan.', maze: 'Labirint bosqichlari: ' + C.MAZE_FOODS + ' ta meva yeb, keyingi bosqichga o\'t. (' + C.MAZES.length + ' xarita)' };
        h = '<div class="ns-card"><h2>MODE</h2>';
        for (var i = 0; i < MODES.length; i++) {
          var k = MODES[i];
          h += '<button class="ns-mode' + (k === m ? ' sel' : '') + ' md-' + k + '" data-act="setmode" data-mode="' + k + '"><b>' + MODE_NAME[k] + '</b><span>' + D[k] + '</span><em>Rekord: ' + (store.best[k] || 0) + (k === 'maze' ? ' &middot; eng yuqori bosqich: ' + store.mazeMax : '') + '</em></button>';
        }
        h += btn('back', '&#8249; ORQAGA', 'ns-ghost') + '</div>';
      } else if (name === 'settings') {
        h = '<div class="ns-card"><h2>SETTINGS</h2>' +
          '<label class="ns-row"><span>Musiqa <b data-v="music">' + store.music + '</b></span><input type="range" min="0" max="100" step="5" data-k="music" value="' + store.music + '"></label>' +
          '<label class="ns-row"><span>Effektlar <b data-v="sfx">' + store.sfx + '</b></span><input type="range" min="0" max="100" step="5" data-k="sfx" value="' + store.sfx + '"></label>' +
          tog('dpad', 'Ekrandagi D-pad tugmalari') + tog('haptics', 'Tebranish (haptic)') + tog('shake', 'Ekran silkinishi') +
          btn('back', '&#8249; ORQAGA', 'ns-ghost') + '</div>';
      } else if (name === 'howto') {
        h = '<div class="ns-card ns-how"><h2>HOW TO PLAY</h2>' +
          '<p><b>Boshqaruv:</b> ekranni istalgan joyda barmoq bilan suring (tez-tez burilish mumkin), yoki D-pad, yoki klaviatura (strelkalar / WASD). P yoki Esc — pauza.</p>' +
          '<p><span class="i f"></span><b>Meva</b> — 10 &times; kombo ball.</p>' +
          '<p><span class="i g"></span><b>Oltin yulduz</b> — 50 &times; kombo ball, lekin tez yo\'qoladi!</p>' +
          '<p><b>Kombo:</b> mevalarni ketma-ket tez yesang ko\'paytiruvchi x10 gacha o\'sadi; sekinlashsang — kamayadi.</p>' +
          '<p><b>Bonuslar:</b> ' + PU_ICON[0] + ' Sekin vaqt, ' + PU_ICON[1] + ' Arvoh (o\'z tanangdan o\'tasan), ' + PU_ICON[2] + ' Magnit (mevalarni tortadi).</p>' +
          '<p><b>Rejimlar:</b> Classic — devor halokatli; Portal — chetlar ulangan; Maze — labirint bosqichlari.</p>' +
          '<p>Har bir mevadan keyin ilon tezlashadi. Omad!</p>' +
          btn('back', '&#8249; ORQAGA', 'ns-ghost') + '</div>';
      } else if (name === 'pause') {
        h = '<div class="ns-card ns-small"><h2>PAUZA</h2>' +
          '<div class="ns-chip">Ball: <b>' + sim.score + '</b> &middot; x' + sim.mult + '</div>' +
          btn('resume', '&#9654; DAVOM ETISH', 'ns-pri') + btn('restart', 'QAYTA BOSHLASH') + btn('menu', 'MENYU') +
          btn('exit', 'WEB APP\'GA QAYTISH', 'ns-ghost') + '</div>';
      } else if (name === 'over') {
        var r = lastRes;
        h = '<div class="ns-card ns-over"><h2>O\'YIN TUGADI</h2>' +
          (newRecord && r.score > 0 ? '<div class="ns-rec">&#9733; YANGI REKORD!</div>' : '') +
          '<div class="ns-big">' + r.score + '</div>' +
          '<div class="ns-grid">' +
          cell('Rekord', store.best[r.mode]) + cell('Mevalar', r.foods) + cell('Oltin', r.golds) +
          cell('Maks. kombo', 'x' + r.maxMult) + cell('Uzunlik', sim.body.length) + cell('Vaqt', fmtTime(r.time)) +
          cell(r.mode === 'maze' ? 'Bosqich' : 'Tezlik', r.level) + cell('Rejim', MODE_NAME[r.mode]) +
          '</div>' +
          btn('again', '&#8635; YANA O\'YNASH', 'ns-pri') + btn('menu', 'MENYU') + btn('exit', 'WEB APP\'GA QAYTISH', 'ns-ghost') + '</div>';
      }
      layer.innerHTML = h;
      layer.className = 'ns-layer on ns-s-' + name;
    }
    function cell(k, v) { return '<div><small>' + k + '</small><b>' + v + '</b></div>'; }
    function tog(k, label) { return '<button class="ns-row ns-tog' + (store[k] ? ' on' : '') + '" data-act="tog" data-k="' + k + '"><span>' + label + '</span><i>' + (store[k] ? 'YOQILGAN' : 'O\'CHIQ') + '</i></button>'; }

    // ----- input -----
    var swId = -1, swX = 0, swY = 0;
    function onClick(e) {
      var t = e.target.closest ? e.target.closest('[data-act]') : null;
      if (!t || !root.contains(t)) return;
      var a = t.getAttribute('data-act');
      snd.unlock();
      if (a !== 'pause') snd.play('ui');
      switch (a) {
        case 'play': case 'again': case 'restart': startGame(); break;
        case 'mode': setScreen('mode'); break;
        case 'settings': setScreen('settings'); break;
        case 'howto': setScreen('howto'); break;
        case 'back': setScreen('menu'); break;
        case 'setmode': store.mode = t.getAttribute('data-mode'); saveStore(store); boardKey = ''; setScreen('menu'); break;
        case 'tog':
          var k = t.getAttribute('data-k'); store[k] = !store[k]; saveStore(store);
          t.classList.toggle('on', store[k]); t.querySelector('i').textContent = store[k] ? 'YOQILGAN' : 'O\'CHIQ';
          if (k === 'dpad') layout();
          break;
        case 'pause': pause(); break;
        case 'resume': resume(); break;
        case 'menu': toMenu(); break;
        case 'exit': exit(); break;
      }
    }
    function onInput(e) {
      var t = e.target, k = t.getAttribute && t.getAttribute('data-k');
      if (k !== 'music' && k !== 'sfx') return;
      store[k] = clamp(parseInt(t.value, 10) || 0, 0, 100);
      var v = layer.querySelector('[data-v="' + k + '"]'); if (v) v.textContent = store[k];
      snd.unlock(); snd.applyVol(); saveStore(store);
    }
    function onDown(e) {
      snd.unlock();
      var d = e.target.closest ? e.target.closest('[data-dir]') : null;
      if (d) { e.preventDefault(); turn(+d.getAttribute('data-dir')); d.classList.add('dn'); return; }
      if (state !== 'play' && state !== 'ready') return;
      if (e.target.closest && e.target.closest('button,input,.ns-layer.on')) return;
      swId = e.pointerId; swX = e.clientX; swY = e.clientY;
    }
    function onMove(e) {
      if (e.pointerId !== swId) return;
      var ddx = e.clientX - swX, ddy = e.clientY - swY, ax = Math.abs(ddx), ay = Math.abs(ddy);
      var dead = Math.max(14, Math.min(root.clientWidth, root.clientHeight) * 0.035);
      if (Math.max(ax, ay) < dead) return;
      var dir = ax > ay ? (ddx > 0 ? 1 : 3) : (ddy > 0 ? 2 : 0);
      turn(dir);
      swX = e.clientX; swY = e.clientY;
    }
    function onUp(e) {
      if (e.pointerId === swId) swId = -1;
      var b = root.querySelectorAll('.ns-pad .dn'); for (var i = 0; i < b.length; i++) b[i].classList.remove('dn');
    }
    var KEYS = { ArrowUp: 0, KeyW: 0, ArrowRight: 1, KeyD: 1, ArrowDown: 2, KeyS: 2, ArrowLeft: 3, KeyA: 3 };
    function onKey(e) {
      if (exited) return;
      snd.unlock();
      var code = e.code || '', d = KEYS[code];
      if (d === undefined) { var kk = e.key; d = kk === 'ArrowUp' ? 0 : kk === 'ArrowRight' ? 1 : kk === 'ArrowDown' ? 2 : kk === 'ArrowLeft' ? 3 : undefined; }
      if (d !== undefined) { if (state === 'play' || state === 'ready') { e.preventDefault(); turn(d); } return; }
      if (code === 'KeyP' || code === 'Escape' || e.key === 'Escape' || e.key === 'p' || e.key === 'P') {
        if (state === 'play' || state === 'ready') pause(); else if (state === 'paused') resume();
        e.preventDefault(); return;
      }
      if ((code === 'Enter' || code === 'Space') && (state === 'menu' && screen === 'menu' || state === 'over')) { e.preventDefault(); startGame(); }
    }
    function onVis() {
      if (document.hidden) { pause(); snd.suspend(); } else snd.resume();
    }
    var needLayout = false;
    function onResize() { needLayout = true; }

    on(root, 'click', onClick);
    on(root, 'input', onInput);
    on(root, 'pointerdown', onDown);
    on(root, 'pointermove', onMove);
    on(root, 'pointerup', onUp);
    on(root, 'pointercancel', onUp);
    on(root, 'contextmenu', function (e) { e.preventDefault(); });
    on(window, 'keydown', onKey);
    on(window, 'resize', onResize);
    on(window, 'orientationchange', onResize);
    on(document, 'visibilitychange', onVis);

    // ----- loop -----
    function frame(ts) {
      raf = requestAnimationFrame(frame);
      if (needLayout) { needLayout = false; layout(); }
      var dt = lastTs ? ts - lastTs : 16; lastTs = ts;
      if (dt > 100) dt = 100; if (dt < 0) dt = 0;
      now += dt;
      update(dt);
      render();
      updateHud();
    }
    var alpha = 1;
    function update(dt) {
      var k = 0;
      if (state === 'menu') {
        if (!demo || (demo.dead && (demoDeadT += dt) > 900)) { newDemo(); boardKey = ''; buildBoard(); }
        if (!demo.dead) {
          acc += dt;
          while (acc >= demo.interval && k++ < 4) { acc -= demo.interval; var bd = C.botDir(demo); if (bd !== demo.dir) demo.turn(bd); demo.step(); if (demo.dead) break; }
          alpha = demo.dead ? 1 : clamp(acc / demo.interval, 0, 1);
        }
      } else if (state === 'ready') {
        countdown -= dt;
        var n = Math.ceil(countdown / 500);
        if (n !== lastCount && n > 0) { lastCount = n; showBanner(String(n), 'cd'); snd.play('count'); }
        if (countdown <= 0) { state = 'play'; acc = 0; showBanner('GO!', 'go'); snd.play('go'); }
        alpha = 0;
      } else if (state === 'play') {
        acc += dt;
        while (acc >= sim.interval && k++ < 4) {
          acc -= sim.interval;
          if (auto) { var ad = C.botDir(sim); if (ad !== (sim.queue.length ? sim.queue[sim.queue.length - 1] : sim.dir)) sim.turn(ad); }
          sim.step(); afterStep();
          if (state !== 'play') break;
        }
        if (k >= 4) acc = 0;
        alpha = state === 'play' ? clamp(acc / sim.interval, 0, 1) : (state === 'ready' ? 0 : 1);
      } else if (state === 'dying') {
        deathT += dt;
        var f = dt / 1000;
        for (k = 0; k < dn; k++) { dx_[k] += dvx[k] * f; dy_[k] += dvy[k] * f; dvy[k] += cs * 9 * f; dvx[k] *= 0.985; }
        if (deathT > 1300) finish();
      }
      // particles & popups
      var fs = dt / 1000;
      for (k = 0; k < PN; k++) if (pl[k] > 0) { pl[k] -= fs; px[k] += pvx[k] * fs; py[k] += pvy[k] * fs; pvx[k] *= 0.94; pvy[k] *= 0.94; }
      for (k = 0; k < UN; k++) if (ul[k] > 0) { ul[k] -= fs * 1.1; uy[k] -= cs * 1.4 * fs; }
      if (shakeT > 0) shakeT -= dt;
    }

    // Path: interpolated head -> real cell centres body[1..n-1] -> interpolated tail (sharp, clean corners).
    function lerpCell(c0, c1, t, portal, k) {
      var x1 = c1 % W, y1 = (c1 / W) | 0, x0 = c0 % W, y0 = (c0 / W) | 0;
      if (portal) { if (x1 - x0 > 1) x0 += W; else if (x0 - x1 > 1) x0 -= W; if (y1 - y0 > 1) y0 += H; else if (y0 - y1 > 1) y0 -= H; }
      RP[k] = bx + (x0 + (x1 - x0) * t + 0.5) * cs;
      RP[k + 1] = by + (y0 + (y1 - y0) * t + 0.5) * cs;
    }
    function computeRP(s, t) {
      var b = s.body, p = s.prev, n = b.length, portal = s.portal;
      lerpCell(p.length ? p[0] : b[0], b[0], t, portal, 0);
      for (var i = 1; i < n; i++) { var c = b[i]; RP[i * 2] = bx + ((c % W) + 0.5) * cs; RP[i * 2 + 1] = by + (((c / W) | 0) + 0.5) * cs; }
      var last = b[n - 1], pl_ = n - 1 < p.length ? p[n - 1] : last;
      // tail end: moves from its old cell towards body[n-1]
      lerpCell(pl_, last, t, portal, n * 2);
      return n + 1;
    }
    function itemPos(c, pc_, t, out) {
      var x1 = c % W, y1 = (c / W) | 0;
      if (pc_ >= 0 && pc_ !== c) { var x0 = pc_ % W, y0 = (pc_ / W) | 0; if (Math.abs(x1 - x0) + Math.abs(y1 - y0) === 1) { x1 = x0 + (x1 - x0) * t; y1 = y0 + (y1 - y0) * t; } }
      out[0] = bx + (x1 + 0.5) * cs; out[1] = by + (y1 + 0.5) * cs;
    }
    var IP = [0, 0];
    function drawItem(sp, x, y, scale) {
      var w = sp.width * scale; ctx.drawImage(sp, x - w / 2, y - w / 2, w, w);
    }
    function timerRing(x, y, frac, col) {
      ctx.strokeStyle = col; ctx.lineWidth = Math.max(1.5, cs * 0.08); ctx.globalAlpha = 0.8;
      ctx.beginPath(); ctx.arc(x, y, cs * 0.62, -1.5708, -1.5708 + frac * 6.2832); ctx.stroke(); ctx.globalAlpha = 1;
    }
    function render() {
      ctx.setTransform(1, 0, 0, 1, 0, 0);
      ctx.clearRect(0, 0, cw, ch);
      var s = S(); if (!s) return;
      if (!boardLayer || boardKey === '') buildBoard();
      var ox = 0, oy = 0;
      if (shakeT > 0 && store.shake) { var amp = cs * 0.5 * (shakeT / 450); ox = (Math.random() - 0.5) * amp * 2; oy = (Math.random() - 0.5) * amp * 2; }
      ctx.setTransform(1, 0, 0, 1, ox, oy);
      ctx.drawImage(boardLayer, bx - margin, by - margin);
      ctx.save();
      ctx.beginPath(); ctx.rect(bx, by, bw, bh); ctx.clip();
      // moving scan band
      var band = cs * 4, sy = by - band + ((now * 0.06 * dpr) % (bh + band * 2));
      ctx.drawImage(scan, bx, sy, bw, band);
      if (s.pw[0] > 0) { ctx.fillStyle = 'rgba(60,150,255,0.07)'; ctx.fillRect(bx, by, bw, bh); }
      var t = state === 'menu' || state === 'play' ? alpha : (state === 'ready' ? 0 : 1);
      var pulse = 1 + 0.08 * Math.sin(now * 0.008);
      // items
      if (s.food >= 0) { itemPos(s.food, s.pf, t, IP); drawItem(spr.food, IP[0], IP[1], pulse); }
      if (s.gold >= 0) {
        itemPos(s.gold, s.pg, t, IP);
        var gl = s.goldT / s.goldMax, blink = gl < 0.3 && ((now / 120) | 0) % 2 === 0;
        if (!blink) { ctx.save(); ctx.translate(IP[0], IP[1]); ctx.rotate(Math.sin(now * 0.004) * 0.3); drawItem(spr.gold, 0, 0, 1 + 0.12 * Math.sin(now * 0.012)); ctx.restore(); }
        timerRing(IP[0], IP[1], gl, COLORS[3]);
      }
      if (s.pu >= 0) {
        var ux_ = cellX(s.pu), uy_ = cellY(s.pu), ulf = s.puT / s.puMax;
        if (!(ulf < 0.3 && ((now / 120) | 0) % 2 === 0)) drawItem(spr.pu[s.puType], ux_, uy_ + Math.sin(now * 0.006) * cs * 0.08, 1);
        timerRing(ux_, uy_, ulf, COLORS[PU_COL[s.puType]]);
      }
      if (state === 'dying' || (state === 'over' && dn > 0)) drawDebris();
      else drawSnake(s, t);
      // particles
      ctx.globalCompositeOperation = 'lighter';
      for (var k = 0; k < PN; k++) {
        if (pl[k] <= 0) continue;
        var a = pl[k] / pm[k], sz = cs * (0.15 + 0.35 * a);
        ctx.globalAlpha = a; ctx.drawImage(glow[pc[k]], px[k] - sz, py[k] - sz, sz * 2, sz * 2);
      }
      ctx.globalAlpha = 1; ctx.globalCompositeOperation = 'source-over';
      ctx.restore();
      // popups
      ctx.font = '800 ' + Math.round(cs * 0.75) + 'px system-ui, -apple-system, "Segoe UI", Roboto, sans-serif';
      ctx.textAlign = 'center'; ctx.textBaseline = 'middle';
      for (k = 0; k < UN; k++) {
        if (ul[k] <= 0) continue;
        ctx.globalAlpha = clamp(ul[k] * 1.5, 0, 1);
        ctx.fillStyle = 'rgba(0,0,0,0.6)'; ctx.fillText(ut[k], ux[k] + 1.5, uy[k] + 1.5);
        ctx.fillStyle = COLORS[uc[k]]; ctx.fillText(ut[k], ux[k], uy[k]);
      }
      ctx.globalAlpha = 1;
    }
    function drawSnake(s, t) {
      var n = computeRP(s, t), i, x0, y0, x1, y1, far = cs * 1.6, ghost = s.pw[1] > 0;
      var fade = 1, gflick = ghost && s.pw[1] < 1500 && ((now / 110) | 0) % 2 === 1;
      var pal = ghost && !gflick ? GHOST_PAL : BODY_PAL;
      ctx.lineCap = 'round'; ctx.lineJoin = 'round';
      // glow underlay (single path)
      ctx.globalAlpha = 0.2 * fade; ctx.strokeStyle = ghost ? '#b892ff' : '#22f3ff'; ctx.lineWidth = cs * 1.25;
      ctx.beginPath(); ctx.moveTo(RP[0], RP[1]);
      for (i = 1; i < n; i++) {
        x1 = RP[i * 2]; y1 = RP[i * 2 + 1]; x0 = RP[i * 2 - 2]; y0 = RP[i * 2 - 1];
        if (Math.abs(x1 - x0) > far || Math.abs(y1 - y0) > far) ctx.moveTo(x1, y1); else ctx.lineTo(x1, y1);
      }
      ctx.stroke();
      // body (tapered), tail -> head
      ctx.globalAlpha = fade;
      var den = Math.max(1, n - 1);
      for (i = n - 1; i >= 1; i--) {
        var f = i / den;
        x0 = RP[i * 2]; y0 = RP[i * 2 + 1]; x1 = RP[i * 2 - 2]; y1 = RP[i * 2 - 1];
        ctx.strokeStyle = pal[Math.min(31, (f * 31) | 0)];
        ctx.lineWidth = cs * (0.8 - 0.42 * f);
        var ddx = x1 - x0, ddy = y1 - y0;
        ctx.beginPath();
        if (Math.abs(ddx) > far || Math.abs(ddy) > far) {
          // wrap across portal edge: draw two stubs
          var wx = ddx > far ? -bw : ddx < -far ? bw : 0, wy = ddy > far ? -bh : ddy < -far ? bh : 0;
          ctx.moveTo(x0, y0); ctx.lineTo(x1 + wx, y1 + wy); ctx.moveTo(x0 - wx, y0 - wy); ctx.lineTo(x1, y1);
        } else { ctx.moveTo(x0, y0); ctx.lineTo(x1, y1); }
        ctx.stroke();
      }
      // gloss line
      ctx.globalAlpha = 0.28 * fade; ctx.strokeStyle = '#ffffff'; ctx.lineWidth = Math.max(1, cs * 0.12);
      ctx.beginPath(); ctx.moveTo(RP[0], RP[1] - cs * 0.12);
      var lim = Math.min(n, 40);
      for (i = 1; i < lim; i++) {
        x1 = RP[i * 2]; y1 = RP[i * 2 + 1] - cs * 0.12; x0 = RP[i * 2 - 2];
        if (Math.abs(x1 - x0) > far || Math.abs(y1 - RP[i * 2 - 1] + cs * 0.12) > far) ctx.moveTo(x1, y1); else ctx.lineTo(x1, y1);
      }
      ctx.stroke();
      ctx.globalAlpha = fade;
      // head
      var hx = RP[0], hy = RP[1], d = s.dir, fx = DX[d], fy = DY[d], rx = -fy, ry = fx;
      ctx.drawImage(glow[ghost ? 5 : 0], hx - cs * 1.4, hy - cs * 1.4, cs * 2.8, cs * 2.8);
      // tongue flick
      var tp = (now % 1800) / 1800;
      if (tp < 0.14 && state !== 'over') {
        var tl = cs * (0.35 + Math.sin(tp / 0.14 * Math.PI) * 0.35), tx = hx + fx * (cs * 0.4 + tl), ty = hy + fy * (cs * 0.4 + tl);
        ctx.strokeStyle = '#ff2bd6'; ctx.lineWidth = Math.max(1, cs * 0.07);
        ctx.beginPath(); ctx.moveTo(hx + fx * cs * 0.4, hy + fy * cs * 0.4); ctx.lineTo(tx, ty);
        ctx.lineTo(tx + (fx + rx) * cs * 0.12, ty + (fy + ry) * cs * 0.12); ctx.moveTo(tx, ty); ctx.lineTo(tx + (fx - rx) * cs * 0.12, ty + (fy - ry) * cs * 0.12);
        ctx.stroke();
      }
      ctx.fillStyle = ghost ? '#e2d8ff' : '#5ffbff';
      ctx.beginPath(); ctx.arc(hx, hy, cs * 0.47, 0, 6.2832); ctx.fill();
      // eyes
      var eo = cs * 0.2, ef = cs * 0.12, er = cs * 0.14;
      ctx.fillStyle = '#ffffff';
      ctx.beginPath(); ctx.arc(hx + rx * eo + fx * ef, hy + ry * eo + fy * ef, er, 0, 6.2832);
      ctx.arc(hx - rx * eo + fx * ef, hy - ry * eo + fy * ef, er, 0, 6.2832); ctx.fill();
      var blinkE = ((now % 3200) < 110);
      ctx.fillStyle = '#081020';
      if (blinkE) {
        ctx.fillRect(hx + rx * eo + fx * ef - er, hy + ry * eo + fy * ef - 1, er * 2, 2);
        ctx.fillRect(hx - rx * eo + fx * ef - er, hy - ry * eo + fy * ef - 1, er * 2, 2);
      } else {
        ctx.beginPath(); ctx.arc(hx + rx * eo + fx * ef * 1.7, hy + ry * eo + fy * ef * 1.7, er * 0.55, 0, 6.2832);
        ctx.arc(hx - rx * eo + fx * ef * 1.7, hy - ry * eo + fy * ef * 1.7, er * 0.55, 0, 6.2832); ctx.fill();
      }
      // magnet aura
      if (s.pw[2] > 0) {
        ctx.globalAlpha = 0.25 + 0.15 * Math.sin(now * 0.01); ctx.strokeStyle = COLORS[6]; ctx.lineWidth = Math.max(1, cs * 0.06);
        ctx.beginPath(); ctx.arc(hx, hy, cs * (1.2 + ((now * 0.003) % 1) * 2.5), 0, 6.2832); ctx.stroke();
      }
      ctx.globalAlpha = 1;
    }
    function drawDebris() {
      var life = clamp(1 - deathT / 1300, 0, 1);
      if (state === 'over') life = 0;
      if (life <= 0) return;
      ctx.globalAlpha = life;
      for (var k = 0; k < dn; k++) {
        ctx.fillStyle = dcol[k];
        ctx.beginPath(); ctx.arc(dx_[k], dy_[k], Math.max(1, dr[k] * (0.4 + 0.6 * life)), 0, 6.2832); ctx.fill();
      }
      ctx.globalAlpha = 1;
    }
    function updateHud() {
      var s = sim;
      if (!s) return;
      var c = hudCache;
      if (c.score !== s.score) { c.score = s.score; hEl.score.textContent = s.score; }
      if (c.mult !== s.mult) { c.mult = s.mult; hEl.mult.textContent = 'x' + s.mult; hEl.mult.parentNode.className = 'ns-hb ns-hm m' + Math.min(10, s.mult); }
      var cb = s.comboT > 0 ? Math.round(s.comboT / s.comboMax * 50) * 2 : 0;
      if (c.combo !== cb) { c.combo = cb; hEl.combo.style.width = cb + '%'; }
      if (c.len !== s.body.length) { c.len = s.body.length; hEl.len.textContent = s.body.length; }
      var best = Math.max(store.best[s.mode] || 0, s.score);
      if (c.best !== best) { c.best = best; hEl.best.textContent = best; }
      var lv = s.mode === 'maze' ? 'LEVEL ' + s.level + ' · ' + s.levelFoods + '/' + C.MAZE_FOODS : MODE_NAME[s.mode] + ' · TEZLIK ' + s.speedLevel();
      if (c.lvl !== lv) { c.lvl = lv; hEl.lvl.textContent = lv; }
      for (var i = 0; i < 3; i++) {
        var v = s.pw[i] > 0 ? Math.ceil(s.pw[i] / 1000) : 0;
        if (c.pw[i] !== v) { c.pw[i] = v; pwEl[i].textContent = v ? PU_ICON[i] + ' ' + PU_NAME[i] + ' ' + v + 's' : ''; pwEl[i].className = v ? 'on p' + i : ''; }
      }
    }

    // ----- public object -----
    G.exit = exit;
    G.pause = pause;
    G.resume = resume;
    G.start = startGame;
    G.menu = toMenu;
    G.root = root;
    G.VERSION = VERSION;
    Object.defineProperty(G, 'state', { get: function () { return state; } });
    Object.defineProperty(G, 'screen', { get: function () { return screen; } });
    Object.defineProperty(G, 'sim', { get: function () { return sim; } });
    // test / debug hook (deterministic stepping)
    G._t = {
      skip: function () { if (state === 'ready') { countdown = 0; state = 'play'; acc = 0; } },
      step: function (n) {
        n = n || 1;
        for (var k = 0; k < n; k++) {
          if (!sim || (state !== 'play' && state !== 'ready')) break;
          state = 'play'; sim.step(); afterStep();
        }
        return sim;
      },
      finishDeath: function () { if (state === 'dying') { deathT = 2000; update(0); } },
      place: function (type, x, y, puType) {
        var c = y * W + x;
        if (type === 'food') { sim.food = c; sim.pf = c; }
        else if (type === 'gold') { sim.gold = c; sim.pg = c; sim.goldT = sim.goldMax = 5600; }
        else if (type === 'pu') { sim.pu = c; sim.puType = puType | 0; sim.puT = sim.puMax = 7000; }
        return c;
      },
      turn: turn,
      auto: function (v) { auto = !!v; },
      store: function () { return store; },
      freeze: function (v) { if (v) { if (raf) cancelAnimationFrame(raf); raf = 0; } else if (!raf && !exited) { lastTs = 0; raf = requestAnimationFrame(frame); } }
    };

    layout();
    newDemo(); buildBoard();
    setScreen('menu');
    raf = requestAnimationFrame(frame);
    return G;
  }

  window.NSNK = {
    VERSION: VERSION,
    launch: function (opts) {
      if (current) { try { current.exit(); } catch (e) {} current = null; }
      current = createGame(opts);
      return current;
    },
    _internal: { core: C, get game() { return current; } }
  };
  Object.defineProperty(window.NSNK, 'current', { get: function () { return current; }, enumerable: true });
})();
