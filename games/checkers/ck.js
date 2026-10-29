/* SHASHKA — rus shashkasi qoidalari: urish majburiy, ketma-ket urish, oddiy tosh orqaga ham uradi, damka uzoqqa yuradi/uradi.
   Solo (alpha-beta AI, 3 daraja) va online 1v1. Taxta: 64 katak, 1/2 = oq tosh/damka, -1/-2 = qora. Oq pastda, birinchi yuradi. */
(function () {
  'use strict';
  var K = window.AKIT, DIRS = [[-1, -1], [-1, 1], [1, -1], [1, 1]];
  function init() { var b = []; for (var i = 0; i < 64; i++) { var r = i >> 3, c = i & 7, dark = (r + c) % 2 === 1; b.push(dark && r < 3 ? -1 : dark && r > 4 ? 1 : 0); } return b; }
  function inb(r, c) { return r >= 0 && r < 8 && c >= 0 && c < 8; }
  function own(p, side) { return p * side > 0; }

  // Barcha yurishlar: {path:[sq..], caps:[sq..], prom}
  function moves(b, side) {
    var caps = [], quiet = [];
    for (var sq = 0; sq < 64; sq++) {
      var p = b[sq]; if (!own(p, side)) continue;
      capDFS(b, sq, p, [sq], [], caps);
      var r = sq >> 3, c = sq & 7, king = Math.abs(p) === 2;
      DIRS.forEach(function (d) {
        if (!king && d[0] !== -side) return;
        for (var k = 1; k < (king ? 8 : 2); k++) { var rr = r + d[0] * k, cc = c + d[1] * k; if (!inb(rr, cc) || b[rr * 8 + cc]) break;
          quiet.push({ path: [sq, rr * 8 + cc], caps: [], prom: !king && (rr === (side > 0 ? 0 : 7)) }); }
      });
    }
    return caps.length ? caps : quiet;
  }
  function capDFS(b, from, piece, path, taken, out) {
    var side = piece > 0 ? 1 : -1, king = Math.abs(piece) === 2, r = from >> 3, c = from & 7, found = false;
    DIRS.forEach(function (d) {
      if (king) {
        var k = 1, rr, cc;
        while (inb(rr = r + d[0] * k, cc = c + d[1] * k) && b[rr * 8 + cc] === 0) k++;
        if (!inb(rr, cc)) return; var vic = rr * 8 + cc; if (!own(b[vic], -side) || taken.indexOf(vic) >= 0) return;
        var lands = [], kk = k + 1;
        while (inb(rr = r + d[0] * kk, cc = c + d[1] * kk) && (b[rr * 8 + cc] === 0 || rr * 8 + cc === path[0])) { lands.push(rr * 8 + cc); kk++; }
        if (!lands.length) return;
        // davom ettirib bo'ladigan qo'nish joylari bo'lsa — faqat ular
        var cont = lands.filter(function (L) { var tmp = []; capDFS(b, L, piece, path.concat(L), taken.concat(vic), tmp); return tmp.length; });
        (cont.length ? cont : lands).forEach(function (L) { found = true; var n0 = out.length; capDFS(b, L, piece, path.concat(L), taken.concat(vic), out);
          if (out.length === n0) out.push({ path: path.concat(L), caps: taken.concat(vic), prom: false }); });
      } else {
        var vr = r + d[0], vc = c + d[1], lr = r + d[0] * 2, lc = c + d[1] * 2;
        if (!inb(lr, lc)) return; var v = vr * 8 + vc, L = lr * 8 + lc;
        if (!own(b[v], -side) || taken.indexOf(v) >= 0 || (b[L] !== 0 && L !== path[0])) return;
        found = true; var promote = lr === (side > 0 ? 0 : 7), n0 = out.length;
        capDFS(b, L, promote ? side * 2 : piece, path.concat(L), taken.concat(v), out);
        if (out.length === n0) out.push({ path: path.concat(L), caps: taken.concat(v), prom: promote });
      }
    });
    return found;
  }
  function apply(b, m) {
    var n = b.slice(), p = n[m.path[0]]; n[m.path[0]] = 0;
    m.caps.forEach(function (s) { n[s] = 0; });
    var to = m.path[m.path.length - 1], side = p > 0 ? 1 : -1;
    if (Math.abs(p) === 1 && (m.prom || m.path.some(function (s) { return (s >> 3) === (side > 0 ? 0 : 7); }))) p = side * 2;
    n[to] = p; return n;
  }
  function evalB(b) {
    var s = 0;
    for (var i = 0; i < 64; i++) { var p = b[i]; if (!p) continue; var r = i >> 3, c = i & 7, v = Math.abs(p) === 2 ? 320 : 100;
      if (Math.abs(p) === 1) v += (p > 0 ? 7 - r : r) * 4; if (c >= 2 && c <= 5 && r >= 2 && r <= 5) v += 6; s += p > 0 ? v : -v; }
    return s;
  }
  function search(b, side, depth, alpha, beta) {
    var ms = moves(b, side);
    if (!ms.length) return -100000 - depth;
    if (depth <= 0 && !ms[0].caps.length) return side * evalB(b);
    if (depth <= -4) return side * evalB(b);
    ms.sort(function (a, c) { return c.caps.length - a.caps.length; });
    for (var i = 0; i < ms.length; i++) { var v = -search(apply(b, ms[i]), -side, depth - 1, -beta, -alpha); if (v > alpha) alpha = v; if (alpha >= beta) break; }
    return alpha;
  }
  function bestMove(b, side, diff) {
    var ms = moves(b, side), depth = [2, 4, 6][diff], best = null, bv = -1e9;
    ms.forEach(function (m) { var v = -search(apply(b, m), -side, depth - 1, -1e9, 1e9) + (diff === 0 ? Math.random() * 120 : Math.random() * 3); if (v > bv) { bv = v; best = m; } });
    return best;
  }

  function launch(opts) {
    var ui = K.root('ck2d'), st = null, sess = null;
    ui.gl.innerHTML = '<div class="ck-wrap"><div class="ck-top"><span class="ck-st"></span><span class="ck-q">☰</span></div><div class="ck-cnt"></div><div class="ck-board"></div><div class="ck-hint">Toshni bosing → yashil katakka yuring. Urish majburiy.</div></div>';
    var boardEl = ui.gl.querySelector('.ck-board'), stEl = ui.gl.querySelector('.ck-st'), cntEl = ui.gl.querySelector('.ck-cnt'), cells = [];
    ui.gl.querySelector('.ck-q').onclick = function () { if (st && st.over === false && st.mode === 'mp') return confirmLeave(); mainMenu(); };
    for (var i = 0; i < 64; i++) { var d = document.createElement('div'); d.className = 'ck-c' + (((i >> 3) + (i & 7)) % 2 ? ' dk' : ''); (function (k) { d.onclick = function () { tap(k); }; })(i); boardEl.appendChild(d); cells.push(d); }
    function view(i) { return st && st.me === -1 ? 63 - i : i; } // qora uchun taxta aylantiriladi
    function paint() {
      var targets = {}; if (st.sel != null) st.legal.forEach(function (m) { if (m.path[0] === st.sel) targets[m.path[m.path.length - 1]] = 1; });
      var movable = {}; if (st.turn === st.me && !st.over) st.legal.forEach(function (m) { movable[m.path[0]] = 1; });
      for (var v = 0; v < 64; v++) {
        var sq = view(v), p = st.b[sq], el = cells[v];
        el.className = 'ck-c' + (((v >> 3) + (v & 7)) % 2 ? ' dk' : '') + (sq === st.sel ? ' sel' : '') + (targets[sq] ? ' tgt' : '') + (st.last && st.last.indexOf(sq) >= 0 ? ' last' : '');
        el.innerHTML = p ? '<i class="ck-p ' + (p > 0 ? 'w' : 'b') + (Math.abs(p) === 2 ? ' k' : '') + (movable[sq] && st.legal[0].caps.length ? ' must' : '') + '"></i>' : '';
      }
      var w = st.b.filter(function (x) { return x > 0; }).length, bl = st.b.filter(function (x) { return x < 0; }).length;
      cntEl.innerHTML = '⚪ ' + w + ' &nbsp; ⚫ ' + bl + (st.mode === 'mp' ? ' &nbsp; · Siz: ' + (st.me > 0 ? '⚪' : '⚫') : '');
    }
    function status(t) { stEl.innerHTML = t; }
    function tap(sqv) {
      if (!st || st.over || st.turn !== st.me || st.busy) return;
      var sq = view(sqv);
      if (own(st.b[sq], st.me)) { if (st.legal.some(function (m) { return m.path[0] === sq; })) { st.sel = sq; K.sfx('tick'); } else K.sfx('hit'); return paint(); }
      if (st.sel == null) return;
      var m = st.legal.filter(function (x) { return x.path[0] === st.sel && x.path[x.path.length - 1] === sq; })
        .sort(function (a, b) { return b.caps.length - a.caps.length; })[0];
      if (!m) return;
      play(m, true);
    }
    function play(m, mine) {
      st.b = apply(st.b, m); st.sel = null; st.last = m.path; st.plies = m.caps.length || m.prom ? 0 : st.plies + 1;
      K.sfx(m.caps.length ? 'boom' : 'pick'); if (m.caps.length) K.haptic('medium');
      if (mine && st.mode === 'mp') sess.emit({ k: 'mv', path: m.path, caps: m.caps });
      st.turn = -st.turn; st.legal = moves(st.b, st.turn); paint();
      if (!st.legal.length) return end(st.turn !== st.me ? 'win' : 'lose');
      if (st.plies >= 60) return end('draw');
      if (st.turn === st.me) status(st.legal[0].caps.length ? '⚔️ Siz urishingiz shart!' : '🎯 Sizning navbat');
      else { status(st.mode === 'solo' ? '🤖 O‘ylamoqda…' : '⏳ Raqib yurishi…'); if (st.mode === 'solo') { st.busy = true; setTimeout(aiMove, 350); } }
    }
    function aiMove() { st.busy = false; if (!st || st.over) return; var m = bestMove(st.b, st.turn, st.diff); if (m) play(m, false); }
    function end(res) {
      st.over = true; K.sfx(res === 'win' ? 'win' : 'boom');
      var left = st.b.filter(function (x) { return own(x, st.me); }).length;
      if (st.mode === 'solo' && res === 'win' && opts.onResult) opts.onResult({ score: 500 + st.diff * 500 + left * 40, diff: st.diff, left: left, win: 1 });
      var items = st.mode === 'solo' ? [['🔁 Yana', function () { solo(st.diff); }, 'go']] : (sess && sess.isHost() ? [['🔁 Qayta o‘ynash', function () { sess.start(); }, 'go']] : [['⏳ Raqib qayta boshlashini kuting', function () {}]]);
      items.push(['🏠 Menyu', function () { leaveMp(); mainMenu(); }]);
      K.menu(ui.menu, res === 'win' ? '🏆 G‘ALABA!' : res === 'draw' ? '🤝 DURANG' : '😔 MAG‘LUBIYAT', 'Qolgan toshlaringiz: ' + left, items);
    }
    function newGame(mode, me) { st = { mode: mode, b: init(), turn: 1, me: me, sel: null, last: null, plies: 0, over: false, busy: false }; st.legal = moves(st.b, 1); K.hideMenu(ui.menu); paint(); }
    function solo(diff) { newGame('solo', 1); st.diff = diff; status('🎯 Sizning navbat (⚪ oq)'); }
    function mpBegin() { newGame('mp', sess.isHost() ? 1 : -1); status(st.me === 1 ? '🎯 Siz oq — birinchi yurasiz' : '⏳ Siz qora — raqib boshlaydi'); }
    function startMp(s) {
      sess = s; mpBegin();
      s.on('event', function (e) {
        if (!st || st.mode !== 'mp' || e.u === s.me) return; var d = e.d;
        if (d.k === 'start') return mpBegin();
        if (d.k === 'mv' && st.turn !== st.me && !st.over) {
          var m = st.legal.filter(function (x) { return x.path.join() === (d.path || []).join(); })[0];
          if (m) play(m, false); else status('⚠️ Sinxron xatosi — qayta boshlang');
        } else if (d.k === 'left' && !st.over) { st.over = true; K.menu(ui.menu, '🏆 G‘ALABA!', 'Raqib o‘yindan chiqdi', [['🏠 Menyu', function () { leaveMp(); mainMenu(); }, 'go']]); }
        else if (d.k === 'kicked') { leaveMp(); mainMenu(); }
      });
    }
    function confirmLeave() { K.menu(ui.menu, '🚪 Chiqasizmi?', 'Online o‘yindan chiqsangiz — mag‘lubiyat', [['✅ Ha', function () { leaveMp(); mainMenu(); }, 'go'], ['↩ Yo‘q', function () { K.hideMenu(ui.menu); }]]); }
    function leaveMp() { if (sess) { sess.leave(); sess = null; } }
    function mainMenu() {
      K.menu(ui.menu, '⚪ SHASHKA ⚫', 'Rus shashkasi qoidalari: urish majburiy, ketma-ket urish, damka uzoqqa yuradi. Barcha toshlarni olgan yoki yo‘lini to‘sgan yutadi.',
        [['🤖 Solo — Oson', function () { solo(0); }], ['🤖 Solo — O‘rta', function () { solo(1); }, 'go'], ['🤖 Solo — Usta', function () { solo(2); }],
          ['🌐 Online 1×1', function () { window.MPNET.lobby({ game: 'checkers', title: 'SHASHKA', icon: '⚪', min: 2, maxNote: 'Xona egasi — oq, birinchi yuradi.', onStart: startMp, onClose: mainMenu }); }],
          ['✕ Chiqish', function () { leaveMp(); ui.el.remove(); if (opts.onExit) opts.onExit(); }]]);
    }
    mainMenu();
  }
  window.CHECK = { launch: launch, _test: { init: init, moves: moves, apply: apply, bestMove: bestMove } };
})();
