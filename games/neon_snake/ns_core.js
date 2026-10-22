/* NEON SNAKE — core simulation (deterministic, no DOM). Original game. */
(function () {
  'use strict';
  var W = 20, H = 20, N = W * H;
  var DX = [0, 1, 0, -1], DY = [-1, 0, 1, 0]; // 0 up, 1 right, 2 down, 3 left
  var MODES = ['classic', 'portal', 'maze'];
  var MAX_MULT = 10, MAZE_FOODS = 8, DECAY_MS = 1600;
  var PU_SLOW = 0, PU_GHOST = 1, PU_MAGNET = 2;
  var PU_DUR = [6000, 6000, 8000];

  // Hand-designed maze levels (20x20, '#' = wall). start = [x, y, dir]
  var MAZES = [
    { name: 'Ikki devor', start: [6, 10, 1], rows: [
      '....................', '....................', '....................', '....................',
      '....############....', '....................', '....................', '....................',
      '....................', '....................', '....................', '....................',
      '....................', '....................', '....................', '....############....',
      '....................', '....................', '....................', '....................'] },
    { name: 'Burchaklar', start: [6, 10, 1], rows: [
      '....................', '.######......######.', '.#................#.', '.#................#.',
      '....................', '....................', '....................', '....................',
      '....................', '....................', '....................', '....................',
      '....................', '....................', '....................', '....................',
      '.#................#.', '.#................#.', '.######......######.', '....................'] },
    { name: 'Chorraha', start: [1, 6, 2], rows: [
      '....................', '....................', '....................', '.........##.........',
      '.........##.........', '.........##.........', '.........##.........', '.........##.........',
      '....................', '...#####....#####...', '...#####....#####...', '....................',
      '.........##.........', '.........##.........', '.........##.........', '.........##.........',
      '.........##.........', '....................', '....................', '....................'] },
    { name: 'Xonalar', start: [8, 10, 1], rows: [
      '....................', '....................', '....................', '...######..######...',
      '...#............#...', '...#............#...', '...#............#...', '...#............#...',
      '....................', '....................', '....................', '....................',
      '...#............#...', '...#............#...', '...#............#...', '...#............#...',
      '...######..######...', '....................', '....................', '....................'] },
    { name: 'Zigzag', start: [6, 10, 1], rows: [
      '....................', '....................', '##############......', '....................',
      '....................', '....................', '......##############', '....................',
      '....................', '....................', '....................', '....................',
      '....................', '##############......', '....................', '....................',
      '....................', '......##############', '....................', '....................'] },
    { name: 'Ustunlar', start: [6, 10, 1], rows: [
      '....................', '....................', '...##....##....##...', '...##....##....##...',
      '....................', '....................', '....................', '...##....##....##...',
      '...##....##....##...', '....................', '....................', '....................',
      '...##....##....##...', '...##....##....##...', '....................', '....................',
      '...##....##....##...', '...##....##....##...', '....................', '....................'] }
  ];

  function rng32(seed) {
    var s = seed >>> 0;
    return function () {
      s = (s + 0x6D2B79F5) >>> 0;
      var t = s;
      t = Math.imul(t ^ (t >>> 15), t | 1);
      t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
      return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
    };
  }

  function Sim(mode, opts) {
    opts = opts || {};
    this.mode = MODES.indexOf(mode) >= 0 ? mode : 'classic';
    this.portal = this.mode === 'portal';
    this.rand = rng32(opts.seed != null ? opts.seed : (Math.random() * 4294967296) >>> 0);
    this.ev = opts.ev || null;
    this.walls = new Uint8Array(N);
    this.occ = new Uint8Array(N);
    this.body = []; this.prev = []; this.queue = [];
    this.score = 0; this.foods = 0; this.golds = 0; this.pus = 0;
    this.mult = 1; this.maxMult = 1; this.comboT = 0; this.comboMax = 1;
    this.level = 1; this.levelFoods = 0; this.timeMs = 0; this.steps = 0;
    this.dead = false; this.cause = ''; this.grow = 0; this.dir = 1;
    this.food = -1; this.gold = -1; this.goldT = 0; this.goldMax = 1;
    this.pu = -1; this.puType = 0; this.puT = 0; this.puMax = 1;
    this.pf = -1; this.pg = -1;
    this.pw = [0, 0, 0];
    this.sincePU = 0; this.base = 150; this.interval = 150; this.leveled = 0;
    this.loadLevel(1);
  }
  Sim.prototype.emit = function (t, c, v) { if (this.ev) this.ev(t, c, v); };
  Sim.prototype.loadLevel = function (lv) {
    var i, x, y;
    this.level = lv; this.levelFoods = 0;
    this.walls.fill(0); this.occ.fill(0);
    var st = [6, 10, 1];
    if (this.mode === 'maze') {
      var m = MAZES[(lv - 1) % MAZES.length];
      for (y = 0; y < H; y++) { var r = m.rows[y]; for (x = 0; x < W; x++) if (r.charCodeAt(x) === 35) this.walls[y * W + x] = 1; }
      st = m.start;
    }
    this.dir = st[2]; this.queue.length = 0; this.grow = 0;
    var b = this.body; b.length = 0;
    for (i = 0; i < 4; i++) {
      var c = (st[1] - DY[st[2]] * i) * W + (st[0] - DX[st[2]] * i);
      b.push(c); this.occ[c]++;
    }
    this.prev.length = 0; for (i = 0; i < b.length; i++) this.prev.push(b[i]);
    this.food = -1; this.gold = -1; this.pu = -1;
    this.food = this.freeCell(); this.pf = this.food; this.pg = -1;
    this.calcInterval();
  };
  Sim.prototype.calcInterval = function () {
    var b;
    if (this.mode === 'maze') b = Math.max(70, 140 - (this.level - 1) * 7 - this.levelFoods * 2);
    else b = Math.max(62, 150 - (this.foods + this.golds) * 3);
    this.base = b;
    this.interval = this.pw[PU_SLOW] > 0 ? Math.round(b * 1.6) : b;
  };
  Sim.prototype.speedLevel = function () { return Math.max(1, Math.min(9, 1 + Math.floor((150 - this.base) / 11))); };
  Sim.prototype.resLevel = function () { return this.mode === 'maze' ? this.level : this.speedLevel(); };
  Sim.prototype.isFree = function (c) {
    return !this.walls[c] && !this.occ[c] && c !== this.food && c !== this.gold && c !== this.pu;
  };
  Sim.prototype.freeCell = function () {
    var h = this.body[0], hx = h % W, hy = (h / W) | 0, r = this.rand, c, i;
    for (i = 0; i < 80; i++) {
      c = (r() * N) | 0;
      if (this.isFree(c)) {
        var x = c % W, y = (c / W) | 0;
        if (Math.abs(x - hx) + Math.abs(y - hy) >= 3 || i > 40) return c;
      }
    }
    var s = (r() * N) | 0;
    for (i = 0; i < N; i++) { c = (s + i) % N; if (this.isFree(c)) return c; }
    return -1;
  };
  Sim.prototype.turn = function (d) {
    if (this.dead) return false;
    var q = this.queue, last = q.length ? q[q.length - 1] : this.dir;
    if (d === last || ((d + 2) & 3) === last) return false;
    if (q.length >= 2) return false;
    q.push(d);
    return true;
  };
  Sim.prototype.bumpMult = function () {
    if (this.comboT > 0 && this.mult < MAX_MULT) { this.mult++; this.emit('mult', this.body[0], this.mult); }
    if (this.mult > this.maxMult) this.maxMult = this.mult;
    this.comboT = this.comboMax = Math.max(1800, 4200 - this.mult * 220);
    return this.mult;
  };
  Sim.prototype.die = function (cause) {
    this.dead = true; this.cause = cause;
    var p = this.prev, b = this.body; p.length = b.length;
    for (var i = 0; i < b.length; i++) p[i] = b[i];
    this.pf = this.food; this.pg = this.gold;
    this.emit('die', b[0], 0);
  };
  Sim.prototype.pull = function (c, hx, hy) {
    if (c < 0) return c;
    var x = c % W, y = (c / W) | 0, dx = hx - x, dy = hy - y;
    if (this.portal) {
      if (dx > W / 2) dx -= W; else if (dx < -W / 2) dx += W;
      if (dy > H / 2) dy -= H; else if (dy < -H / 2) dy += H;
    }
    var d = Math.abs(dx) + Math.abs(dy);
    if (d > 7 || d <= 1) return c;
    var sx = dx === 0 ? 0 : (dx > 0 ? 1 : -1), sy = dy === 0 ? 0 : (dy > 0 ? 1 : -1);
    var xFirst = Math.abs(dx) >= Math.abs(dy);
    for (var k = 0; k < 2; k++) {
      var nx = x, ny = y;
      if ((k === 0) === xFirst) nx += sx; else ny += sy;
      if (nx === x && ny === y) continue;
      nx = (nx + W) % W; ny = (ny + H) % H;
      var n = ny * W + nx;
      if (!this.walls[n] && !this.occ[n] && n !== this.food && n !== this.gold && n !== this.pu) return n;
    }
    return c;
  };
  Sim.prototype.step = function () {
    if (this.dead) return;
    var iv = this.interval, i;
    this.steps++; this.timeMs += iv; this.leveled = 0;
    this.pf = this.food; this.pg = this.gold;
    if (this.comboT > 0) {
      this.comboT -= iv;
      if (this.comboT <= 0) {
        this.comboT = 0;
        if (this.mult > 1) {
          this.mult--;
          if (this.mult > 1) this.comboT = this.comboMax = DECAY_MS;
          this.emit('decay', -1, this.mult);
        }
      }
    }
    if (this.gold >= 0) { this.goldT -= iv; if (this.goldT <= 0) { this.emit('goldgone', this.gold, 0); this.gold = -1; } }
    if (this.pu >= 0) { this.puT -= iv; if (this.puT <= 0) { this.emit('pugone', this.pu, 0); this.pu = -1; } }
    for (i = 0; i < 3; i++) if (this.pw[i] > 0) { this.pw[i] -= iv; if (this.pw[i] <= 0) { this.pw[i] = 0; this.emit('puend', -1, i); } }
    if (this.pw[PU_MAGNET] > 0) {
      var hh = this.body[0];
      this.food = this.pull(this.food, hh % W, (hh / W) | 0);
      this.gold = this.pull(this.gold, hh % W, (hh / W) | 0);
    }
    if (this.queue.length) this.dir = this.queue.shift();
    var h = this.body[0], x = h % W + DX[this.dir], y = ((h / W) | 0) + DY[this.dir];
    if (x < 0 || y < 0 || x >= W || y >= H) {
      if (this.portal) { x = (x + W) % W; y = (y + H) % H; } else return this.die('wall');
    }
    var ni = y * W + x;
    if (this.walls[ni]) return this.die('wall');
    var eatF = ni === this.food, eatG = ni === this.gold, eatP = ni === this.pu;
    var b = this.body, tail = b[b.length - 1];
    var keepTail = this.grow > 0 || eatF || eatG;
    if (this.occ[ni] && this.pw[PU_GHOST] <= 0 && !(ni === tail && !keepTail)) return this.die('self');
    var p = this.prev; p.length = b.length;
    for (i = 0; i < b.length; i++) p[i] = b[i];
    b.unshift(ni); this.occ[ni]++;
    if (eatF) this.grow += 1;
    if (eatG) this.grow += 2;
    if (this.grow > 0) { this.grow--; p.push(tail); } else { b.pop(); this.occ[tail]--; }

    if (eatF) {
      this.foods++; this.levelFoods++; this.sincePU++;
      var pts = 10 * this.bumpMult();
      this.score += pts;
      this.emit('eat', ni, pts);
      this.food = -1; this.food = this.freeCell(); this.pf = this.food;
      if (this.gold < 0 && this.rand() < 0.2) {
        var g = this.freeCell();
        if (g >= 0) { this.gold = g; this.pg = g; this.goldT = this.goldMax = 5600; this.emit('goldspawn', g, 0); }
      }
      if (this.pu < 0 && this.sincePU >= 4 && this.rand() < 0.45) {
        var u = this.freeCell();
        if (u >= 0) { this.pu = u; this.puType = (this.rand() * 3) | 0; this.puT = this.puMax = 7000; this.sincePU = 0; this.emit('puspawn', u, this.puType); }
      }
      if (this.food < 0) { this.dead = true; this.cause = 'full'; this.emit('die', ni, 1); }
    }
    if (eatG) {
      this.golds++; this.levelFoods++;
      var gp = 50 * this.bumpMult();
      this.score += gp; this.gold = -1; this.pg = -1;
      this.emit('gold', ni, gp);
    }
    if (eatP) {
      this.pus++; this.pw[this.puType] = PU_DUR[this.puType]; this.pu = -1;
      this.emit('pu', ni, this.puType);
    }
    if (this.mode === 'maze' && (eatF || eatG) && !this.dead && this.levelFoods >= MAZE_FOODS) {
      this.loadLevel(this.level + 1); this.leveled = 1;
      this.emit('level', -1, this.level);
    }
    this.calcInterval();
  };

  // ---- simple autopilot (menu demo + tests) ----
  var Q = new Int16Array(N), FROM = new Int8Array(N), SEEN = new Uint8Array(N), SEEN2 = new Uint8Array(N);
  function nb(sim, c, d) {
    var x = c % W + DX[d], y = ((c / W) | 0) + DY[d];
    if (x < 0 || y < 0 || x >= W || y >= H) { if (!sim.portal) return -1; x = (x + W) % W; y = (y + H) % H; }
    var n = y * W + x;
    return sim.walls[n] ? -1 : n;
  }
  function flood(sim, s, cap) {
    SEEN2.fill(0); var qh = 0, qt = 0, ghost = sim.pw[PU_GHOST] > 0;
    SEEN2[s] = 1; Q[qt++] = s;
    while (qh < qt && qt < cap) {
      var c = Q[qh++];
      for (var d = 0; d < 4; d++) {
        var n = nb(sim, c, d);
        if (n < 0 || SEEN2[n] || (sim.occ[n] && !ghost)) continue;
        SEEN2[n] = 1; Q[qt++] = n;
      }
    }
    return qt;
  }
  function botDir(sim) {
    var b = sim.body, h = b[0], tail = b[b.length - 1], ghost = sim.pw[PU_GHOST] > 0;
    var cur = sim.queue.length ? sim.queue[sim.queue.length - 1] : sim.dir, d, n;
    var need = Math.min(b.length + 2, 60), target = -1;
    SEEN.fill(0); SEEN[h] = 1;
    var qh = 0, qt = 0;
    for (d = 0; d < 4; d++) {
      if (d === ((cur + 2) & 3)) continue;
      n = nb(sim, h, d);
      if (n < 0 || SEEN[n] || (sim.occ[n] && n !== tail && !ghost)) continue;
      SEEN[n] = 1; FROM[n] = d; Q[qt++] = n;
    }
    while (qh < qt) {
      var c = Q[qh++];
      if (c === sim.food || c === sim.gold || c === sim.pu) { target = FROM[c]; break; }
      for (d = 0; d < 4; d++) {
        n = nb(sim, c, d);
        if (n < 0 || SEEN[n] || (sim.occ[n] && !ghost)) continue;
        SEEN[n] = 1; FROM[n] = FROM[c]; Q[qt++] = n;
      }
    }
    if (target >= 0 && flood(sim, nb(sim, h, target), need + 1) >= need) return target;
    var best = -1, bs = -1;
    for (d = 0; d < 4; d++) {
      if (d === ((cur + 2) & 3)) continue;
      n = nb(sim, h, d);
      if (n < 0 || (sim.occ[n] && n !== tail && !ghost)) continue;
      var s = flood(sim, n, N);
      if (s > bs) { bs = s; best = d; }
    }
    return best < 0 ? cur : best;
  }

  window.NSNK_CORE = {
    W: W, H: H, N: N, DX: DX, DY: DY, MODES: MODES, MAZES: MAZES, MAX_MULT: MAX_MULT,
    MAZE_FOODS: MAZE_FOODS, PU_DUR: PU_DUR, Sim: Sim, botDir: botDir, rng32: rng32
  };
})();
