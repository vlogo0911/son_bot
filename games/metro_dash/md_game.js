/* METRO DASH — o'yin: Engine (renderer/kamera/sifat), Player (yo'lak, sakrash, sirpanish, power-up, uchar taxta), Input (swipe,
   ikki marta bosish, klaviatura), UI (menyu/personaj/do'kon/sozlamalar/HUD/pauza/natija), launch(). Tashqi API: MDASH.launch(opts). */
(function () {
  'use strict';
  const MD = window.MDASH, U = MD.U, A = MD.Audio, S = MD.Save, PU = MD.PU;
  const { LANES, ROOF } = MD.C;
  const G_ACC = -17, JUMP_V = 5.9, BOOT_V = 8.6, ROLL_T = 0.62, LANE_V = 11, BODY_H = 0.92, ROLL_H = 0.45, JET_Y = 4.2;
  const CHAR_SCALE = 1.4, CHASE_T = 8;

  // ── Engine ──
  function weakDevice() { return (navigator.deviceMemory && navigator.deviceMemory <= 3) || (navigator.hardwareConcurrency && navigator.hardwareConcurrency <= 4); }
  function Engine(canvas, quality) {
    this.q = quality === 'auto' ? (weakDevice() ? 'low' : 'medium') : quality;
    this.r = new THREE.WebGLRenderer({ canvas, antialias: this.q !== 'low', powerPreference: 'high-performance' });
    this.prBase = { low: 0.75, medium: 1.15, high: 1.7 }[this.q]; this.pr = Math.min(window.devicePixelRatio || 1, this.prBase);
    this.r.setPixelRatio(this.pr); this.scene = new THREE.Scene();
    this.cam = new THREE.PerspectiveCamera(62, 1, 0.1, 260); this.resize();
    this.fpsT = 0; this.fpsN = 0; this.fps = 60; this.slow = 0;
  }
  Engine.prototype.resize = function () {
    const c = this.r.domElement, w = c.clientWidth || window.innerWidth, h = c.clientHeight || window.innerHeight;
    this.r.setSize(w, h, false); this.cam.aspect = w / h; this.cam.fov = w / h < 0.8 ? 70 : 60; this.cam.updateProjectionMatrix();
  };
  Engine.prototype.tick = function (dt) {      // FPS o'lchash + avtomatik pasaytirish
    this.fpsT += dt; this.fpsN++;
    if (this.fpsT >= 1) {
      this.fps = this.fpsN / this.fpsT; this.fpsT = 0; this.fpsN = 0;
      this.slow = this.fps < 28 ? this.slow + 1 : 0;
      if (this.slow >= 3 && this.pr > 0.6) { this.pr = Math.max(0.6, this.pr - 0.2); this.r.setPixelRatio(this.pr); this.resize(); this.slow = 0; }
    }
  };

  // ── Patrul droni (quvlovchi) ──
  function makeDrone(own) {
    const g = new THREE.Group(), body = new THREE.Mesh(own(new THREE.SphereGeometry(0.28, 14, 10)), own(new THREE.MeshLambertMaterial({ color: 0x2b3442 })));
    body.scale.set(1.3, 0.7, 1.1); g.add(body);
    const eye = new THREE.Mesh(own(new THREE.SphereGeometry(0.09, 10, 8)), own(new THREE.MeshBasicMaterial({ color: 0xff2a2a }))); eye.position.set(0, 0, -0.28); g.add(eye);
    const armG = own(new THREE.BoxGeometry(0.9, 0.04, 0.06)), rotG = own(new THREE.CylinderGeometry(0.16, 0.16, 0.015, 14)), am = own(new THREE.MeshLambertMaterial({ color: 0x5b6676 })), rm = own(new THREE.MeshBasicMaterial({ color: 0xaad8ff, transparent: true, opacity: 0.45 }));
    const a1 = new THREE.Mesh(armG, am); a1.rotation.y = Math.PI / 4; const a2 = new THREE.Mesh(armG, am); a2.rotation.y = -Math.PI / 4; g.add(a1, a2);
    g.userData.rot = []; for (const [x, z] of [[0.32, 0.32], [-0.32, 0.32], [0.32, -0.32], [-0.32, -0.32]]) { const r = new THREE.Mesh(rotG, rm); r.position.set(x, 0.06, z); g.add(r); g.userData.rot.push(r); }
    const sm = own(new THREE.SpriteMaterial({ color: 0xff2020, transparent: true, blending: THREE.AdditiveBlending, depthWrite: false })), sb = own(new THREE.SpriteMaterial({ color: 0x2060ff, transparent: true, blending: THREE.AdditiveBlending, depthWrite: false }));
    const l1 = new THREE.Sprite(sm), l2 = new THREE.Sprite(sb); l1.position.set(0.18, 0.2, 0); l2.position.set(-0.18, 0.2, 0); l1.scale.setScalar(0.35); l2.scale.setScalar(0.35); g.add(l1, l2); g.userData.l = [l1, l2];
    return g;
  }

  // ── O'yin ──
  function Game(root, opts) {
    this.root = root; this.opts = opts; S.load(); const st = S.data.settings;
    this.disp = []; const own = (o) => { this.disp.push(o); return o; }; this.own = own;
    this.canvas = root.querySelector('canvas'); this.E = new Engine(this.canvas, st.quality);
    this.scene = this.E.scene; this.cam = this.E.cam;
    this.world = new MD.World(this.scene, this.E.q);
    // O'yinchi
    this.pl = new THREE.Group(); this.scene.add(this.pl); this.body = new THREE.Group(); this.pl.add(this.body);
    this.shadow = new THREE.Mesh(own(new THREE.CircleGeometry(0.32, 20)), own(new THREE.MeshBasicMaterial({ color: 0x000000, transparent: true, opacity: 0.35, depthWrite: false })));
    this.shadow.rotation.x = -Math.PI / 2; this.scene.add(this.shadow);
    const bm = own(new THREE.MeshLambertMaterial({ color: 0xff2fa0, emissive: 0x6a0040 }));
    this.board = new THREE.Mesh(own(new THREE.BoxGeometry(0.42, 0.05, 0.95)), bm); this.board.position.y = 0.06; this.board.visible = false; this.pl.add(this.board);
    const bg = new THREE.Sprite(own(new THREE.SpriteMaterial({ map: this.world.glow, color: 0xff3fd0, transparent: true, opacity: 0.7, blending: THREE.AdditiveBlending, depthWrite: false }))); bg.scale.set(1.2, 0.5, 1); bg.position.y = -0.02; this.board.add(bg);
    const jm = own(new THREE.MeshLambertMaterial({ color: 0xc0c6d0 })), jg = own(new THREE.CylinderGeometry(0.07, 0.07, 0.36, 10));
    this.jet = new THREE.Group(); for (const x of [-0.09, 0.09]) { const t = new THREE.Mesh(jg, jm); t.position.set(x, 0, 0); this.jet.add(t); }
    this.flame = new THREE.Sprite(own(new THREE.SpriteMaterial({ map: this.world.glow, color: 0xff8a1a, transparent: true, blending: THREE.AdditiveBlending, depthWrite: false }))); this.flame.position.y = -0.35; this.flame.scale.set(0.35, 0.7, 1); this.jet.add(this.flame);
    this.jet.position.set(0, 0.62, 0.15); this.jet.visible = false; this.pl.add(this.jet);
    this.drone = makeDrone(own); this.drone.visible = false; this.scene.add(this.drone);
    // Uchqunlar (tanga/qo'nish) — sprite pool
    this.fx = []; const fm = own(new THREE.SpriteMaterial({ map: this.world.glow, color: 0xffe066, transparent: true, blending: THREE.AdditiveBlending, depthWrite: false }));
    for (let i = 0; i < 24; i++) { const s = new THREE.Sprite(fm); s.visible = false; this.scene.add(s); this.fx.push({ s, t: 0, v: new THREE.Vector3() }); }
    this.mixer = null; this.acts = {}; this.cur = null; this.skin = null;
    this.state = 'menu'; this.time = 0; this.raf = 0; this.last = 0;
    this.input = new Input(this); this.ui = new UI(this);
    this.onResize = () => { this.E.resize(); this.menuOff = false; }; window.addEventListener('resize', this.onResize);
    this.onVis = () => { if (document.hidden && this.state === 'run') this.pause(); }; document.addEventListener('visibilitychange', this.onVis);
    this.resetRun(); this.setSkin(S.data.skin);
    this.loop = this.loop.bind(this); this.raf = requestAnimationFrame(this.loop);
  }
  const GP = Game.prototype;
  GP.setSkin = function (id) {
    this.skinId = id;
    return MD.Assets.char(id).then((g) => {
      if (this.dead || this.skinId !== id) return;
      if (this.skin) this.body.remove(this.skin);
      if (this.mixer) this.mixer.stopAllAction();
      this.skin = g.scene; this.skin.scale.setScalar(CHAR_SCALE); this.skin.position.set(0, 0, 0); this.skin.rotation.set(0, 0, 0); this.body.add(this.skin);
      this.mixer = new THREE.AnimationMixer(this.skin); this.acts = {}; this.cur = null;
      for (const c of g.animations) this.acts[c.name] = this.mixer.clipAction(c);
      for (const k of ['jump', 'die', 'crouch', 'fall', 'emote-yes']) if (this.acts[k]) { this.acts[k].setLoop(THREE.LoopOnce, 1); this.acts[k].clampWhenFinished = true; }
      this.mixer.addEventListener('finished', (e) => { if (e.action === this.acts['emote-yes'] && this.state === 'menu') this.anim('idle', 0.2, 1); });
      this.anim(this.state === 'run' ? 'sprint' : 'idle', 0);
    }).catch(() => {     // model yuklanmasa — oddiy kapsula
      if (this.skin || this.dead) return; const m = new THREE.Mesh(this.own(new THREE.CylinderGeometry(0.22, 0.22, BODY_H, 12)), this.own(new THREE.MeshLambertMaterial({ color: 0xff7a00 })));
      m.position.y = BODY_H / 2; this.skin = m; this.body.add(m);
    });
  };
  GP.anim = function (name, fade, speed) {
    const a = this.acts[name]; if (!a) return; if (speed) a.timeScale = speed;
    if (this.cur === a) return; a.reset(); a.play(); if (this.cur && fade !== 0) a.crossFadeFrom(this.cur, fade == null ? 0.12 : fade, false); else if (this.cur) this.cur.stop();
    this.cur = a;
  };
  GP.resetRun = function () {
    this.world.reset();
    this.p = { lane: 1, prevLane: 1, x: 0, y: 0, vy: 0, s: 0, prevS: 0, ground: true, roll: 0, speed: 0, inv: 0, stumbleT: 0 };
    this.r = { score: 0, coins: 0, time: 0, mult: 1, pu: {}, board: 0, chase: 0, dist: 0, over: false, deadT: 0, boards: 0, combo: 0 };
    this.shake = 0; this.camY = 0; this.turn = 0;
    this.world.generate(0, 0);
    this.pl.position.set(0, 0, 0); this.body.rotation.set(0, 0, 0); this.body.scale.set(1, 1, 1);
    this.board.visible = false; this.jet.visible = false; this.drone.visible = false; A.jetStop();
  };
  GP.start = function () {
    if (this.state === 'run') return;
    if (this.state !== 'menu') this.resetRun();
    this.state = 'run'; this.turn = 0.0001; A.init(); A.resume(); A.music(S.data.settings.music > 0);
    this.ui.screen(null); this.ui.hud(true); this.ui.toast('⬅ ➡ ⬆ ⬇  suring!');
    const tg = window.Telegram && window.Telegram.WebApp; if (tg && tg.disableVerticalSwipes) tg.disableVerticalSwipes();
    this.anim('sprint', 0.2, 1.3);
  };
  GP.pause = function () { if (this.state !== 'run') return; this.state = 'pause'; A.music(false); A.jetStop(); this.ui.screen('pause'); };
  GP.resume = function () { if (this.state !== 'pause') return; this.state = 'run'; A.resume(); A.music(S.data.settings.music > 0); if (this.r.pu.jet) A.jetStart(); this.ui.screen(null); this.last = performance.now(); };
  GP.toMenu = function () { A.music(false); A.jetStop(); this.state = 'menu'; this.resetRun(); this.anim('idle', 0.2, 1); this.ui.hud(false); this.ui.screen('menu'); };
  GP.speedAt = function (t) { return 7 + 9 * (1 - Math.exp(-t / 95)); };

  // ── Harakat buyruqlari ──
  GP.cmd = function (c) {
    if (this.state !== 'run' || this.r.over) return; const p = this.p;
    if (c === 'left' || c === 'right') {
      const nl = U.clamp(p.lane + (c === 'left' ? -1 : 1), 0, 2); if (nl === p.lane) { this.stumble(true); return; }
      p.prevLane = p.lane; p.lane = nl; A.swipe();
    } else if (c === 'up') {
      if (this.r.pu.jet) return;
      if (p.ground) { p.vy = this.r.pu.boots ? BOOT_V : JUMP_V; p.ground = false; p.roll = 0; A.jump(); this.anim('jump', 0.06, 1.1); }
    } else if (c === 'down') {
      if (this.r.pu.jet) return;
      if (!p.ground) p.vy = Math.min(p.vy, -13);
      p.roll = ROLL_T; A.roll(); this.anim('crouch', 0.06);
    } else if (c === 'board') this.useBoard();
  };
  GP.useBoard = function () {
    if (this.r.board > 0 || this.state !== 'run') return;
    if (S.data.stats.boards <= 0) { this.ui.toast('🛹 Taxta yo\'q — do\'kondan oling'); return; }
    S.data.stats.boards--; S.save(); this.r.board = 30; this.r.boards++; this.board.visible = true; A.board(); this.ui.toast('🛹 Uchar taxta — 30 s himoya');
  };
  GP.stumble = function (wall) {
    const r = this.r; if (this.p.inv > 0) return;
    A.stumble(); this.shake = 0.35; this.p.stumbleT = 0.4; this.haptic('medium');
    if (wall) return;
    if (r.chase > 0) { this.crash('caught'); return; }
    r.chase = CHASE_T; this.ui.toast('🚨 Dron quvlayapti!');
  };
  GP.crash = function (why, ob) {
    const r = this.r, p = this.p; if (r.over || p.inv > 0) return;
    if (r.board > 0) {          // taxta bir marta qutqaradi
      r.board = 0; this.board.visible = false; p.inv = 1.4; A.crash(); this.shake = 0.5; this.haptic('heavy'); this.ui.toast('🛹 Taxta sindi — davom!');
      if (ob) { ob.s0 = ob.s1 = -1e6; ob.mesh.visible = false; }
      r.chase = 0; return;
    }
    r.over = true; r.why = why; p.speed = 0; A.crash(); A.jetStop(); A.music(false); this.shake = 0.7; this.haptic('heavy');
    this.anim('die', 0.05); if (why === 'caught') this.r.chase = 2;
    r.deadT = 1.4;
  };
  GP.haptic = function (k) { try { const h = window.Telegram && window.Telegram.WebApp && window.Telegram.WebApp.HapticFeedback; if (h) h.impactOccurred(k); } catch (e) { /* */ } };
  GP.finish = function () {
    const r = this.r, res = { score: Math.floor(r.score), coins: r.coins, distance: Math.floor(this.p.s), time: Math.round(r.time * 10) / 10 };
    S.record(res); this.state = 'over'; A.over(); this.ui.hud(false); this.ui.screen('over', res);
    if (this.opts.onResult) { try { this.opts.onResult({ score: res.score, coins: res.coins, distance: res.distance, time: Math.round(r.time), skin: this.skinId }); } catch (e) { /* */ } }
  };
  GP.givePU = function (k) {
    const r = this.r, p = this.p; r.pu[k] = PU[k].dur; A.power(); this.ui.toast(PU[k].icon + ' ' + PU[k].name);
    if (k === 'x2') r.mult = 2;
    if (k === 'jet') {        // osmonda tangalar yo'li
      p.roll = 0; this.jet.visible = true; A.jetStart(); let lane = p.lane; const v = Math.max(p.speed, this.speedAt(r.time)), s0 = p.s + v * 0.7 + 3, n = Math.floor(v * PU.jet.dur / 1.4) + 2;
      for (let i = 0; i < n; i++) { if (i % 9 === 8) lane = U.clamp(lane + U.pick([-1, 1]), 0, 2); this.world.coins.push({ lane, s: s0 + i * 1.4, y: JET_Y + 0.4, got: false, x: LANES[lane] }); }
    }
  };
  GP.spark = function (x, y, z, col, n) {
    for (let i = 0, k = 0; i < this.fx.length && k < n; i++) { const f = this.fx[i]; if (f.t > 0) continue; f.t = 0.45; f.s.visible = true; f.s.position.set(x, y, z); f.v.set(U.rand(-1.5, 1.5), U.rand(1, 3), U.rand(-1, 1)); f.s.material.color.set(col); k++; }
  };

  // ── Fizika va to'qnashuvlar (kichik qadamlar) ──
  GP.step = function (dt) {
    const p = this.p, r = this.r, W = this.world;
    r.time += dt; if (p.inv > 0) p.inv -= dt; if (p.stumbleT > 0) p.stumbleT -= dt;
    const target = r.over ? 0 : this.speedAt(r.time) * Math.min(1, r.time / 0.7 + 0.15); p.speed = r.over ? Math.max(0, p.speed - 40 * dt) : target;
    p.prevS = p.s; const ds = p.speed * dt; p.s += ds; if (!r.over) r.score += ds * r.mult;
    // yo'lak
    const tx = LANES[p.lane], px0 = p.x; p.x += U.clamp(tx - p.x, -LANE_V * dt, LANE_V * dt);
    // vertikal
    const jetOn = !!r.pu.jet;
    if (jetOn) { p.y += (JET_Y - p.y) * Math.min(1, dt * 4.5); p.vy = 0; p.ground = false; }
    else {
      p.vy += G_ACC * dt; p.y += p.vy * dt;
      const gh = W.groundAt(p.x, p.s), floor = gh - p.y > 0.4 ? 0 : gh;     // juda baland bo'lsa — ichiga kirdi (pastda to'qnashuv)
      if (p.y <= floor + 0.001 && p.vy <= 0) {
        if (!p.ground && p.vy < -4) { A.land(); this.spark(p.x, floor, -p.s, '#d8c9b0', 3); }
        p.y = floor; p.vy = 0; if (!p.ground) { p.ground = true; if (!r.over && p.roll <= 0) this.anim('sprint', 0.1, 1.3); }
      } else if (p.ground && p.y > floor + 0.05) { p.ground = false; p.vy = Math.min(p.vy, 0); if (p.y - floor > 0.6 && !r.over) this.anim('fall', 0.15); }
    }
    if (p.roll > 0) { p.roll -= dt; if (p.roll <= 0 && !r.over) this.anim(p.ground ? 'sprint' : 'fall', 0.1, 1.3); }
    if (r.over) return;
    // to'qnashuvlar
    const h = p.roll > 0 ? ROLL_H : BODY_H;
    if (!jetOn && p.inv <= 0) {
      for (const o of W.obs) {
        const dx = Math.abs(LANES[o.lane] - p.x);
        if (o.type === 'train') {
          if (dx > 0.62 || p.s < o.s0 - 0.25 || p.s > o.s1 + 0.1) continue;
          if (p.y > ROOF - 0.38) continue;            // tomida yoki ustidan
          const wasFront = p.prevS < o.s0 + (o.speed ? o.speed * dt : 0) + 0.12 && Math.abs(LANES[o.lane] - px0) < 0.62;
          if (wasFront || Math.abs(LANES[o.lane] - px0) < 0.62) { this.crash('train', o); break; }
          // yon tomondan urildi — orqaga qaytish
          p.lane = p.prevLane; p.x = px0; this.stumble(false); break;
        } else if (o.type === 'low' || o.type === 'high') {
          if (dx > 0.6) continue; if (!(p.prevS < o.s1 + 0.05 && p.s > o.s0 - 0.05)) continue;
          if (o.type === 'low' && p.y < o.top - 0.04) { this.crash('barrier', o); break; }
          if (o.type === 'high' && p.y + h > o.bot && p.y < o.bot + 0.34) { this.crash('barrier', o); break; }
        }
      }
    }
    // tangalar va power-up'lar
    const mag = !!r.pu.magnet, cy = p.y + 0.45;
    for (const c of W.coins) {
      if (c.got) continue; const d = c.s - p.s; if (d > 12 || d < -2) continue;
      if (mag && d < 9 && d > -1) { c.x += (p.x - c.x) * Math.min(1, dt * 9); c.y += (cy - c.y) * Math.min(1, dt * 9); c.s += (p.s - c.s) * Math.min(1, dt * 7); }
      if (Math.abs(c.s - p.s) < 0.55 && Math.abs(c.x - p.x) < 0.6 && Math.abs(c.y - cy) < 0.75) { c.got = true; r.coins++; A.coin(); this.spark(c.x, c.y, -c.s, '#ffd84a', 2); }
    }
    for (const q of W.pows) { if (q.got) continue; if (Math.abs(q.s - p.s) < 0.7 && Math.abs(LANES[q.lane] - p.x) < 0.7 && Math.abs(0.6 - (p.y + 0.4)) < 0.9) { q.got = true; this.givePU(q.kind); } }
    // power-up taymerlari
    for (const k of Object.keys(r.pu)) { r.pu[k] -= dt; if (r.pu[k] <= 0) { delete r.pu[k]; if (k === 'x2') r.mult = 1; if (k === 'jet') { this.jet.visible = false; A.jetStop(); p.inv = Math.max(p.inv, 1.3); p.vy = 0; this.anim('fall', 0.15); } } }
    if (r.board > 0) { r.board -= dt; if (r.board <= 0) { r.board = 0; this.board.visible = false; } }
    if (r.chase > 0) r.chase -= dt;
  };

  GP.loop = function (now) {
    if (this.dead) return; this.raf = requestAnimationFrame(this.loop);
    const dt = Math.min(0.05, (now - (this.last || now)) / 1000); this.last = now; this.E.tick(dt);
    this.time += dt; const p = this.p, r = this.r;
    if (this.state === 'run') {
      const n = Math.ceil(dt / (1 / 120)); for (let i = 0; i < n; i++) this.step(dt / n);
      this.world.generate(p.s, (p.speed - 7) / 9);
      if (r.over) { r.deadT -= dt; if (r.deadT <= 0) this.finish(); }
      this.ui.tick();
    }
    this.world.update(this.state === 'run' ? dt : 0, p.s, this.time, this.cam);
    // o'yinchi ko'rinishi
    this.pl.position.set(p.x, p.y, -p.s);
    const running = this.state !== 'menu';
    if (running && this.turn < 1) this.turn = Math.min(1, this.turn + dt * 4);
    const lean = (LANES[p.lane] - p.x) * -0.25;
    this.body.rotation.set(0, (running ? this.turn : 0) * Math.PI, running ? lean : 0);
    const sq = p.roll > 0 ? 0.62 : 1; this.body.scale.y += (sq - this.body.scale.y) * Math.min(1, dt * 18);
    if (r.pu.jet) { this.jet.visible = true; this.flame.scale.set(0.3 + Math.random() * 0.1, 0.6 + Math.random() * 0.3, 1); }
    this.board.position.y = r.board > 0 ? 0.06 + Math.sin(this.time * 6) * 0.03 : 0.06;
    if (this.state === 'run' && !r.over && p.inv > 0) this.body.visible = Math.floor(this.time * 14) % 2 === 0; else this.body.visible = true;
    const gh = this.world.groundAt(p.x, p.s); this.shadow.position.set(p.x, gh + 0.02, -p.s); const sh = U.clamp(1 - (p.y - gh) / 4, 0.3, 1); this.shadow.scale.setScalar(sh);
    if (this.mixer) this.mixer.update(dt * (this.state === 'pause' ? 0 : 1));
    // dron
    if (r.chase > 0 && this.state !== 'menu') {
      this.drone.visible = true; const tz = -p.s + (r.over ? 1.2 : 2.1), tx = p.x * 0.9;
      this.drone.position.x += (tx - this.drone.position.x) * Math.min(1, dt * 5); this.drone.position.z = this.drone.position.z > -p.s + 6 || this.drone.position.z < -p.s ? -p.s + 6 : this.drone.position.z + (tz - this.drone.position.z) * Math.min(1, dt * 3);
      this.drone.position.y = p.y + 1.25 + Math.sin(this.time * 5) * 0.08;
      for (const rr of this.drone.userData.rot) rr.rotation.y += dt * 40; const bl = Math.floor(this.time * 6) % 2; this.drone.userData.l[0].visible = !!bl; this.drone.userData.l[1].visible = !bl;
    } else if (this.drone.visible) { this.drone.position.z += dt * 6; this.drone.position.y += dt * 2; if (this.drone.position.z > -p.s + 14) this.drone.visible = false; }
    // uchqunlar
    for (const f of this.fx) if (f.t > 0) { f.t -= dt; f.v.y -= 8 * dt; f.s.position.addScaledVector(f.v, dt); f.s.scale.setScalar(0.25 * Math.max(0, f.t / 0.45) + 0.05); if (f.t <= 0) f.s.visible = false; }
    // kamera
    const cam = this.cam;
    if (!running) {
      cam.position.set(0.55 + Math.sin(this.time * 0.4) * 0.15, 1.2, 3.0); cam.lookAt(0, 0.62, 0);
      if (!this.menuOff) { const v = this.E.r.getSize(new THREE.Vector2()); cam.setViewOffset(v.x, v.y, 0, v.y * 0.2, v.x, v.y); this.menuOff = true; }
    } else {
      if (this.menuOff) { cam.clearViewOffset(); this.menuOff = false; }
      this.camY += (Math.min(p.y, r.pu.jet ? JET_Y : 3) - this.camY) * Math.min(1, dt * 3.5);
      const k = this.turn < 1 ? this.turn : 1, tx = p.x * 0.55, ty = 2.75 + this.camY * 0.72, tz = -p.s + 4.9;
      cam.position.set(U.lerp(0.55, tx, k), U.lerp(1.2, ty, k), U.lerp(-p.s + 3.0, tz, k));
      if (this.shake > 0) { this.shake -= dt; cam.position.x += (Math.random() - 0.5) * this.shake * 0.4; cam.position.y += (Math.random() - 0.5) * this.shake * 0.4; }
      cam.lookAt(p.x * 0.7, 0.62 + this.camY * 0.8 + 0.2 * k, -p.s - 6 * k);
    }
    this.E.r.render(this.scene, cam);
  };

  // ── Input ──
  function Input(g) {
    this.g = g; const c = g.canvas; let sx = 0, sy = 0, st = 0, fired = false, lastTap = 0, id = null;
    this.down = (e) => { if (id !== null) return; id = e.pointerId; sx = e.clientX; sy = e.clientY; st = performance.now(); fired = false; A.resume(); };
    this.move = (e) => {
      if (e.pointerId !== id || fired) return; const dx = e.clientX - sx, dy = e.clientY - sy, d = Math.hypot(dx, dy);
      if (d > 28) { fired = true; g.cmd(Math.abs(dx) > Math.abs(dy) ? (dx > 0 ? 'right' : 'left') : (dy > 0 ? 'down' : 'up')); }
    };
    this.up = (e) => {
      if (e.pointerId !== id) return; id = null; if (fired) return; const now = performance.now();
      if (now - st < 250) { if (now - lastTap < 320) { g.cmd('board'); lastTap = 0; } else lastTap = now; }
    };
    this.key = (e) => {
      const k = e.key, map = { ArrowLeft: 'left', a: 'left', A: 'left', ArrowRight: 'right', d: 'right', D: 'right', ArrowUp: 'up', w: 'up', W: 'up', ' ': 'up', ArrowDown: 'down', s: 'down', S: 'down', b: 'board', B: 'board' };
      if (k === 'Escape' || k === 'p' || k === 'P') { if (g.state === 'run') g.pause(); else if (g.state === 'pause') g.resume(); e.preventDefault(); return; }
      if (map[k]) { if (g.state === 'menu' && k === ' ') return; g.cmd(map[k]); e.preventDefault(); }
    };
    c.addEventListener('pointerdown', this.down); window.addEventListener('pointermove', this.move); window.addEventListener('pointerup', this.up); window.addEventListener('pointercancel', this.up);
    window.addEventListener('keydown', this.key);
  }
  Input.prototype.dispose = function () {
    this.g.canvas.removeEventListener('pointerdown', this.down); window.removeEventListener('pointermove', this.move); window.removeEventListener('pointerup', this.up);
    window.removeEventListener('pointercancel', this.up); window.removeEventListener('keydown', this.key);
  };

  // ── UI ──
  const esc = (s) => String(s).replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
  function UI(g) {
    this.g = g; const R = g.root;
    this.hudEl = R.querySelector('.md-hud'); this.scr = R.querySelector('.md-scr'); this.toastEl = R.querySelector('.md-toast');
    this.hudEl.innerHTML = '<div class="md-top"><div class="md-score"><b data-k="score">0</b><span data-k="mult" class="md-mult">x1</span></div>' +
      '<div class="md-coins">🪙 <b data-k="coins">0</b></div><button class="md-pbtn" data-a="pause">❚❚</button></div>' +
      '<div class="md-pus" data-k="pus"></div><button class="md-bbtn" data-a="board">🛹 <b data-k="boards">0</b></button>' +
      '<div class="md-chase" data-k="chase">🚨</div><div class="md-fps" data-k="fps"></div>';
    this.k = {}; this.hudEl.querySelectorAll('[data-k]').forEach((e) => (this.k[e.dataset.k] = e));
    this.onClick = (e) => { const b = e.target.closest('[data-a]'); if (!b) return; A.init(); A.resume(); A.beep(); this.act(b.dataset.a, b.dataset.v); };
    R.addEventListener('click', this.onClick); this.screen('menu');
  }
  const UP = UI.prototype;
  UP.hud = function (on) { this.hudEl.style.display = on ? '' : 'none'; };
  UP.toast = function (t) { const e = this.toastEl; e.textContent = t; e.classList.remove('on'); void e.offsetWidth; e.classList.add('on'); clearTimeout(this.tt); this.tt = setTimeout(() => e.classList.remove('on'), 1600); };
  UP.tick = function () {
    const g = this.g, r = g.r, k = this.k;
    k.score.textContent = U.fmt(r.score); k.coins.textContent = r.coins; k.mult.textContent = 'x' + r.mult; k.mult.classList.toggle('hot', r.mult > 1);
    k.boards.textContent = S.data.stats.boards; k.chase.style.opacity = r.chase > 0 && !r.over ? 1 : 0;
    let h = ''; for (const key of Object.keys(r.pu)) h += '<div class="md-pu" style="--c:' + PU[key].col + '"><i>' + PU[key].icon + '</i><span><em style="width:' + Math.max(0, r.pu[key] / PU[key].dur * 100).toFixed(1) + '%"></em></span></div>';
    if (r.board > 0) h += '<div class="md-pu" style="--c:#ff3fd0"><i>🛹</i><span><em style="width:' + (r.board / 30 * 100).toFixed(1) + '%"></em></span></div>';
    if (h !== this.lastPu) { k.pus.innerHTML = h; this.lastPu = h; }
    k.fps.textContent = S.data.settings.fps ? Math.round(g.E.fps) + ' FPS' : '';
  };
  UP.screen = function (name, data) {
    const s = this.scr, st = S.data.stats; this.cur = name;
    if (!name) { s.innerHTML = ''; s.className = 'md-scr'; return; }
    s.className = 'md-scr on md-s-' + name; let h = '';
    if (name === 'menu') {
      h = '<div class="md-logo"><span>METRO</span><b>DASH</b></div><div class="md-stat"><span>🏆 ' + U.fmt(st.best) + '</span><span>🪙 ' + U.fmt(st.coins) + '</span><span>🛹 ' + st.boards + '</span></div>' +
        '<div class="md-menu"><button class="md-btn big" data-a="play">▶ O\'YNASH</button><button class="md-btn" data-a="chars">🧍 PERSONAJ</button><button class="md-btn" data-a="shop">🛹 DO\'KON</button>' +
        '<button class="md-btn" data-a="set">⚙ SOZLAMALAR</button><button class="md-btn" data-a="help">❓ QANDAY O\'YNALADI</button><button class="md-btn ghost" data-a="exit">✕ CHIQISH</button></div>';
    } else if (name === 'chars') {
      h = '<div class="md-h">🧍 PERSONAJLAR</div><div class="md-stat"><span>🪙 ' + U.fmt(st.coins) + '</span></div><div class="md-grid">' + MD.SKINS.map((k) => {
        const own = S.data.owned.includes(k.id), sel = S.data.skin === k.id;
        return '<button class="md-skin' + (sel ? ' sel' : '') + (own ? '' : ' lock') + '" data-a="skin" data-v="' + k.id + '"><b>' + esc(k.name) + '</b><span>' + (sel ? '✅ Tanlangan' : own ? 'Tanlash' : '🪙 ' + U.fmt(k.cost)) + '</span></button>';
      }).join('') + '</div><button class="md-btn" data-a="menu">‹ ORQAGA</button>';
    } else if (name === 'shop') {
      h = '<div class="md-h">🛹 DO\'KON</div><div class="md-stat"><span>🪙 ' + U.fmt(st.coins) + '</span><span>🛹 ' + st.boards + '</span></div>' +
        '<div class="md-card"><b>🛹 Uchar taxta</b><p>Ekranni 2 marta bosing (yoki B) — 30 soniya davomida bitta urilishdan qutqaradi.</p><button class="md-btn big" data-a="buyboard">🪙 ' + MD.BOARD_COST + ' — SOTIB OLISH</button></div>' +
        '<button class="md-btn" data-a="menu">‹ ORQAGA</button>';
    } else if (name === 'set') {
      const se = S.data.settings, q = (v, t) => '<option value="' + v + '"' + (se.quality === v ? ' selected' : '') + '>' + t + '</option>';
      h = '<div class="md-h">⚙ SOZLAMALAR</div><div class="md-card md-form">' +
        '<label>🎵 Musiqa <input type="range" min="0" max="1" step="0.05" value="' + se.music + '" data-s="music"></label>' +
        '<label>🔊 Effektlar <input type="range" min="0" max="1" step="0.05" value="' + se.sfx + '" data-s="sfx"></label>' +
        '<label>🖥 Grafika <select data-s="quality">' + q('auto', 'Avto') + q('low', 'Past') + q('medium', 'O\'rta') + q('high', 'Yuqori') + '</select></label>' +
        '<label>📊 FPS ko\'rsatish <input type="checkbox" data-s="fps"' + (se.fps ? ' checked' : '') + '></label><p class="md-note">Grafika o\'zgarishi keyingi ochilishda qo\'llanadi.</p></div>' +
        '<button class="md-btn" data-a="menu">‹ ORQAGA</button>';
    } else if (name === 'help') {
      h = '<div class="md-h">❓ QANDAY O\'YNALADI</div><div class="md-card md-help"><p>⬅ ➡ — yo\'lak almashtirish</p><p>⬆ — sakrash (past to\'siqlar ustidan)</p><p>⬇ — sirpanish (baland to\'siqlar ostidan)</p>' +
        '<p>👆👆 ikki marta bosish — 🛹 uchar taxta</p><p>Rampalardan poyezd tomiga chiqing. Yon tomondan urilsangiz dron quvlay boshlaydi — ikkinchi marta qoqilsangiz ushlanasiz!</p>' +
        '<p>🧲 Magnit · 🚀 Jetpak · 👟 Super sakrash · ✖2 Ochko</p><p>Klaviatura: ← → ↑ ↓ / WASD, Space, B, P</p><p class="md-cred">3D modellar: Kenney.nl (CC0). O\'yin original — METRO DASH.</p></div>' +
        '<button class="md-btn" data-a="menu">‹ ORQAGA</button>';
    } else if (name === 'pause') {
      h = '<div class="md-h">⏸ PAUZA</div><div class="md-menu"><button class="md-btn big" data-a="resume">▶ DAVOM</button><button class="md-btn" data-a="restart">↻ QAYTADAN</button><button class="md-btn ghost" data-a="menu">☰ MENYU</button></div>';
    } else if (name === 'over') {
      const why = { train: '🚆 Poyezdga urildingiz!', barrier: '🚧 To\'siqqa urildingiz!', caught: '🚨 Dron ushlab oldi!' }[this.g.r.why] || '';
      h = '<div class="md-h">' + why + '</div>' + (data.best ? '<div class="md-best">🏆 YANGI REKORD!</div>' : '') +
        '<div class="md-res"><div><span>OCHKO</span><b>' + U.fmt(data.score) + '</b></div><div><span>TANGA</span><b>🪙 ' + data.coins + '</b></div><div><span>MASOFA</span><b>' + U.fmt(data.distance) + ' m</b></div></div>' +
        '<div class="md-menu"><button class="md-btn big" data-a="restart">↻ YANA</button><button class="md-btn ghost" data-a="menu">☰ MENYU</button></div>';
    }
    s.innerHTML = h;
    s.querySelectorAll('[data-s]').forEach((el) => el.addEventListener('change', () => {
      const se = S.data.settings, k = el.dataset.s; se[k] = el.type === 'checkbox' ? el.checked : el.type === 'range' ? +el.value : el.value; S.save();
      A.setVol(se.music, se.sfx);
    }));
  };
  UP.act = function (a, v) {
    const g = this.g;
    if (a === 'play') g.start();
    else if (a === 'pause') g.pause();
    else if (a === 'resume') g.resume();
    else if (a === 'restart') { g.state = 'over'; g.start(); }
    else if (a === 'menu') g.toMenu();
    else if (a === 'board') g.cmd('board');
    else if (a === 'exit') g.opts._exit();
    else if (a === 'chars' || a === 'shop' || a === 'set' || a === 'help') this.screen(a);
    else if (a === 'buyboard') { const rr = S.buyBoard(); this.toast(rr === 'ok' ? '🛹 +1 taxta' : '🪙 Tanga yetmaydi'); this.screen('shop'); }
    else if (a === 'skin') {
      if (!S.data.owned.includes(v)) { const rr = S.buySkin(v); if (rr !== 'ok') { this.toast('🪙 Tanga yetmaydi'); return; } A.power(); }
      S.data.skin = v; S.save(); g.setSkin(v).then(() => g.anim('emote-yes', 0.1)); this.screen('chars');
    }
  };
  UP.dispose = function () { this.g.root.removeEventListener('click', this.onClick); clearTimeout(this.tt); };

  // ── launch ──
  MD.launch = function (opts) {
    opts = opts || {}; if (MD.game) MD.game.exit();
    const root = document.createElement('div'); root.className = 'mdash';
    root.innerHTML = '<canvas></canvas><div class="md-hud" style="display:none"></div><div class="md-scr"></div><div class="md-toast"></div><div class="md-load">⏳ 3D shahar yuklanmoqda…</div>';
    document.body.appendChild(root); const prevOverflow = document.body.style.overflow; document.body.style.overflow = 'hidden';
    let game = null, closed = false;
    const api = {
      exit() {
        if (closed) return; closed = true;
        if (game) { game.dead = true; cancelAnimationFrame(game.raf); game.input.dispose(); game.ui.dispose(); window.removeEventListener('resize', game.onResize); document.removeEventListener('visibilitychange', game.onVis);
          A.dispose(); game.world.dispose(); for (const d of game.disp) { try { d.dispose(); } catch (e) { /* */ } } if (game.mixer) game.mixer.stopAllAction(); game.E.r.dispose(); try { game.E.r.forceContextLoss(); } catch (e) { /* */ } }
        root.remove(); document.body.style.overflow = prevOverflow; MD.game = null;
        const tg = window.Telegram && window.Telegram.WebApp; if (tg && tg.enableVerticalSwipes) tg.enableVerticalSwipes();
        if (opts.onExit) try { opts.onExit(); } catch (e) { /* */ }
      },
    };
    opts._exit = api.exit; MD.game = api;
    const boot = () => { if (closed) return; root.querySelector('.md-load').remove(); game = new Game(root, opts); api.game = game; };
    MD.Assets.load(opts.assets || '', opts.ver || '', opts.lib).then(boot, () => { boot(); if (game) game.ui.toast('⚠️ 3D modellar yuklanmadi — oddiy rejim'); });
    return api;
  };
})();
