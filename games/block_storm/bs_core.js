/* BLOCK STORM — core logic (pure, no DOM). Original falling-block puzzle engine.
   Exposes window.BSTORM._Core. Load before bs_game.js. */
(function () {
  'use strict';
  var B = window.BSTORM = window.BSTORM || {};

  var W = 10, VIS = 20, HID = 20, H = VIS + HID;
  var NAMES = ' IJLOSTZ'; // type ids 1..7, 8 = grey filler
  var DEF = {
    I: [4, [[0, 1], [1, 1], [2, 1], [3, 1]]],
    J: [3, [[0, 0], [0, 1], [1, 1], [2, 1]]],
    L: [3, [[2, 0], [0, 1], [1, 1], [2, 1]]],
    O: [2, [[0, 0], [1, 0], [0, 1], [1, 1]]],
    S: [3, [[1, 0], [2, 0], [0, 1], [1, 1]]],
    T: [3, [[1, 0], [0, 1], [1, 1], [2, 1]]],
    Z: [3, [[0, 0], [1, 0], [1, 1], [2, 1]]]
  };
  // CELLS[t][r] = Int8Array [x0,y0,x1,y1,...] relative to box top-left
  var CELLS = [null], BOXN = [0];
  for (var t = 1; t <= 7; t++) {
    var d = DEF[NAMES[t]], n = d[0], cur = d[1], rots = [];
    for (var r = 0; r < 4; r++) {
      var a = new Int8Array(8);
      for (var i = 0; i < 4; i++) { a[i * 2] = cur[i][0]; a[i * 2 + 1] = cur[i][1]; }
      rots.push(a);
      var nx = [];
      for (i = 0; i < 4; i++) nx.push([n - 1 - cur[i][1], cur[i][0]]); // clockwise
      cur = nx;
    }
    CELLS.push(rots); BOXN.push(n);
  }
  var SPAWN_X = [0, 3, 3, 3, 4, 3, 3, 3];
  var SPAWN_Y = HID - 1; // piece appears fully inside the visible well after the initial one-row drop

  // Rotation offset tests, written with y pointing UP (converted below).
  var K_STD_CW = [
    [[0, 0], [-1, 0], [-1, 1], [0, -2], [-1, -2]], // 0->1
    [[0, 0], [1, 0], [1, -1], [0, 2], [1, 2]],     // 1->2
    [[0, 0], [1, 0], [1, 1], [0, -2], [1, -2]],    // 2->3
    [[0, 0], [-1, 0], [-1, -1], [0, 2], [-1, 2]]   // 3->0
  ];
  var K_STD_CCW = [
    [[0, 0], [1, 0], [1, 1], [0, -2], [1, -2]],    // 0->3
    [[0, 0], [1, 0], [1, -1], [0, 2], [1, 2]],     // 1->0
    [[0, 0], [-1, 0], [-1, 1], [0, -2], [-1, -2]], // 2->1
    [[0, 0], [-1, 0], [-1, -1], [0, 2], [-1, 2]]   // 3->2
  ];
  var K_LONG_CW = [
    [[0, 0], [-2, 0], [1, 0], [-2, -1], [1, 2]],   // 0->1
    [[0, 0], [-1, 0], [2, 0], [-1, 2], [2, -1]],   // 1->2
    [[0, 0], [2, 0], [-1, 0], [2, 1], [-1, -2]],   // 2->3
    [[0, 0], [1, 0], [-2, 0], [1, -2], [-2, 1]]    // 3->0
  ];
  var K_LONG_CCW = [
    [[0, 0], [-1, 0], [2, 0], [-1, 2], [2, -1]],   // 0->3
    [[0, 0], [2, 0], [-1, 0], [2, 1], [-1, -2]],   // 1->0
    [[0, 0], [1, 0], [-2, 0], [1, -2], [-2, 1]],   // 2->1
    [[0, 0], [-2, 0], [1, 0], [-2, -1], [1, 2]]    // 3->2
  ];
  function conv(tab) { // -> Int8Array per rotation, y flipped to "down"
    return tab.map(function (l) {
      var a = new Int8Array(l.length * 2);
      l.forEach(function (k, i) { a[i * 2] = k[0]; a[i * 2 + 1] = -k[1]; });
      return a;
    });
  }
  var KICK = {
    stdCW: conv(K_STD_CW), stdCCW: conv(K_STD_CCW),
    longCW: conv(K_LONG_CW), longCCW: conv(K_LONG_CCW),
    none: [new Int8Array([0, 0]), new Int8Array([0, 0]), new Int8Array([0, 0]), new Int8Array([0, 0])]
  };

  var LINE_PTS = [0, 100, 300, 500, 800];
  var SPIN_PTS = [0, 800, 1200, 1600, 1600];
  var MINI_PTS = [0, 200, 400, 400, 400];
  var MAX_LEVEL = 30;
  var DROP_CAP = 60; // drop points per piece never exceed this

  function mulberry(seed) {
    var s = seed >>> 0;
    return function () {
      s = (s + 0x6D2B79F5) >>> 0;
      var x = s;
      x = Math.imul(x ^ (x >>> 15), x | 1);
      x ^= x + Math.imul(x ^ (x >>> 7), x | 61);
      return ((x ^ (x >>> 14)) >>> 0) / 4294967296;
    };
  }

  function gravityTime(level) {
    var L = Math.max(1, Math.min(MAX_LEVEL, level));
    var b = Math.max(0.8 - (L - 1) * 0.007, 0.05);
    return Math.max(Math.pow(b, L - 1), 1e-6);
  }

  function Engine(o) {
    o = o || {};
    this.o = o;
    this.mode = o.mode || 'marathon';
    this.board = new Uint8Array(W * H);
    this.clearRows = new Int8Array(4);
    this.lockCells = new Int8Array(8);
    this.queue = [];
    this.bag = [];
    this.das = o.das != null ? o.das : 0.15;
    this.arr = o.arr != null ? o.arr : 0.033;
    this.lockDelay = o.lockDelay != null ? o.lockDelay : 0.5;
    this.maxResets = o.maxResets != null ? o.maxResets : 15;
    this.clearDelay = o.clearDelay != null ? o.clearDelay : 0.22;
    this.goalLines = this.mode === 'sprint' ? 40 : (this.mode === 'marathon' && o.goal ? o.goal * 10 : 0);
    this.onEvent = o.onEvent || null;
    this.reset(o.seed);
  }
  var P = Engine.prototype;

  P.ev = function (type, a, b) { if (this.onEvent) this.onEvent(type, a, b); };

  P.reset = function (seed) {
    this.seed = (seed != null ? seed : Math.floor(Math.random() * 4294967296)) >>> 0;
    this.rng = mulberry(this.seed);
    this.board.fill(0);
    this.bag.length = 0; this.queue.length = 0;
    this.genLog = this.o.log ? [] : null;
    while (this.queue.length < 5) this.queue.push(this.nextFromBag());
    this.hold = 0; this.holdUsed = false;
    this.score = 0; this.lines = 0;
    this.startLevel = Math.max(1, Math.min(MAX_LEVEL, this.o.startLevel || 1));
    this.level = this.startLevel; this.maxLevel = this.level;
    this.pieces = 0; this.time = 0;
    this.combo = -1; this.b2b = false;
    this.over = false; this.won = false; this.reason = ''; this.target = false;
    this.pt = 0; this.pr = 0; this.px = 0; this.py = 0; this.ghostY = 0;
    this.gAcc = 0; this.lockT = 0; this.resets = 0; this.lowest = 0; this.landed = false;
    this.lastRot = false; this.lastKick = 0; this.dropPts = 0;
    this.clearN = 0; this.clearT = 0;
    this.lHeld = false; this.rHeld = false; this.dir = 0; this.dasT = 0; this.arrT = 0; this.soft = false;
    this.lastClear = null;
    this.spawn(0, false);
  };

  P.nextFromBag = function () {
    if (!this.bag.length) {
      for (var i = 1; i <= 7; i++) this.bag.push(i);
      for (i = 6; i > 0; i--) {
        var j = Math.floor(this.rng() * (i + 1)), tmp = this.bag[i];
        this.bag[i] = this.bag[j]; this.bag[j] = tmp;
      }
    }
    var t = this.bag.pop();
    if (this.genLog) this.genLog.push(t);
    return t;
  };

  P.collide = function (t, r, x, y) {
    var c = CELLS[t][r], b = this.board;
    for (var i = 0; i < 8; i += 2) {
      var cx = x + c[i], cy = y + c[i + 1];
      if (cx < 0 || cx >= W || cy >= H || cy < 0) return true;
      if (b[cy * W + cx]) return true;
    }
    return false;
  };

  P.grounded = function () { return !this.pt || this.collide(this.pt, this.pr, this.px, this.py + 1); };

  P.updateGhost = function () {
    if (!this.pt) return;
    var y = this.py;
    while (!this.collide(this.pt, this.pr, this.px, y + 1)) y++;
    this.ghostY = y;
  };

  P.setActive = function (t) {
    this.pt = t; this.pr = 0; this.px = SPAWN_X[t]; this.py = SPAWN_Y;
    this.gAcc = 0; this.lockT = 0; this.resets = 0; this.landed = false;
    this.lastRot = false; this.lastKick = 0; this.dropPts = 0;
    if (this.collide(t, 0, this.px, this.py)) {
      if (this.mode === 'zen') { this.zenClear(); }
      else { this.pt = 0; this.gameOver('blockout'); return false; }
    }
    if (!this.collide(t, 0, this.px, this.py + 1)) this.py++;
    this.lowest = this.py;
    this.updateGhost();
    // pre-charged auto-shift carries into the new piece
    if (this.dir && this.dasT >= this.das && this.arr <= 0) { while (this.tryMove(this.dir, 0)) { /* slide */ } this.updateGhost(); }
    return true;
  };

  P.spawn = function (type, fromHold) {
    if (this.over) return;
    var t = type;
    if (!t) { t = this.queue.shift(); this.queue.push(this.nextFromBag()); }
    if (!fromHold) this.holdUsed = false;
    if (this.setActive(t)) this.ev('spawn', t);
  };

  P.zenClear = function () { this.board.fill(0); this.ev('zenclear'); };

  P.tryMove = function (dx, dy) {
    if (this.collide(this.pt, this.pr, this.px + dx, this.py + dy)) return false;
    this.px += dx; this.py += dy; return true;
  };

  P.checkLowest = function () {
    if (this.py > this.lowest) { this.lowest = this.py; this.resets = 0; this.lockT = 0; }
  };

  P.manip = function () {
    this.checkLowest();
    if (this.landed) { this.resets++; if (this.resets <= this.maxResets) this.lockT = 0; }
    this.updateGhost();
  };

  P.active = function () { return !!this.pt && !this.over && this.clearT <= 0; };

  P.shift = function (dir) {
    if (!this.active()) return false;
    if (!this.tryMove(dir, 0)) return false;
    this.lastRot = false; this.manip(); this.ev('move', dir);
    return true;
  };

  P.rotate = function (d) {
    if (!this.active()) return false;
    var t = this.pt, r = this.pr, nr = (r + (d > 0 ? 1 : 3)) % 4;
    var tab = t === 4 ? KICK.none : (t === 1 ? (d > 0 ? KICK.longCW : KICK.longCCW) : (d > 0 ? KICK.stdCW : KICK.stdCCW));
    var k = tab[r];
    for (var i = 0; i < k.length; i += 2) {
      var x = this.px + k[i], y = this.py + k[i + 1];
      if (!this.collide(t, nr, x, y)) {
        this.pr = nr; this.px = x; this.py = y;
        this.lastRot = true; this.lastKick = i >> 1;
        this.manip();
        this.ev('rotate', i >> 1, d);
        return true;
      }
    }
    return false;
  };

  P.addDrop = function (pts) {
    var add = Math.min(pts, DROP_CAP - this.dropPts);
    if (add > 0) { this.score += add; this.dropPts += add; }
  };

  P.softStep = function () {
    if (!this.active()) return false;
    if (!this.tryMove(0, 1)) return false;
    this.lastRot = false; this.gAcc = 0; this.addDrop(1); this.checkLowest();
    this.ev('soft');
    return true;
  };

  P.hardDrop = function () {
    if (!this.active()) return false;
    this.updateGhost();
    var d = this.ghostY - this.py, from = this.py;
    if (d > 0) this.lastRot = false;
    this.py = this.ghostY;
    this.addDrop(2 * d);
    this.ev('hard', d, from);
    this.lock();
    return true;
  };

  P.doHold = function () {
    if (!this.active() || this.holdUsed || this.o.noHold) return false;
    var t = this.pt, h = this.hold;
    this.hold = t;
    if (h) this.spawn(h, true); else this.spawn(0, true);
    this.holdUsed = true;
    this.ev('hold', t);
    return true;
  };

  P.input = function (key, down) {
    if (key === 'soft') { this.soft = !!down; if (down) this.gAcc = Math.max(this.gAcc, this.softTime()); return; }
    var dir = key === 'left' ? -1 : 1;
    if (key === 'left') this.lHeld = !!down; else this.rHeld = !!down;
    if (down) {
      this.dir = dir; this.dasT = 0; this.arrT = this.arr;
      this.shift(dir);
    } else if (this.dir === dir) {
      var other = dir < 0 ? this.rHeld : this.lHeld;
      this.dir = other ? -dir : 0; this.dasT = 0; this.arrT = this.arr;
    }
  };

  P.gravityTime = function () {
    return gravityTime(this.mode === 'marathon' ? this.level : 1);
  };
  P.softTime = function () { return Math.min(this.gravityTime() / 20, 0.05); };

  P.spinKind = function () {
    if (this.pt !== 6 || !this.lastRot) return 0;
    var x = this.px, y = this.py, b = this.board, self = this;
    function occ(cx, cy) { return cx < 0 || cx >= W || cy >= H || cy < 0 || !!b[cy * W + cx]; }
    var c = [occ(x, y), occ(x + 2, y), occ(x + 2, y + 2), occ(x, y + 2)]; // TL TR BR BL
    var n = (c[0] ? 1 : 0) + (c[1] ? 1 : 0) + (c[2] ? 1 : 0) + (c[3] ? 1 : 0);
    if (n < 3) return 0;
    var r = self.pr, f1 = c[r], f2 = c[(r + 1) % 4]; // front corners for each facing
    if ((f1 && f2) || self.lastKick === 4) return 2;
    return 1;
  };

  P.lock = function () {
    var t = this.pt, cl = CELLS[t][this.pr], b = this.board, above = true, i;
    var spin = this.spinKind();
    var minY = H, maxY = 0;
    for (i = 0; i < 8; i += 2) {
      var cx = this.px + cl[i], cy = this.py + cl[i + 1];
      b[cy * W + cx] = t;
      this.lockCells[i] = cx; this.lockCells[i + 1] = cy;
      if (cy >= HID) above = false;
      if (cy < minY) minY = cy; if (cy > maxY) maxY = cy;
    }
    this.pieces++;
    this.pt = 0;
    this.ev('lock', t, spin);
    if (above) {
      if (this.mode === 'zen') { this.zenClear(); this.spawn(0, false); return; }
      this.gameOver('lockout'); return;
    }
    var n = 0;
    for (var y = minY; y <= maxY; y++) {
      var full = true;
      for (var x = 0; x < W; x++) if (!b[y * W + x]) { full = false; break; }
      if (full) this.clearRows[n++] = y;
    }
    this.score_(n, spin);
    if (n > 0) {
      this.clearN = n;
      this.ev('clear', n, this.lastClear);
      if (this.goalLines && this.lines >= this.goalLines) this.target = true;
      if (this.clearDelay > 0) { this.clearT = this.clearDelay; return; }
      this.finishClear();
    } else {
      this.spawn(0, false);
    }
  };

  P.score_ = function (n, spin) {
    var lvl = this.level, pts = 0, cpts = 0, hard = false, base, b2bUsed = false;
    if (spin === 2) { base = SPIN_PTS[n]; hard = n > 0; }
    else if (spin === 1) { base = MINI_PTS[n]; hard = n > 0; }
    else { base = LINE_PTS[n]; hard = n === 4; }
    if (n > 0) {
      pts = base * lvl;
      if (hard && this.b2b) { pts = Math.floor(pts * 1.5); b2bUsed = true; }
      this.combo++;
      if (this.combo > 0) cpts = 50 * this.combo * lvl;
      this.b2b = hard;
    } else {
      this.combo = -1;
    }
    this.score += pts + cpts;
    this.lines += n;
    this.lastClear = { n: n, spin: spin, b2b: b2bUsed, combo: this.combo, pts: pts, comboPts: cpts, level: lvl };
    var nl = Math.min(MAX_LEVEL, this.startLevel + Math.floor(this.lines / 10));
    if (nl > this.level) {
      this.level = nl;
      if (nl > this.maxLevel) this.maxLevel = nl;
      this.ev('levelup', nl);
    }
    var bound = this.bound();
    if (this.score > bound) { this.score = bound; this.clampHits = (this.clampHits || 0) + 1; } // safety net, never expected to trigger
  };

  P.bound = function () { return (this.lines * 1800 + this.pieces * 60) * this.maxLevel; };

  P.finishClear = function () {
    var b = this.board, n = this.clearN, rows = this.clearRows;
    var dst = H - 1;
    for (var y = H - 1; y >= 0; y--) {
      var skip = false;
      for (var k = 0; k < n; k++) if (rows[k] === y) { skip = true; break; }
      if (skip) continue;
      if (dst !== y) for (var x = 0; x < W; x++) b[dst * W + x] = b[y * W + x];
      dst--;
    }
    for (; dst >= 0; dst--) for (x = 0; x < W; x++) b[dst * W + x] = 0;
    this.clearN = 0; this.clearT = 0;
    if (this.target) { this.finish(true); return; }
    this.spawn(0, false);
  };

  P.gameOver = function (reason) {
    if (this.over) return;
    this.over = true; this.won = false; this.reason = reason || 'topout'; this.pt = 0;
    this.ev('gameover', this.reason);
  };
  P.finish = function (won) {
    if (this.over) return;
    this.over = true; this.won = !!won; this.reason = won ? 'goal' : 'end'; this.pt = 0;
    this.ev('finish', this.won);
  };

  P.step = function (dt) {
    if (this.over) return;
    if (!this.target) this.time += dt;
    // auto-shift charging always runs so it carries over between pieces
    if (this.dir) {
      this.dasT += dt;
      if (this.dasT >= this.das && this.active()) {
        if (this.arr <= 0) { while (this.shift(this.dir)) { /* slide */ } }
        else {
          this.arrT += dt;
          var guard = 0;
          while (this.arrT >= this.arr && guard++ < 12) { this.arrT -= this.arr; if (!this.shift(this.dir)) { this.arrT = 0; break; } }
        }
      }
    }
    if (this.clearT > 0) {
      this.clearT -= dt;
      if (this.clearT <= 0) this.finishClear();
      return;
    }
    if (!this.pt) return;
    var gt = this.gravityTime();
    if (this.soft) gt = Math.min(gt, this.softTime());
    if (!this.collide(this.pt, this.pr, this.px, this.py + 1)) {
      this.gAcc += dt;
      var n = 0;
      while (this.gAcc >= gt && n++ < 44) {
        this.gAcc -= gt;
        if (this.tryMove(0, 1)) {
          this.lastRot = false;
          if (this.soft) { this.addDrop(1); this.ev('soft'); }
          this.checkLowest();
        } else { this.gAcc = 0; break; }
      }
    }
    if (this.collide(this.pt, this.pr, this.px, this.py + 1)) {
      this.landed = true; this.gAcc = 0;
      this.lockT += dt;
      if (this.lockT >= this.lockDelay || this.resets > this.maxResets) this.lock();
    }
  };

  P.fallFrac = function () {
    if (!this.pt || this.clearT > 0 || this.grounded()) return 0;
    var gt = this.gravityTime();
    if (this.soft) gt = Math.min(gt, this.softTime());
    return Math.max(0, Math.min(0.999, this.gAcc / gt));
  };

  P.result = function () {
    return {
      score: Math.min(this.score, this.bound()) | 0,
      lines: this.lines | 0, level: this.level | 0, pieces: this.pieces | 0,
      maxLevel: this.maxLevel | 0, mode: this.mode,
      time: Math.round(this.time * 100) / 100
    };
  };

  // ---- test / tooling helpers ----
  function typeOf(ch) {
    if (typeof ch === 'number') return ch;
    var i = NAMES.indexOf(String(ch).toUpperCase());
    return i > 0 ? i : 8;
  }
  P.setBoard = function (rows) { // rows top->bottom, bottom-aligned; '.' empty
    this.board.fill(0);
    var off = H - rows.length;
    for (var r = 0; r < rows.length; r++)
      for (var x = 0; x < W; x++) {
        var ch = rows[r][x];
        if (ch && ch !== '.' && ch !== ' ') this.board[(off + r) * W + x] = typeOf(ch);
      }
    this.updateGhost();
  };
  P.setPiece = function (t, r, x, y) {
    this.pt = typeOf(t); this.pr = r || 0; this.px = x; this.py = y;
    this.gAcc = 0; this.lockT = 0; this.resets = 0; this.landed = false; this.lowest = y;
    this.lastRot = false; this.dropPts = 0; this.clearT = 0;
    this.updateGhost();
  };
  P.setQueue = function (list) { this.queue = list.map(typeOf); while (this.queue.length < 5) this.queue.push(this.nextFromBag()); };
  P.cells = function () {
    if (!this.pt) return [];
    var c = CELLS[this.pt][this.pr], out = [];
    for (var i = 0; i < 8; i += 2) out.push([this.px + c[i], this.py + c[i + 1]]);
    return out;
  };
  P.rowsText = function () {
    var out = [];
    for (var y = HID; y < H; y++) {
      var s = '';
      for (var x = 0; x < W; x++) { var v = this.board[y * W + x]; s += v ? (v === 8 ? '#' : NAMES[v]) : '.'; }
      out.push(s);
    }
    return out;
  };

  B._Core = {
    Engine: Engine, W: W, H: H, VIS: VIS, HID: HID, NAMES: NAMES, CELLS: CELLS, BOXN: BOXN,
    SPAWN_X: SPAWN_X, SPAWN_Y: SPAWN_Y, KICK: KICK, gravityTime: gravityTime, MAX_LEVEL: MAX_LEVEL,
    LINE_PTS: LINE_PTS, SPIN_PTS: SPIN_PTS, MINI_PTS: MINI_PTS, DROP_CAP: DROP_CAP, mulberry: mulberry
  };
})();
