/* DENGIZ JANGI — taktik o'yin: solo (3 darajali AI) va online 1v1. Klassik qoidalar: 4·3·3·2·2·2·1·1·1·1, kemalar tegmaydi. */
(function () {
  'use strict';
  var K = window.AKIT, N = 10, FLEET = [4, 3, 3, 2, 2, 2, 1, 1, 1, 1], LET = 'ABCDEFGHIK';

  function emptyB() { var b = []; for (var i = 0; i < N; i++) { b.push([]); for (var j = 0; j < N; j++) b[i].push(0); } return b; } // 0 suv,1 kema,2 o'q tegdi,3 o'tkazdi
  function canPlace(b, r, c, len, v) {
    for (var k = 0; k < len; k++) { var rr = r + (v ? k : 0), cc = c + (v ? 0 : k); if (rr >= N || cc >= N) return false;
      for (var dr = -1; dr <= 1; dr++) for (var dc = -1; dc <= 1; dc++) { var a = rr + dr, d = cc + dc; if (a >= 0 && a < N && d >= 0 && d < N && b[a][d] === 1) return false; } }
    return true;
  }
  function randomFleet() {
    for (;;) { var b = emptyB(), ships = [], ok = true;
      for (var s = 0; s < FLEET.length && ok; s++) { var placed = false;
        for (var t = 0; t < 300 && !placed; t++) { var v = Math.random() < 0.5, r = Math.floor(Math.random() * N), c = Math.floor(Math.random() * N);
          if (canPlace(b, r, c, FLEET[s], v)) { var cells = []; for (var k = 0; k < FLEET[s]; k++) { var rr = r + (v ? k : 0), cc = c + (v ? 0 : k); b[rr][cc] = 1; cells.push([rr, cc]); } ships.push({ cells: cells, v: v }); placed = true; } }
        ok = placed; }
      if (ok) return { b: b, ships: ships }; }
  }
  function shipAt(F, r, c) { for (var i = 0; i < F.ships.length; i++) for (var j = 0; j < F.ships[i].cells.length; j++) { var x = F.ships[i].cells[j]; if (x[0] === r && x[1] === c) return F.ships[i]; } return null; }
  // Mening taxtamga o'q: {hit, sunk:[cells]|null, over}
  function receive(F, r, c) {
    if (F.b[r][c] >= 2) return { dup: true };
    if (F.b[r][c] === 0) { F.b[r][c] = 3; return { hit: 0 }; }
    F.b[r][c] = 2; var s = shipAt(F, r, c), sunk = s.cells.every(function (x) { return F.b[x[0]][x[1]] === 2; });
    var over = sunk && F.ships.every(function (sh) { return sh.cells.every(function (x) { return F.b[x[0]][x[1]] === 2; }); });
    return { hit: 1, sunk: sunk ? s.cells : null, over: over ? 1 : 0 };
  }
  function around(cells, fn) { cells.forEach(function (x) { for (var dr = -1; dr <= 1; dr++) for (var dc = -1; dc <= 1; dc++) { var a = x[0] + dr, d = x[1] + dc; if (a >= 0 && a < N && d >= 0 && d < N) fn(a, d); } }); }

  // ---- AI ----
  function AI(diff) { this.diff = diff; this.v = emptyB(); /* 0 noma'lum, 2 tegdi, 3 bo'sh */ this.hits = []; this.left = FLEET.slice(); }
  AI.prototype.pick = function () {
    var v = this.v, self = this, i, j;
    var unk = []; for (i = 0; i < N; i++) for (j = 0; j < N; j++) if (!v[i][j]) unk.push([i, j]);
    if (this.diff === 0) return unk[Math.floor(Math.random() * unk.length)];
    var P = this.diff === 2 ? this.density() : null;
    if (this.hits.length) {
      var cand = [], hs = this.hits;
      var line = hs.length > 1 ? (hs[0][0] === hs[1][0] ? 'h' : 'v') : null;
      hs.forEach(function (h) { [[0, 1], [0, -1], [1, 0], [-1, 0]].forEach(function (d) { if (line === 'h' && d[0]) return; if (line === 'v' && d[1]) return;
        var a = h[0] + d[0], b = h[1] + d[1]; if (a >= 0 && a < N && b >= 0 && b < N && !v[a][b]) cand.push([a, b]); }); });
      if (cand.length) { if (!P) return cand[Math.floor(Math.random() * cand.length)];
        return cand.reduce(function (b, x) { return P[x[0]][x[1]] > P[b[0]][b[1]] ? x : b; }, cand[0]); }
    }
    if (this.diff === 1) return unk[Math.floor(Math.random() * unk.length)];
    var best = unk[0], bv = -1; unk.forEach(function (x) { var sc = P[x[0]][x[1]] + Math.random() * 0.5; if (sc > bv) { bv = sc; best = x; } });
    return best;
  };
  // qiyin: ehtimollik xaritasi — qolgan kemalarning barcha mumkin joylashuvlari (o'tkazilgan kataklardan o'tmaydi)
  AI.prototype.density = function () {
    var v = this.v, P = emptyB(), i, j;
    this.left.forEach(function (len) { for (i = 0; i < N; i++) for (j = 0; j < N; j++) [false, true].forEach(function (vert) {
      if (len === 1 && vert) return; var ok = true;
      for (var k = 0; k < len; k++) { var a = i + (vert ? k : 0), b = j + (vert ? 0 : k); if (a >= N || b >= N || v[a][b] === 3) { ok = false; break; } }
      if (ok) for (var k2 = 0; k2 < len; k2++) P[i + (vert ? k2 : 0)][j + (vert ? 0 : k2)]++; }); });
    return P;
  };
  AI.prototype.learn = function (r, c, res) {
    var v = this.v;
    if (!res.hit) { v[r][c] = 3; return; }
    v[r][c] = 2; this.hits.push([r, c]);
    if (res.sunk) { around(res.sunk, function (a, d) { if (v[a][d] !== 3) v[a][d] = 3; }); var i = this.left.indexOf(res.sunk.length); if (i >= 0) this.left.splice(i, 1); this.hits = []; }
  };

  function launch(opts) {
    var ui = K.root('sb2d'), st = null, sess = null;
    ui.gl.innerHTML = '<div class="sb-wrap"><div class="sb-top"><span class="sb-st"></span><span class="sb-q">☰</span></div>' +
      '<div class="sb-lbl" id="sbEl">🎯 Dushman</div><div class="sb-grid" id="sbE"></div><div class="sb-lbl" id="sbMl">🚢 Sizning flotingiz</div><div class="sb-grid sm" id="sbM"></div><div class="sb-act"></div></div>';
    var gE = ui.gl.querySelector('#sbE'), gM = ui.gl.querySelector('#sbM'), act = ui.gl.querySelector('.sb-act'), stEl = ui.gl.querySelector('.sb-st');
    ui.gl.querySelector('.sb-q').onclick = function () { mainMenu(); };
    function mkGrid(host, onTap) {
      host.innerHTML = ''; var cells = [];
      for (var i = -1; i < N; i++) for (var j = -1; j < N; j++) {
        var d = document.createElement('div');
        if (i < 0 || j < 0) { d.className = 'sb-h'; d.textContent = i < 0 && j >= 0 ? LET[j] : j < 0 && i >= 0 ? (i + 1) : ''; }
        else { d.className = 'sb-c'; (function (r, c) { d.onclick = function () { onTap(r, c); }; })(i, j); cells.push(d); }
        host.appendChild(d);
      }
      return cells;
    }
    var cE = mkGrid(gE, function (r, c) { fire(r, c); }), cM = mkGrid(gM, function (r, c) { placeTap(r, c); });
    function status(t) { stEl.innerHTML = t; }
    function paint() {
      if (!st) return;
      for (var i = 0; i < N; i++) for (var j = 0; j < N; j++) {
        var e = st.view[i][j], m = st.me.b[i][j], ce = cE[i * N + j], cm = cM[i * N + j];
        ce.className = 'sb-c' + (e === 2 ? ' hit' : e === 3 ? ' miss' : e === 4 ? ' sunk' : '') + (st.phase === 'battle' && st.turn === 'me' && !e ? ' aim' : '');
        cm.className = 'sb-c' + (m === 1 ? ' ship' : m === 2 ? ' hit' : m === 3 ? ' miss' : '') + (st.sel && shipHas(st.sel, i, j) ? ' sel' : '');
      }
      gE.parentNode.classList.toggle('placing', st.phase === 'place');
    }
    function shipHas(s, r, c) { return s.cells.some(function (x) { return x[0] === r && x[1] === c; }); }

    // ---- joylashtirish ----
    function placeTap(r, c) {
      if (!st || st.phase !== 'place') return;
      var s = shipAt(st.me, r, c);
      if (s) { st.sel = st.sel === s ? null : s; K.sfx('tick'); return paint(); }
      if (!st.sel) return;
      moveShip(st.sel, r, c, st.sel.v);
    }
    function moveShip(s, r, c, v) {
      s.cells.forEach(function (x) { st.me.b[x[0]][x[1]] = 0; });
      var len = s._len || s.cells.length;
      if (canPlace(st.me.b, r, c, len, v)) { s.cells = []; s.v = v; for (var k2 = 0; k2 < len; k2++) s.cells.push([r + (v ? k2 : 0), c + (v ? 0 : k2)]); K.sfx('pick'); }
      else K.sfx('hit');
      s.cells.forEach(function (x) { st.me.b[x[0]][x[1]] = 1; }); paint();
    }
    function placeUI(onReady) {
      st.phase = 'place'; status('🚢 Kemalarni joylashtiring: kemani bosing → yangi katakni bosing');
      act.innerHTML = '<button class="ak-mb" data-a="rnd">🎲 Tasodifiy</button><button class="ak-mb" data-a="rot">🔄 Burish</button><button class="ak-mb go" data-a="ok">✅ Tayyor</button>';
      act.querySelector('[data-a=rnd]').onclick = function () { st.me = randomFleet(); st.me.ships.forEach(function (s) { s._len = s.cells.length; }); st.sel = null; paint(); };
      act.querySelector('[data-a=rot]').onclick = function () { if (st.sel) moveShip(st.sel, st.sel.cells[0][0], st.sel.cells[0][1], !st.sel.v); };
      act.querySelector('[data-a=ok]').onclick = function () { st.sel = null; act.innerHTML = ''; onReady(); };
      paint();
    }
    function newState(mode) {
      var me = randomFleet(); me.ships.forEach(function (s) { s._len = s.cells.length; });
      st = { mode: mode, me: me, view: emptyB(), phase: 'place', turn: 'me', shots: 0, sunk: 0, msunk: 0, sel: null, busy: false };
    }

    // ---- jang ----
    function fire(r, c) {
      if (!st || st.phase !== 'battle' || st.turn !== 'me' || st.busy || st.view[r][c]) return;
      st.shots++;
      if (st.mode === 'solo') { applyShot(r, c, receive(st.foe, r, c)); }
      else { st.busy = true; sess.emit({ k: 'fire', r: r, c: c }); status('⏳ Javob kutilmoqda…'); }
    }
    function applyShot(r, c, res) {
      st.busy = false;
      if (res.dup) return;
      st.view[r][c] = res.hit ? 2 : 3;
      if (res.hit) { K.sfx('boom'); K.haptic('medium'); } else K.sfx('tick');
      if (res.sunk) { st.sunk++; around(res.sunk, function (a, d) { if (!st.view[a][d]) st.view[a][d] = 3; }); res.sunk.forEach(function (x) { st.view[x[0]][x[1]] = 4; }); status('🔥 Kema cho‘kdi! (' + st.sunk + '/10) — yana oting'); }
      else if (res.hit) status('💥 Tegdi! Yana oting');
      paint();
      if (res.over) return end(true);
      if (!res.hit) { st.turn = 'foe'; status(st.mode === 'solo' ? '🤖 Raqib o‘ylamoqda…' : '⏳ Raqib otmoqda…'); paint(); if (st.mode === 'solo') setTimeout(aiTurn, 650); }
    }
    function incoming(r, c) {
      var res = receive(st.me, r, c);
      if (res.hit) { K.sfx('boom'); K.haptic('heavy'); if (res.sunk) { st.msunk++; around(res.sunk, function (a, d) { if (!st.me.b[a][d]) st.me.b[a][d] = 3; }); } } else K.sfx('tick');
      paint(); return res;
    }
    function aiTurn() {
      if (!st || st.phase !== 'battle') return;
      var p = st.ai.pick(), res = incoming(p[0], p[1]); st.ai.learn(p[0], p[1], res);
      if (res.over) return end(false);
      if (res.hit) { status('🤖 Raqib tekkizdi ' + LET[p[1]] + (p[0] + 1) + '…'); setTimeout(aiTurn, 650); }
      else { st.turn = 'me'; status('🎯 Sizning navbat'); paint(); }
    }
    function end(win) {
      st.phase = 'over'; K.sfx(win ? 'win' : 'boom');
      if (st.mode === 'solo' && win && opts.onResult) opts.onResult({ score: Math.max(0, 2000 - st.shots * 15) + st.diff * 300, shots: st.shots, diff: st.diff, win: 1 });
      var acc = st.shots ? Math.round(st.view.reduce(function (s, row) { return s + row.filter(function (x) { return x === 2 || x === 4; }).length; }, 0) / st.shots * 100) : 0;
      var items = st.mode === 'solo' ? [['🔁 Yana', function () { solo(st.diff); }, 'go']] : (sess && sess.isHost() ? [['🔁 Qayta o‘ynash', function () { sess.start(); }, 'go']] : [['⏳ Raqib qayta boshlashini kuting', function () {}]]);
      items.push(['🏠 Menyu', function () { leaveMp(); mainMenu(); }]);
      K.menu(ui.menu, win ? '🏆 G‘ALABA!' : '🌊 MAG‘LUBIYAT', 'O‘qlar: ' + st.shots + ' · Aniqlik: ' + acc + '%', items);
    }
    function solo(diff) {
      K.hideMenu(ui.menu); newState('solo'); st.diff = diff; st.foe = randomFleet(); st.ai = new AI(diff);
      placeUI(function () { st.phase = 'battle'; st.turn = 'me'; status('🎯 Sizning navbat — dushman maydoniga oting'); paint(); });
    }
    // ---- online ----
    function mpBegin() {
      K.hideMenu(ui.menu); newState('mp'); st.foeReady = false; st.meReady = false;
      placeUI(function () { st.meReady = true; sess.emit({ k: 'ready' }); tryBattle(); });
    }
    function tryBattle() {
      if (!st.meReady) return;
      if (!st.foeReady) return status('⏳ Raqib kemalarini joylashtirmoqda…');
      st.phase = 'battle'; st.turn = sess.isHost() ? 'me' : 'foe'; status(st.turn === 'me' ? '🎯 Sizning navbat' : '⏳ Raqib boshlaydi…'); paint();
    }
    function startMp(s) {
      sess = s; mpBegin();
      s.on('event', function (e) {
        if (!st || st.mode !== 'mp' || e.u === s.me) return; var d = e.d;
        if (d.k === 'start') { sess.seed = d.seed; return mpBegin(); }
        if (d.k === 'ready') { st.foeReady = true; tryBattle(); }
        else if (d.k === 'fire' && st.phase === 'battle') { var res = incoming(d.r, d.c); sess.emit({ k: 'res', r: d.r, c: d.c, hit: res.hit || 0, sunk: res.sunk || null, over: res.over || 0 });
          if (res.over) end(false); else if (!res.hit) { st.turn = 'me'; status('🎯 Sizning navbat'); paint(); } }
        else if (d.k === 'res') applyShot(d.r, d.c, d);
        else if (d.k === 'left' && st.phase !== 'over') { st.phase = 'over'; K.menu(ui.menu, '🏆 G‘ALABA!', 'Raqib o‘yindan chiqdi', [['🏠 Menyu', function () { leaveMp(); mainMenu(); }, 'go']]); }
        else if (d.k === 'kicked') { leaveMp(); mainMenu(); }
      });
    }
    function leaveMp() { if (sess) { sess.leave(); sess = null; } }
    function mainMenu() {
      K.menu(ui.menu, '🚢 DENGIZ JANGI', 'Kemalarni joylashtiring va dushman flotini birinchi bo‘lib cho‘ktiring. Tekkizsangiz — yana otasiz.',
        [['🤖 Solo — Oson', function () { solo(0); }], ['🤖 Solo — O‘rta', function () { solo(1); }, 'go'], ['🤖 Solo — Qiyin', function () { solo(2); }],
          ['🌐 Online 1×1', function () { window.MPNET.lobby({ game: 'sea', title: 'DENGIZ JANGI', icon: '🚢', min: 2, maxNote: '2 kishilik. Xona egasi birinchi otadi.', onStart: startMp, onClose: mainMenu }); }],
          ['✕ Chiqish', function () { leaveMp(); ui.el.remove(); if (opts.onExit) opts.onExit(); }]]);
    }
    mainMenu();
  }
  window.SEAB = { launch: launch, _test: { randomFleet: randomFleet, receive: receive, AI: AI, canPlace: canPlace } };
})();
