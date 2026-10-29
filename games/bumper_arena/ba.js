/* BUMPER ARENA 3D — sumo uslubidagi to'qnashuv: raqiblarni torayuvchi maydondan itarib tushiring. Solo + online. ORIGINAL. */
(function () {
  'use strict';
  var T = window.THREE, K = window.AKIT;
  var R0 = 22, RMIN = 9, SHRINK = 100, CR = 1.3, LIVES = 3, ACC = 26, FRIC = 1.6, VMAX = 15, DASH = 19, DASH_CD = 2.4, TLIM = 180;
  var BOTN = ['Gurzi', 'Tulpor', 'Bulldog', 'Pinak', 'Zilzila'];

  function launch(opts) {
    var ui = K.root('ba3d'), W = K.world(ui.gl, { sky: 0x160a24 }), sc = W.scene, keys = K.keys();
    var G = null, stop = null, sess = null;
    var plat = new T.Mesh(new T.CylinderGeometry(1, 1, 1.2, 64), new T.MeshStandardMaterial({ color: 0x241a4a, roughness: 0.5, metalness: 0.2 }));
    plat.position.y = -0.6; sc.add(plat);
    var ring = new T.Mesh(new T.TorusGeometry(1, 0.012, 8, 96), new T.MeshBasicMaterial({ color: 0xff3ea5 })); ring.rotation.x = Math.PI / 2; ring.position.y = 0.05; sc.add(ring);
    var lava = new T.Mesh(new T.PlaneGeometry(300, 300), new T.MeshBasicMaterial({ color: 0x2a0518 })); lava.rotation.x = -Math.PI / 2; lava.position.y = -12; sc.add(lava);
    var mvS = K.stick(ui.ctl, 'l', 'Yurish'), dashB = K.button(ui.ctl, '', '💥');

    function carMesh(color, name) {
      var g = new T.Group(), c = new T.MeshStandardMaterial({ color: color, roughness: 0.35, metalness: 0.4, emissive: color, emissiveIntensity: 0.15 });
      var body = new T.Mesh(new T.CylinderGeometry(1.05, 1.15, 0.7, 20), c); body.position.y = 0.55; g.add(body);
      var bump = new T.Mesh(new T.TorusGeometry(1.2, 0.18, 8, 24), new T.MeshStandardMaterial({ color: 0x111111, roughness: 0.9 })); bump.rotation.x = Math.PI / 2; bump.position.y = 0.4; g.add(bump);
      var cab = new T.Mesh(new T.SphereGeometry(0.55, 14, 10, 0, Math.PI * 2, 0, Math.PI / 2), new T.MeshStandardMaterial({ color: 0x9fe8ff, transparent: true, opacity: 0.75 })); cab.position.y = 0.9; g.add(cab);
      var nose = new T.Mesh(new T.BoxGeometry(0.5, 0.2, 0.4), new T.MeshBasicMaterial({ color: 0xffffff })); nose.position.set(0, 0.7, -0.95); g.add(nose);
      var lb = K.label(name, '#' + color.toString(16).padStart(6, '0')); lb.position.y = 2.4; g.add(lb);
      sc.add(g); return { g: g, c: c };
    }
    function newCar(id, name, color, bot) {
      var c = { id: id, name: name, color: color, x: 0, z: 0, y: 0, vx: 0, vz: 0, a: 0, lives: LIVES, fall: 0, out: false, resp: 0, dcd: 0, dashT: 0,
        last: null, lastT: 0, knocks: 0, bot: bot, remote: false, tx: 0, tz: 0, flash: 0, ai: { t: 0 } };
      c.m = carMesh(color, name); G.cars[id] = c; return c;
    }
    function rad() { return Math.max(RMIN, R0 - (R0 - RMIN) * Math.min(1, G.t / SHRINK)); }
    function place(c, i, n) { var a = i / Math.max(1, n) * Math.PI * 2 + (G.seed % 7); c.x = Math.cos(a) * rad() * 0.6; c.z = Math.sin(a) * rad() * 0.6; c.vx = c.vz = 0; c.y = 0; c.fall = 0; c.a = Math.atan2(c.x, c.z); c.m.g.visible = true; }

    function collide(a, b, onlyA) {
      var dx = b.x - a.x, dz = b.z - a.z, d = Math.hypot(dx, dz);
      if (d >= CR * 2 || d < 1e-4 || a.fall || b.fall) return;
      var nx = dx / d, nz = dz / d, ov = CR * 2 - d;
      var rv = (b.vx - a.vx) * nx + (b.vz - a.vz) * nz;
      var j = Math.max(0, -rv) * 1.15 + ov * 6;
      var ka = 1 + (b.dashT > 0 ? 0.9 : 0), kb = 1 + (a.dashT > 0 ? 0.9 : 0);
      a.vx -= nx * j * ka; a.vz -= nz * j * ka; a.x -= nx * ov / 2; a.z -= nz * ov / 2; a.last = b.id; a.lastT = 3; a.flash = 0.15;
      if (!onlyA) { b.vx += nx * j * kb; b.vz += nz * j * kb; b.x += nx * ov / 2; b.z += nz * ov / 2; b.last = a.id; b.lastT = 3; b.flash = 0.15; }
      if (a === G.me || b === G.me) { K.sfx('bump'); K.haptic(j > 10 ? 'heavy' : 'light'); }
    }
    function drive(c, ix, iz, dash, dt) {
      var mag = Math.min(1, Math.hypot(ix, iz));
      if (mag > 0.1) { c.vx += ix / Math.max(mag, 1) * ACC * dt; c.vz += iz / Math.max(mag, 1) * ACC * dt; c.a = K.lerpAng(c.a, Math.atan2(-ix, -iz), Math.min(1, dt * 10)); }
      if (dash && c.dcd <= 0) { c.dcd = DASH_CD; c.dashT = 0.35; c.vx += -Math.sin(c.a) * DASH; c.vz += -Math.cos(c.a) * DASH; if (c === G.me) K.sfx('shot'); }
    }
    function physics(c, dt) {
      c.dcd -= dt; c.dashT -= dt; c.lastT -= dt; c.flash -= dt;
      if (c.fall) { c.fall += dt; c.y -= 14 * c.fall * dt * 3; c.x += c.vx * dt; c.z += c.vz * dt; return; }
      var sp = Math.hypot(c.vx, c.vz), lim = c.dashT > 0 ? VMAX * 2 : VMAX;
      if (sp > lim) { c.vx *= lim / sp; c.vz *= lim / sp; }
      c.vx -= c.vx * FRIC * dt; c.vz -= c.vz * FRIC * dt;
      c.x += c.vx * dt; c.z += c.vz * dt;
      if (Math.hypot(c.x, c.z) > rad() + 0.4) c.fall = 0.001;
    }
    function bot(c, dt) {
      var tgt = null, bd = 1e9, r = rad();
      for (var k in G.cars) { var o = G.cars[k]; if (o === c || o.out || o.fall) continue; var d = Math.hypot(o.x - c.x, o.z - c.z); if (d < bd) { bd = d; tgt = o; } }
      var ix = 0, iz = 0, dist = Math.hypot(c.x, c.z);
      if (tgt) { ix = tgt.x - c.x; iz = tgt.z - c.z; var n = Math.hypot(ix, iz) || 1; ix /= n; iz /= n; }
      if (dist > r * 0.72) { ix = ix * 0.3 - c.x / dist; iz = iz * 0.3 - c.z / dist; }
      c.ai.t -= dt; var dash = false;
      if (tgt && bd < 7 && c.ai.t <= 0) { var want = Math.atan2(-(tgt.x - c.x), -(tgt.z - c.z)), off = Math.abs(((want - c.a + Math.PI * 3) % (Math.PI * 2)) - Math.PI);
        if (off < 0.35 && Math.hypot(tgt.x, tgt.z) > dist - 1) { dash = true; c.ai.t = 1 + Math.random() * (2.2 - G.diff * 0.6); } }
      drive(c, ix * (0.75 + G.diff * 0.12), iz * (0.75 + G.diff * 0.12), dash, dt);
    }
    function eliminate(c) {
      c.lives--; c.out = c.lives <= 0; c.resp = 2; c.m.g.visible = false; W.boom(c.x, -4, c.z, 0xff3ea5, 2);
      var k = c.last && c.lastT > 0 ? G.cars[c.last] : null;
      if (k && k !== c) k.knocks++;
      feed((k && k !== c ? k.name + ' ➜ ' : '') + c.name + (c.out ? ' ☠️ chiqdi' : ' tushdi'));
      if (c === G.me) { K.haptic('heavy'); center(c.out ? '☠️ Siz chiqdingiz' : '💧 Tushib ketdingiz! Jon: ' + c.lives, 2); }
    }

    ui.hud.innerHTML = '<div class="ak-box" id="baL"></div><div class="ak-box" id="baT"></div><div class="ak-box ak-q" id="baQ">☰</div>';
    var board = K.el('<div class="ak-board"></div>'), cen = K.el('<div class="ak-center"></div>'); ui.el.appendChild(board); ui.el.appendChild(cen);
    ui.hud.querySelector('#baQ').onclick = function () { pause(); };
    var cenT = 0; function center(t, s) { cen.innerHTML = t; cenT = s || 1.5; }
    function feed(t) { G.feed.unshift([t, 3]); G.feed.length = Math.min(4, G.feed.length); }
    function hud() {
      var me = G.me; ui.hud.querySelector('#baL').innerHTML = '❤️'.repeat(Math.max(0, me.lives)) + ' · 💥 ' + (me.dcd > 0 ? me.dcd.toFixed(1) : 'TAYYOR');
      var left = Math.max(0, TLIM - G.t); ui.hud.querySelector('#baT').textContent = '⏱ ' + Math.floor(left / 60) + ':' + ('0' + Math.floor(left % 60)).slice(-2);
      var list = Object.keys(G.cars).map(function (k) { return G.cars[k]; }).sort(function (a, b) { return b.lives - a.lives || b.knocks - a.knocks; });
      board.innerHTML = list.map(function (c) { return '<div class="' + (c === me ? 'me' : '') + '"><span>' + K.esc(c.name) + '</span><b>' + (c.out ? '☠️' : '❤️' + c.lives) + ' · ' + c.knocks + '</b></div>'; }).join('') +
        G.feed.map(function (f) { return '<div style="opacity:.7;font-size:11px">' + K.esc(f[0]) + '</div>'; }).join('');
    }

    function step(dt) {
      if (!G || G.over) { W.render(dt); return; }
      G.t += dt; var r = rad(), me = G.me;
      plat.scale.set(r, 1, r); ring.scale.set(r, r, 1);
      if (!me.out && !me.fall && me.resp <= 0) {
        var ix = mvS.x, iz = mvS.y;
        if (keys.KeyW || keys.ArrowUp) iz = -1; if (keys.KeyS || keys.ArrowDown) iz = 1; if (keys.KeyA || keys.ArrowLeft) ix = -1; if (keys.KeyD || keys.ArrowRight) ix = 1;
        drive(me, ix, iz, dashB.on || keys.Space, dt);
      }
      var ids = Object.keys(G.cars);
      ids.forEach(function (k) {
        var c = G.cars[k];
        if (c.remote) { var f = Math.min(1, dt * 12); c.x += (c.tx - c.x) * f; c.z += (c.tz - c.z) * f; c.a = K.lerpAng(c.a, c.ta || 0, f); }
        else if (c.out) { /* kuzatuvchi */ }
        else if (c.resp > 0 && !c.fall) { c.resp -= dt; if (c.resp <= 0) { place(c, Math.floor(Math.random() * 8), 8); c.m.g.visible = true; } }
        else { if (c.bot && !c.fall) bot(c, dt); physics(c, dt); if (c.fall > 1.1) { c.fall = 0; if (G.mode === 'mp') { if (c === me) sess.emit({ k: 'out', by: c.lastT > 0 ? c.last : null }); c.resp = 2; c.m.g.visible = false; } else eliminate(c); } }
      });
      for (var i = 0; i < ids.length; i++) for (var j = i + 1; j < ids.length; j++) {
        var a = G.cars[ids[i]], b = G.cars[ids[j]];
        if (!a.m.g.visible || !b.m.g.visible) continue;
        if (G.mode === 'solo') collide(a, b, false);
        else if (a === me) collide(a, b, true); else if (b === me) collide(b, a, true);
      }
      ids.forEach(function (k) { var c = G.cars[k]; c.m.g.position.set(c.x, c.y, c.z); c.m.g.rotation.y = c.a; c.m.c.emissiveIntensity = c.dashT > 0 ? 1 : c.flash > 0 ? 0.7 : 0.15; });
      if (G.mode === 'mp') sess.send({ x: +me.x.toFixed(2), z: +me.z.toFixed(2), a: +me.a.toFixed(2), vx: +me.vx.toFixed(2), vz: +me.vz.toFixed(2), l: me.lives, d: me.dashT > 0 ? 1 : 0, v: me.m.g.visible ? 1 : 0 });
      G.feed.forEach(function (f) { f[1] -= dt; }); G.feed = G.feed.filter(function (f) { return f[1] > 0; });
      cenT -= dt; if (cenT <= 0) cen.innerHTML = '';
      var alive = ids.map(function (k) { return G.cars[k]; }).filter(function (c) { return !c.out; });
      if ((alive.length <= 1 && ids.length > 1) || G.t >= TLIM || (me.out && G.mode === 'solo')) finish(alive);
      var cx = me.out ? 0 : me.x, cz = me.out ? 0 : me.z;
      W.cam.position.set(cx * 0.6, 30, cz * 0.6 + 22); W.cam.lookAt(cx * 0.6, 0, cz * 0.6);
      hud(); W.render(dt);
    }
    function finish(alive) {
      if (G.over) return; G.over = true;
      var list = Object.keys(G.cars).map(function (k) { return G.cars[k]; }).sort(function (a, b) { return (b.out ? 0 : 1) - (a.out ? 0 : 1) || b.lives - a.lives || b.knocks - a.knocks; });
      var win = list[0] === G.me && !G.me.out; K.sfx(win ? 'win' : 'boom');
      if (G.mode === 'solo' && opts.onResult) opts.onResult({ score: G.me.knocks * 150 + Math.floor(Math.min(G.t, 600)) * 5 * (G.me.out ? 0 : 1) + (win ? 600 : 0), knocks: G.me.knocks, time: Math.floor(Math.min(G.t, 600)), win: win ? 1 : 0 });
      var rows = list.map(function (c, i) { return (i + 1) + '. ' + K.esc(c.name) + ' — 💥' + c.knocks + (c.out ? ' ☠️' : ' ❤️' + c.lives); }).join('<br>');
      var items = G.mode === 'solo' ? [['🔁 Yana', function () { start(G.diff); }, 'go']] : (sess && sess.isHost() ? [['🔁 Qayta boshlash', function () { sess.start(); }, 'go']] : [['⏳ Xona egasini kuting', function () {}]]);
      items.push(['🏠 Menyu', function () { leaveMp(); mainMenu(); }]);
      K.menu(ui.menu, win ? '🏆 CHEMPION!' : 'RAUND TUGADI', rows, items);
    }
    function reset(seed, mode) {
      if (G) for (var k in G.cars) sc.remove(G.cars[k].m.g);
      G = { mode: mode, seed: seed, t: 0, cars: {}, feed: [], over: false, diff: 1 };
    }
    function start(diff) {
      reset((Math.random() * 1e9) >>> 0, 'solo'); G.diff = diff;
      G.me = newCar('me', opts.playerName || 'Siz', K.COLORS[0], false);
      for (var i = 0; i < 5; i++) newCar('b' + i, BOTN[i], K.COLORS[i + 1], true);
      var ids = Object.keys(G.cars); ids.forEach(function (k, i) { place(G.cars[k], i, ids.length); });
      K.hideMenu(ui.menu); center('💥 Itarib tushiring!', 2);
    }
    function mpBegin() {
      reset(sess.seed, 'mp'); G.me = newCar(sess.me, opts.playerName || 'Siz', K.COLORS[0], false);
      var idx = sess.players.map(function (p) { return p.uid; }).sort().indexOf(sess.me); place(G.me, Math.max(0, idx), Math.max(2, sess.players.length));
      K.hideMenu(ui.menu); center('🌐 Online · oxirgi qolgan yutadi', 2);
    }
    function startMp(s) {
      sess = s; mpBegin();
      s.on('sync', function (r) {
        if (!G || G.mode !== 'mp') return; var seen = {};
        r.players.forEach(function (p, i) {
          if (p.uid === s.me) return; seen[p.uid] = 1;
          var c = G.cars[p.uid]; if (!c) { c = newCar(p.uid, p.name, K.COLORS[(i % 7) + 1], false); c.remote = true; if (p.state) { c.x = p.state.x; c.z = p.state.z; } }
          if (p.state) { c.tx = p.state.x; c.tz = p.state.z; c.ta = p.state.a; c.vx = p.state.vx; c.vz = p.state.vz; c.dashT = p.state.d ? 0.1 : 0; c.lives = p.state.l; c.out = p.state.l <= 0; c.m.g.visible = !!p.state.v && !c.out; }
        });
        for (var k in G.cars) if (G.cars[k].remote && !seen[k]) { sc.remove(G.cars[k].m.g); delete G.cars[k]; }
      });
      s.on('event', function (e) {
        if (!G || G.mode !== 'mp') return; var d = e.d;
        if (d.k === 'start') { sess.seed = d.seed; return mpBegin(); }
        if (d.k === 'out') { var c = G.cars[e.u]; if (c) { if (c !== G.me) { c.last = d.by; c.lastT = 1; } else { c.last = d.by; c.lastT = 1; } eliminate(c); if (c !== G.me) c.lives = Math.max(c.lives, 0); } }
        if (d.k === 'kicked') { leaveMp(); mainMenu(); }
      });
    }
    function leaveMp() { if (sess) { sess.leave(); sess = null; } }
    function pause() {
      if (!G || G.over) return; var solo = G.mode === 'solo'; if (solo) G.over = true;
      K.menu(ui.menu, '⏸ PAUZA', '', [['▶ Davom etish', function () { if (solo) G.over = false; K.hideMenu(ui.menu); }, 'go'], ['🏠 Menyu', function () { leaveMp(); mainMenu(); }], ['✕ Chiqish', exit]]);
    }
    function mainMenu() {
      if (G) G.over = true;
      K.menu(ui.menu, '💥 BUMPER ARENA', 'Maydon torayib boradi! Raqiblarni chetdan itarib tushiring. 💥 — zarba (dash). Har kimda 3 jon.',
        [['🤖 Solo — Oson', function () { start(0); }], ['🤖 Solo — O‘rta', function () { start(1); }, 'go'], ['🤖 Solo — Qiyin', function () { start(2); }],
          ['🌐 Online (6 kishigacha)', function () { window.MPNET.lobby({ game: 'bumper', title: 'BUMPER ARENA', icon: '💥', min: 2, maxNote: 'Oxirgi qolgan g‘olib. 3 jon.', onStart: startMp, onClose: mainMenu }); }],
          ['✕ Chiqish', exit]]);
    }
    function exit() { leaveMp(); if (stop) stop(); keys.off(); W.dispose(); ui.el.remove(); if (opts.onExit) opts.onExit(); }
    reset(1, 'solo'); G.me = newCar('me', opts.playerName || 'Siz', K.COLORS[0], false); G.over = true;
    stop = K.loop(step); mainMenu();
  }
  window.BUMPA = { launch: launch };
})();
