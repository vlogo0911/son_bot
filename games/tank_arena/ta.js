/* TANK ARENA 3D — solo (botlar) va online deathmatch. ORIGINAL o'yin. Talab: three r128, AKIT, MPNET. */
(function () {
  'use strict';
  var T = window.THREE, K = window.AKIT;
  var A = 36, KILLS_WIN = 15, MATCH_T = 240, BUL_V = 30, BUL_LIFE = 2.2, DMG = 25, R = 1.4;
  var BOTN = ['Bo‘ron', 'Temir', 'Shamol', 'Chaqmoq', 'Qoplon', 'Burgut', 'Tosh'];
  var PU = { hp: [0x5dff7a, '❤️ +50'], sh: [0x3ea8ff, '🛡 Qalqon'], tr: [0xffc93e, '🔱 Uch o‘q'], sp: [0xc77dff, '⚡ Tezlik'] };
  var PUK = ['hp', 'sh', 'tr', 'sp'];

  function launch(opts) {
    var ui = K.root('ta3d'), W = K.world(ui.gl, { sky: 0x0b1024 }), sc = W.scene, keys = K.keys();
    var G = null, stop = null, sess = null;
    K.grid(sc, A * 2 + 8, 0x2f4bff);
    var obsGroup = new T.Group(); sc.add(obsGroup);
    var mvS = K.stick(ui.ctl, 'l', 'Yurish'), aimS = K.stick(ui.ctl, 'r', 'Nishon + o‘q');
    var mouse = { x: 0, z: 0, on: false, fire: false };
    var ray = new T.Raycaster(), plane = new T.Plane(new T.Vector3(0, 1, 0), 0), v2 = new T.Vector2(), hitP = new T.Vector3();
    ui.gl.addEventListener('pointermove', function (e) { if (e.pointerType !== 'mouse') return; v2.set(e.clientX / innerWidth * 2 - 1, -e.clientY / innerHeight * 2 + 1); ray.setFromCamera(v2, W.cam); if (ray.ray.intersectPlane(plane, hitP)) { mouse.x = hitP.x; mouse.z = hitP.z; mouse.on = true; } });
    addEventListener('mousedown', md); addEventListener('mouseup', mu);
    function md(e) { if (e.button === 0) mouse.fire = true; } function mu() { mouse.fire = false; }

    // ---- xarita ----
    var OBS = [], SPAWN = [];
    function buildMap(seed) {
      while (obsGroup.children.length) { var o = obsGroup.children.pop(); o.geometry.dispose(); }
      OBS = []; SPAWN = []; var rnd = K.rng(seed);
      var mat = new T.MeshStandardMaterial({ color: 0x2a335c, roughness: 0.6, emissive: 0x0a1030 }), edge = new T.MeshBasicMaterial({ color: 0x4f7bff });
      function box(x, z, w, d, h) {
        var m = new T.Mesh(new T.BoxGeometry(w, h || 2.2, d), mat); m.position.set(x, (h || 2.2) / 2, z); obsGroup.add(m);
        var e = new T.Mesh(new T.BoxGeometry(w + 0.05, 0.12, d + 0.05), edge); e.position.set(x, (h || 2.2) + 0.02, z); obsGroup.add(e);
        OBS.push({ x: x, z: z, hw: w / 2, hd: d / 2 });
      }
      box(0, -A - 0.5, A * 2 + 2, 1, 2.6); box(0, A + 0.5, A * 2 + 2, 1, 2.6); box(-A - 0.5, 0, 1, A * 2, 2.6); box(A + 0.5, 0, 1, A * 2, 2.6);
      for (var i = 0; i < 8; i++) { var an = i / 8 * Math.PI * 2; SPAWN.push([Math.cos(an) * 28, Math.sin(an) * 28]); }
      var n = 0, tries = 0;
      while (n < 18 && tries++ < 400) {
        var w = 2 + rnd() * 6, d = 2 + rnd() * 6, x = (rnd() * 2 - 1) * (A - 6), z = (rnd() * 2 - 1) * (A - 6);
        if (Math.hypot(x, z) < 5) continue;
        if (SPAWN.some(function (s) { return Math.hypot(s[0] - x, s[1] - z) < 6; })) continue;
        if (OBS.slice(4).some(function (o) { return Math.abs(o.x - x) < o.hw + w / 2 + 2.5 && Math.abs(o.z - z) < o.hd + d / 2 + 2.5; })) continue;
        box(x, z, w, d); n++;
      }
    }
    function solid(x, z, r) { for (var i = 0; i < OBS.length; i++) { var o = OBS[i]; if (Math.abs(x - o.x) < o.hw + r && Math.abs(z - o.z) < o.hd + r) return o; } return null; }
    function pushOut(t) {
      for (var i = 0; i < OBS.length; i++) {
        var o = OBS[i], dx = t.x - o.x, dz = t.z - o.z, px = o.hw + R - Math.abs(dx), pz = o.hd + R - Math.abs(dz);
        if (px > 0 && pz > 0) { if (px < pz) t.x += px * Math.sign(dx || 1); else t.z += pz * Math.sign(dz || 1); }
      }
    }
    function los(ax, az, bx, bz) { var d = Math.hypot(bx - ax, bz - az), n = Math.ceil(d); for (var i = 1; i < n; i++) { var k = i / n; if (solid(ax + (bx - ax) * k, az + (bz - az) * k, 0.2)) return false; } return true; }

    // ---- tank modeli ----
    function tankMesh(color, name) {
      var g = new T.Group(), c = new T.MeshStandardMaterial({ color: color, roughness: 0.45, metalness: 0.3, emissive: color, emissiveIntensity: 0.12 }),
        dk = new T.MeshStandardMaterial({ color: 0x1a1d29, roughness: 0.8 });
      var body = new T.Mesh(new T.BoxGeometry(2.2, 0.8, 3), c); body.position.y = 0.7; g.add(body);
      [-1.25, 1.25].forEach(function (x) { var tr = new T.Mesh(new T.BoxGeometry(0.55, 0.7, 3.3), dk); tr.position.set(x, 0.4, 0); g.add(tr); });
      var tur = new T.Group(); tur.position.y = 1.15; g.add(tur);
      var head = new T.Mesh(new T.CylinderGeometry(0.75, 0.9, 0.55, 12), c); tur.add(head);
      var gun = new T.Mesh(new T.BoxGeometry(0.28, 0.28, 2), dk); gun.position.set(0, 0.05, -1.2); tur.add(gun);
      var sh = new T.Mesh(new T.SphereGeometry(2.1, 16, 10), new T.MeshBasicMaterial({ color: 0x3ea8ff, transparent: true, opacity: 0.22, depthWrite: false })); sh.position.y = 0.9; sh.visible = false; g.add(sh);
      var lb = K.label(name, '#' + color.toString(16).padStart(6, '0')); lb.position.y = 3.2; g.add(lb);
      sc.add(g);
      return { g: g, tur: tur, body: c, sh: sh };
    }
    function newTank(id, name, color, bot) {
      var t = { id: id, name: name, color: color, x: 0, z: 0, a: 0, t: 0, hp: 100, shield: 0, alive: true, resp: 0, cd: 0, kills: 0, deaths: 0,
        bot: bot, triT: 0, spT: 0, flash: 0, ai: { dir: 1, sw: 0 }, remote: false, tx: 0, tz: 0, ta: 0, tt: 0 };
      t.m = tankMesh(color, name); G.tanks[id] = t; return t;
    }
    function spawnAt(t, i) { var s = SPAWN[i % SPAWN.length]; t.x = s[0]; t.z = s[1]; t.a = Math.atan2(-s[0], -s[1]) + Math.PI; t.t = t.a; t.hp = 100; t.shield = 0; t.alive = true; t.m.g.visible = true; }
    function freeSpawn() { var best = 0, bd = -1; SPAWN.forEach(function (s, i) { var d = 1e9; for (var k in G.tanks) { var o = G.tanks[k]; if (o.alive) d = Math.min(d, Math.hypot(o.x - s[0], o.z - s[1])); } if (d > bd) { bd = d; best = i; } }); return best; }

    // ---- o'q ----
    var bulGeo = new T.SphereGeometry(0.28, 8, 6);
    function shoot(t, tri, net) {
      var angs = tri ? [-0.18, 0, 0.18] : [0];
      angs.forEach(function (da) {
        var a = t.t + da, m = new T.Mesh(bulGeo, new T.MeshBasicMaterial({ color: t.color }));
        var b = { x: t.x - Math.sin(a) * 2.2, z: t.z - Math.cos(a) * 2.2, vx: -Math.sin(a) * BUL_V, vz: -Math.cos(a) * BUL_V, life: BUL_LIFE, own: t.id, bn: 0, m: m };
        m.position.set(b.x, 1.2, b.z); sc.add(m); G.bul.push(b);
      });
      K.sfx('shot');
      if (net && sess) sess.emit({ k: 'f', x: +t.x.toFixed(2), z: +t.z.toFixed(2), a: +t.t.toFixed(3), tr: tri ? 1 : 0 });
    }
    function killBul(i, boom) { var b = G.bul[i]; if (boom) W.boom(b.x, 1.2, b.z, 0xffd080, 0.4); sc.remove(b.m); b.m.material.dispose(); G.bul.splice(i, 1); }

    // ---- zarar / o'lim ----
    function damage(t, by) {
      if (!t.alive) return;
      t.flash = 0.15;
      if (t.shield > 0) { t.shield = Math.max(0, t.shield - DMG); return; }
      t.hp -= DMG; if (t === G.me) { K.haptic('medium'); K.sfx('hit'); }
      if (t.hp <= 0) {
        if (G.mode === 'mp') { if (t === G.me) { t.alive = false; t.resp = 3; t.m.g.visible = false; sess.emit({ k: 'die', by: by }); } }
        else die(t, by);
      }
    }
    function die(t, by) {
      if (!t.alive && t.resp > 0) return;
      t.alive = false; t.resp = 3; t.deaths++; t.m.g.visible = false; W.boom(t.x, 1, t.z, 0xff6a30, 1.6); K.sfx('boom');
      var k = G.tanks[by]; if (k && k !== t) k.kills++;
      feed((k ? k.name : '?') + ' 💥 ' + t.name);
      if (t === G.me) K.haptic('heavy');
      checkWin();
    }
    function feed(txt) { G.feed.unshift([txt, 3]); G.feed.length = Math.min(G.feed.length, 4); }

    // ---- power-up ----
    function puSpawn(i, rnd) {
      for (var tries = 0; tries < 30; tries++) {
        var x = (rnd() * 2 - 1) * (A - 4), z = (rnd() * 2 - 1) * (A - 4);
        if (!solid(x, z, 1.5)) {
          var type = PUK[Math.floor(rnd() * 4)], m = new T.Mesh(new T.OctahedronGeometry(0.9), new T.MeshStandardMaterial({ color: PU[type][0], emissive: PU[type][0], emissiveIntensity: 0.6 }));
          m.position.set(x, 1.2, z); sc.add(m); G.pus.push({ i: i, x: x, z: z, type: type, m: m }); return;
        }
      }
    }
    function puTake(p, t) {
      if (p.type === 'hp') t.hp = Math.min(100, t.hp + 50); else if (p.type === 'sh') t.shield = 50; else if (p.type === 'tr') t.triT = 8; else t.spT = 6;
      if (t === G.me) { K.sfx('pick'); center(PU[p.type][1], 1); }
    }
    function puRemove(i) { for (var k = G.pus.length - 1; k >= 0; k--) if (G.pus[k].i === i) { sc.remove(G.pus[k].m); G.pus[k].m.geometry.dispose(); G.pus.splice(k, 1); } }

    // ---- HUD ----
    ui.hud.innerHTML = '<div class="ak-box" id="taHp"></div><div class="ak-box" id="taTime"></div><div class="ak-box ak-q" id="taQ">☰</div>';
    var board = K.el('<div class="ak-board"></div>'), cen = K.el('<div class="ak-center"></div>'); ui.el.appendChild(board); ui.el.appendChild(cen);
    var fireBtn = K.button(ui.ctl, '', '🔥');
    ui.hud.querySelector('#taQ').onclick = function () { pause(); };
    var cenT = 0; function center(t, s) { cen.innerHTML = t; cenT = s || 1.5; }
    function hud() {
      var me = G.me;
      ui.hud.querySelector('#taHp').innerHTML = '❤️ ' + Math.max(0, me.hp) + (me.shield ? ' 🛡' + me.shield : '') + (me.triT > 0 ? ' 🔱' : '') + (me.spT > 0 ? ' ⚡' : '');
      var left = Math.max(0, MATCH_T - G.t); ui.hud.querySelector('#taTime').textContent = '⏱ ' + Math.floor(left / 60) + ':' + ('0' + Math.floor(left % 60)).slice(-2) + ' · 🎯 ' + KILLS_WIN;
      var list = Object.keys(G.tanks).map(function (k) { return G.tanks[k]; }).sort(function (a, b) { return b.kills - a.kills; });
      board.innerHTML = list.map(function (t) { return '<div class="' + (t === me ? 'me' : '') + '"><span>' + K.esc(t.name) + '</span><b>' + t.kills + '</b></div>'; }).join('') +
        G.feed.map(function (f) { return '<div style="opacity:.7;font-size:11px">' + K.esc(f[0]) + '</div>'; }).join('');
    }

    // ---- boshqaruv ----
    function control(dt) {
      var me = G.me, mx = mvS.x, mz = mvS.y;
      if (keys.KeyW || keys.ArrowUp) mz = -1; if (keys.KeyS || keys.ArrowDown) mz = 1; if (keys.KeyA || keys.ArrowLeft) mx = -1; if (keys.KeyD || keys.ArrowRight) mx = 1;
      var mag = Math.min(1, Math.hypot(mx, mz)), sp = 9 * (me.spT > 0 ? 1.5 : 1);
      if (mag > 0.15) { var want = Math.atan2(-mx, -mz); me.a = K.lerpAng(me.a, want, Math.min(1, dt * 8)); me.x += -Math.sin(me.a) * sp * mag * dt; me.z += -Math.cos(me.a) * sp * mag * dt; }
      var firing = false;
      if (aimS.on && Math.hypot(aimS.x, aimS.y) > 0.3) { me.t = Math.atan2(-aimS.x, -aimS.y); firing = true; }
      else if (mouse.on) { me.t = Math.atan2(-(mouse.x - me.x), -(mouse.z - me.z)); firing = mouse.fire || keys.Space; }
      else if (mag > 0.15) me.t = K.lerpAng(me.t, me.a, Math.min(1, dt * 6));
      if (fireBtn.on) firing = true;
      if (firing && me.cd <= 0) { me.cd = 0.42; shoot(me, me.triT > 0, G.mode === 'mp'); }
    }
    function bot(t, dt) {
      var tgt = null, bd = 1e9, diff = G.diff;
      for (var k in G.tanks) { var o = G.tanks[k]; if (o === t || !o.alive) continue; var d = Math.hypot(o.x - t.x, o.z - t.z) * (los(t.x, t.z, o.x, o.z) ? 1 : 1.8); if (d < bd) { bd = d; tgt = o; } }
      if (!tgt) return;
      var dx = tgt.x - t.x, dz = tgt.z - t.z, dist = Math.hypot(dx, dz), want;
      t.ai.sw -= dt; if (t.ai.sw <= 0) { t.ai.sw = 1.5 + Math.random() * 2; t.ai.dir = Math.random() < 0.5 ? -1 : 1; }
      if (dist > 15) want = Math.atan2(-dx, -dz); else if (dist < 8) want = Math.atan2(dx, dz); else want = Math.atan2(-dx, -dz) + t.ai.dir * Math.PI / 2;
      var px = t.x - Math.sin(want) * 3, pz = t.z - Math.cos(want) * 3;
      if (solid(px, pz, 1)) want += t.ai.dir * Math.PI / 2;
      t.a = K.lerpAng(t.a, want, dt * 4); var sp = (5.5 + diff * 1.5) * (t.spT > 0 ? 1.5 : 1);
      t.x += -Math.sin(t.a) * sp * dt; t.z += -Math.cos(t.a) * sp * dt;
      var lead = dist / BUL_V * (0.3 + diff * 0.3), aimA = Math.atan2(-(tgt.x + (tgt._vx || 0) * lead - t.x), -(tgt.z + (tgt._vz || 0) * lead - t.z)) + (Math.random() - 0.5) * (0.25 - diff * 0.08);
      t.t = K.lerpAng(t.t, aimA, dt * (2.5 + diff * 1.5));
      var off = Math.abs(((aimA - t.t + Math.PI * 3) % (Math.PI * 2)) - Math.PI);
      if (off < 0.14 && dist < 30 && t.cd <= 0 && los(t.x, t.z, tgt.x, tgt.z)) { t.cd = 0.7 - diff * 0.12; shoot(t, t.triT > 0, false); }
    }

    // ---- o'yin sikli ----
    function step(dt) {
      if (!G || G.over) { W.render(dt); return; }
      G.t += dt;
      var me = G.me;
      if (me.alive) control(dt);
      for (var k in G.tanks) {
        var t = G.tanks[k];
        t.cd -= dt; t.triT -= dt; t.spT -= dt; t.flash -= dt;
        var ox = t.x, oz = t.z;
        if (t.remote) {
          var f = Math.min(1, dt * 12); t.x += (t.tx - t.x) * f; t.z += (t.tz - t.z) * f; t.a = K.lerpAng(t.a, t.ta, f); t.t = K.lerpAng(t.t, t.tt, f);
        } else if (!t.alive) {
          t.resp -= dt;
          if (t.resp <= 0 && (G.mode === 'solo' || t === me)) { spawnAt(t, freeSpawn()); if (t === me) center('▶ Qayta tug‘ildingiz', 1); }
        } else { if (t.bot) bot(t, dt); pushOut(t); t.x = Math.max(-A + R, Math.min(A - R, t.x)); t.z = Math.max(-A + R, Math.min(A - R, t.z)); }
        t._vx = (t.x - ox) / Math.max(dt, 1e-3); t._vz = (t.z - oz) / Math.max(dt, 1e-3);
        t.m.g.position.set(t.x, 0, t.z); t.m.g.rotation.y = t.a; t.m.tur.rotation.y = t.t - t.a;
        t.m.sh.visible = t.shield > 0; t.m.body.emissiveIntensity = t.flash > 0 ? 0.9 : 0.12; t.m.g.visible = t.alive;
      }
      for (var i = G.bul.length - 1; i >= 0; i--) {
        var b = G.bul[i]; b.life -= dt; if (b.life <= 0) { killBul(i, false); continue; }
        var nx = b.x + b.vx * dt, nz = b.z + b.vz * dt, o = solid(nx, nz, 0.25);
        if (o) { if (b.bn++ >= 1) { killBul(i, true); continue; } if (Math.abs(b.x - o.x) > o.hw) b.vx = -b.vx; else b.vz = -b.vz; nx = b.x; nz = b.z; }
        b.x = nx; b.z = nz; b.m.position.set(b.x, 1.2, b.z);
        for (var k2 in G.tanks) {
          var tk = G.tanks[k2]; if (!tk.alive || tk.id === b.own) continue;
          if (Math.hypot(tk.x - b.x, tk.z - b.z) < R + 0.2) {
            if (G.mode === 'solo' || tk === me) damage(tk, b.own);
            killBul(i, true); break;
          }
        }
      }
      // power-up'lar: har 10 s da (online'da seed bo'yicha bir xil joy)
      var slot = Math.floor(G.t / 10);
      if (slot > G.puSlot) { G.puSlot = slot; if (G.pus.length < 4) puSpawn(slot, K.rng((G.seed + slot * 7919) >>> 0)); }
      for (var p = G.pus.length - 1; p >= 0; p--) {
        var pu = G.pus[p]; pu.m.rotation.y += dt * 2; pu.m.position.y = 1.2 + Math.sin(G.t * 3 + p) * 0.2;
        for (var k3 in G.tanks) { var tt = G.tanks[k3]; if (!tt.alive || tt.remote || Math.hypot(tt.x - pu.x, tt.z - pu.z) > 2) continue;
          if (G.mode === 'mp') { if (tt !== me) continue; sess.emit({ k: 'pu', i: pu.i }); }
          puTake(pu, tt); puRemove(pu.i); break; }
      }
      if (G.mode === 'mp') sess.send({ x: +me.x.toFixed(2), z: +me.z.toFixed(2), a: +me.a.toFixed(2), t: +me.t.toFixed(2), h: me.hp, sh: me.shield, al: me.alive ? 1 : 0 });
      G.feed.forEach(function (f) { f[1] -= dt; }); G.feed = G.feed.filter(function (f) { return f[1] > 0; });
      cenT -= dt; if (cenT <= 0) cen.innerHTML = me.alive ? '' : '💀 ' + Math.ceil(Math.max(0, me.resp)) ;
      if (G.t >= MATCH_T) finish();
      W.cam.position.set(me.x, 30, me.z + 17); W.cam.lookAt(me.x, 0, me.z - 2);
      hud(); W.render(dt);
    }
    function checkWin() { for (var k in G.tanks) if (G.tanks[k].kills >= KILLS_WIN) return finish(); }
    function finish() {
      if (G.over) return; G.over = true;
      var list = Object.keys(G.tanks).map(function (k) { return G.tanks[k]; }).sort(function (a, b) { return b.kills - a.kills; }), win = list[0] === G.me;
      K.sfx(win ? 'win' : 'boom');
      var rows = list.map(function (t, i) { return (i + 1) + '. ' + K.esc(t.name) + ' — ' + t.kills + ' / ' + t.deaths; }).join('<br>');
      if (G.mode === 'solo' && opts.onResult) opts.onResult({ score: G.me.kills * 100 + (win ? 500 : 0), kills: G.me.kills, win: win ? 1 : 0, mode: 'solo' });
      var items = [];
      if (G.mode === 'solo') items.push(['🔁 Yana', function () { start('solo', G.diff); }, 'go']);
      else if (sess && sess.isHost()) items.push(['🔁 Qayta boshlash', function () { sess.start(); }, 'go']);
      else items.push(['⏳ Xona egasi qayta boshlashini kuting', function () {}]);
      items.push(['🏠 Menyu', function () { leaveMp(); mainMenu(); }]);
      K.menu(ui.menu, win ? '🏆 G‘ALABA!' : 'O‘YIN TUGADI', rows, items);
    }

    function reset(seed, mode) {
      if (G) { for (var k in G.tanks) sc.remove(G.tanks[k].m.g); G.bul.forEach(function (b) { sc.remove(b.m); }); G.pus.forEach(function (p) { sc.remove(p.m); }); }
      buildMap(seed);
      G = { mode: mode, seed: seed, t: 0, tanks: {}, bul: [], pus: [], feed: [], puSlot: 0, over: false, diff: 1 };
    }
    function start(mode, diff) {
      reset((Math.random() * 1e9) >>> 0, 'solo'); G.diff = diff;
      G.me = newTank('me', opts.playerName || 'Siz', K.COLORS[0], false); spawnAt(G.me, 0);
      for (var i = 0; i < 5; i++) { var b = newTank('b' + i, BOTN[i], K.COLORS[i + 1], true); spawnAt(b, i + 1); }
      K.hideMenu(ui.menu); center('🎯 ' + KILLS_WIN + ' frag — g‘alaba!', 2);
    }
    function mpBegin() {
      reset(sess.seed, 'mp');
      G.me = newTank(sess.me, opts.playerName || 'Siz', K.COLORS[0], false);
      spawnAt(G.me, freeSpawn() + (sess.me % 3));
      K.hideMenu(ui.menu); center('🌐 Online · ' + KILLS_WIN + ' frag', 2);
    }
    function startMp(s) {
      sess = s; mpBegin();
      s.on('sync', function (r) {
        if (!G || G.mode !== 'mp') return;
        var seen = {};
        r.players.forEach(function (p, i) {
          if (p.uid === s.me) return; seen[p.uid] = 1;
          var t = G.tanks[p.uid]; if (!t) { t = newTank(p.uid, p.name, K.COLORS[(i % 7) + 1], false); t.remote = true; if (p.state) { t.x = p.state.x; t.z = p.state.z; } }
          if (p.state) { t.tx = p.state.x; t.tz = p.state.z; t.ta = p.state.a; t.tt = p.state.t; t.hp = p.state.h; t.shield = p.state.sh; t.alive = !!p.state.al; }
        });
        for (var k in G.tanks) { var t2 = G.tanks[k]; if (t2.remote && !seen[k]) { sc.remove(t2.m.g); delete G.tanks[k]; } }
      });
      s.on('event', function (e) {
        if (!G || G.mode !== 'mp') return;
        var d = e.d, t = G.tanks[e.u];
        if (d.k === 'start') { sess.seed = d.seed; return mpBegin(); }
        if (d.k === 'f' && e.u !== s.me && t) { var save = { x: t.x, z: t.z, t: t.t }; t.x = d.x; t.z = d.z; t.t = d.a; shoot(t, d.tr, false); t.x = save.x; t.z = save.z; t.t = save.t; }
        else if (d.k === 'die') { var v = G.tanks[e.u]; if (v) { v.alive = true; v.resp = 0; die(v, d.by); } }
        else if (d.k === 'pu' && e.u !== s.me) puRemove(d.i);
        else if (d.k === 'kicked') { leaveMp(); mainMenu(); }
      });
    }
    function leaveMp() { if (sess) { sess.leave(); sess = null; } }
    function pause() {
      if (!G || G.over) return;
      var was = G.mode === 'solo'; if (was) G.over = true;
      K.menu(ui.menu, '⏸ PAUZA', G.mode === 'mp' ? 'Online o‘yin davom etmoqda' : '', [
        ['▶ Davom etish', function () { if (was) G.over = false; K.hideMenu(ui.menu); }, 'go'],
        ['🏠 Menyu', function () { leaveMp(); mainMenu(); }], ['✕ Chiqish', exit]]);
    }
    function mainMenu() {
      if (G) { G.over = true; }
      K.menu(ui.menu, '🛡 TANK ARENA', 'Chap tomon — yurish, o‘ng tomon — nishon va o‘q. Devordan o‘q bir marta qaytadi. Power-up: ❤️ 🛡 🔱 ⚡',
        [['🤖 Solo — Oson', function () { start('solo', 0); }], ['🤖 Solo — O‘rta', function () { start('solo', 1); }, 'go'], ['🤖 Solo — Qiyin', function () { start('solo', 2); }],
          ['🌐 Online (8 kishigacha)', function () { window.MPNET.lobby({ game: 'tank', title: 'TANK ARENA', icon: '🛡', min: 2, maxNote: 'Deathmatch: ' + KILLS_WIN + ' frag yoki 4 daqiqa. O‘yin ketayotgan xonaga ham kirish mumkin.', onStart: startMp, onClose: mainMenu }); }],
          ['✕ Chiqish', exit]]);
    }
    function exit() {
      leaveMp(); if (stop) stop(); keys.off(); removeEventListener('mousedown', md); removeEventListener('mouseup', mu);
      W.dispose(); ui.el.remove(); if (opts.onExit) opts.onExit();
    }
    reset(1, 'solo'); G.me = newTank('me', opts.playerName || 'Siz', K.COLORS[0], false); G.over = true;
    stop = K.loop(step); mainMenu();
  }
  window.TANKA = { launch: launch };
})();
