/* NEON RUSH — Race: mashinalar (protsedura 3D model, arkada fizika, drift), raqib AI, 8 ta power-up,
   effektlar (uchqunlar, portlashlar, yorug'lik izlari), poyga holati (aylanalar, o'rinlar, fanlar). */
(function () {
  'use strict';
  const NR = window.NR3D, U = NR.U, A = NR.Audio;

  const CARS = {
    viper: { name: 'Viper GT', color: 0xff2b6a, top: 62, acc: 23, grip: 1.0, hp: 100, mass: 1.0, d: 'Muvozanatli, tez sport-kupe' },
    hornet: { name: 'Hornet', color: 0xffd400, top: 58, acc: 27, grip: 1.14, hp: 90, mass: 0.9, d: 'Yengil, chaqqon, burilishlarda kuchli' },
    bulldog: { name: 'Bulldog', color: 0x2f9bff, top: 57, acc: 21, grip: 0.95, hp: 145, mass: 1.4, d: 'Og‘ir zirhli muscle-car, zarbaga chidamli' },
    phantom: { name: 'Phantom', color: 0xb04bff, top: 67, acc: 25, grip: 1.05, hp: 105, mass: 1.05, d: 'Eng tez giperkar' },
  };
  const BOT_NAMES = ['Nova', 'Blaze', 'Kairo', 'Vex', 'Rook', 'Zara', 'Echo', 'Jet', 'Lumen', 'Dash', 'Orbit', 'Raid', 'Sable', 'Torq'];
  const BOT_COLORS = [0x22e4ff, 0xff7a1a, 0x7aff5a, 0xff3b3b, 0xffffff, 0xff5ad8, 0x4a6bff, 0xffb000, 0x00ffa8, 0xc0c0c0];
  const PU = {
    seeker: { name: 'Seeker', icon: '🎯', col: '#ff3b5c', w: 16, d: 'Oldingi raqibni quvib boradigan raketa (orqaga — to‘g‘ri otiladi)' },
    volt: { name: 'Volt', icon: '⚡', col: '#3bb8ff', w: 16, d: '3 ta tezkor elektr o‘qi oldinga (yoki orqaga)' },
    blast: { name: 'Blast', icon: '💥', col: '#ff9a1a', w: 12, d: 'Atrofdagi mashinalarni uloqtiruvchi zarba to‘lqini' },
    mine: { name: 'Mine', icon: '💣', col: '#ff4040', w: 12, d: 'Orqaga mina tashlaydi (oldinga — uloqtiradi)' },
    shield: { name: 'Shield', icon: '🛡', col: '#7aff8a', w: 12, d: '8 soniya himoya: bitta zarbani to‘liq qaytaradi' },
    nitro: { name: 'Nitro', icon: '🔥', col: '#ffd400', w: 14, d: '2.5 soniya kuchli tezlanish' },
    repair: { name: 'Repair', icon: '🔧', col: '#ffffff', w: 10, d: '+55 HP tiklaydi' },
    storm: { name: 'Storm', icon: '🌩', col: '#b04bff', w: 5, d: 'Peshqadamlar oldiga elektr gumbazlar tushiradi' },
  };
  const PU_KEYS = Object.keys(PU);
  function rollPU(rank, n) {
    // orqadagilar hujumkor buyumlarni ko'proq oladi (oddiy rubber-band)
    const back = n > 1 ? (rank - 1) / (n - 1) : 0; let sum = 0; const w = {};
    for (const k of PU_KEYS) { let v = PU[k].w; if (k === 'storm') v *= 0.3 + back * 1.6; if (k === 'seeker') v *= 0.7 + back; if (k === 'repair' || k === 'shield') v *= 1.2 - back * 0.4; w[k] = v; sum += v; }
    let r = Math.random() * sum; for (const k of PU_KEYS) { r -= w[k]; if (r <= 0) return k; } return 'nitro';
  }
  NR.CARS = CARS; NR.PU = PU;

  // ── Model qurish: qutilarni bitta geometriyaga birlashtirish (har mashina ~3 draw call) ──
  function mergeBoxes(list) {
    const pos = [], nor = [], col = [], c = new THREE.Color(), m = new THREE.Matrix4(), e = new THREE.Euler();
    for (const b of list) {
      const g = new THREE.BoxGeometry(b[0], b[1], b[2]).toNonIndexed();
      e.set(b[7] || 0, 0, 0); m.makeRotationFromEuler(e); m.setPosition(b[3], b[4], b[5]); g.applyMatrix4(m);
      const p = g.attributes.position, n = g.attributes.normal; c.set(b[6]);
      for (let i = 0; i < p.count; i++) { pos.push(p.getX(i), p.getY(i), p.getZ(i)); nor.push(n.getX(i), n.getY(i), n.getZ(i)); col.push(c.r, c.g, c.b); }
      g.dispose();
    }
    const g = new THREE.BufferGeometry();
    g.setAttribute('position', new THREE.Float32BufferAttribute(pos, 3)); g.setAttribute('normal', new THREE.Float32BufferAttribute(nor, 3)); g.setAttribute('color', new THREE.Float32BufferAttribute(col, 3));
    return g;
  }
  const SH = {};   // umumiy resurslar (barcha mashinalar uchun)
  function shared() {
    if (SH.ok) return SH;
    SH.ok = true;
    SH.wheels = mergeBoxes([[0.32, 0.72, 0.72, -0.98, 0.36, 1.35, 0x111111], [0.32, 0.72, 0.72, 0.98, 0.36, 1.35, 0x111111], [0.36, 0.76, 0.76, -0.98, 0.38, -1.3, 0x111111], [0.36, 0.76, 0.76, 0.98, 0.38, -1.3, 0x111111],
      [0.34, 0.36, 0.36, -0.99, 0.36, 1.35, 0x9a9aa8], [0.34, 0.36, 0.36, 0.99, 0.36, 1.35, 0x9a9aa8], [0.38, 0.38, 0.38, -0.99, 0.38, -1.3, 0x9a9aa8], [0.38, 0.38, 0.38, 0.99, 0.38, -1.3, 0x9a9aa8]]);
    SH.wheelMat = new THREE.MeshLambertMaterial({ vertexColors: true });
    SH.lights = mergeBoxes([[0.5, 0.14, 0.06, -0.62, 0.72, 2.16, 0xffffff], [0.5, 0.14, 0.06, 0.62, 0.72, 2.16, 0xffffff],
      [1.7, 0.1, 0.06, 0, 0.78, -2.17, 0xff1030], [0.4, 0.16, 0.06, -0.7, 0.78, -2.17, 0xff2040], [0.4, 0.16, 0.06, 0.7, 0.78, -2.17, 0xff2040]]);
    SH.lightMat = new THREE.MeshBasicMaterial({ vertexColors: true });
    SH.glow = NR.Tex.glowTex();
    SH.under = new THREE.PlaneGeometry(3.4, 6); SH.under.rotateX(-Math.PI / 2);
    SH.shadow = new THREE.PlaneGeometry(2.6, 5.2); SH.shadow.rotateX(-Math.PI / 2);
    const [c2, g2] = (() => { const c = document.createElement('canvas'); c.width = c.height = 64; return [c, c.getContext('2d')]; })();
    const r = g2.createRadialGradient(32, 32, 4, 32, 32, 32); r.addColorStop(0, 'rgba(0,0,0,.75)'); r.addColorStop(1, 'rgba(0,0,0,0)'); g2.fillStyle = r; g2.fillRect(0, 0, 64, 64);
    SH.shadowMat = new THREE.MeshBasicMaterial({ map: new THREE.CanvasTexture(c2), transparent: true, depthWrite: false });
    SH.shieldGeo = new THREE.SphereGeometry(3.1, 16, 10);
    return SH;
  }
  function disposeShared() {
    if (!SH.ok) return;
    for (const k of Object.keys(SH)) { const v = SH[k]; if (v && v.dispose) { if (v.map) v.map.dispose(); v.dispose(); } }
    for (const k of Object.keys(SH)) delete SH[k];
  }
  function bodyGeo(kind, color) {
    const c = color, dk = new THREE.Color(color).multiplyScalar(0.45).getHex(), gl = 0x0d1220, tr = 0x18181c;
    const L = {
      viper: [[1.9, 0.42, 4.3, 0, 0.62, 0, c], [1.84, 0.2, 1.4, 0, 0.9, 1.35, c, -0.12], [1.45, 0.42, 1.8, 0, 1.03, -0.25, gl], [1.5, 0.06, 1.7, 0, 1.25, -0.3, c], [1.94, 0.12, 4.0, 0, 0.42, 0, dk], [1.9, 0.07, 0.42, 0, 1.18, -1.98, tr], [0.08, 0.3, 0.2, -0.6, 1.0, -1.98, tr], [0.08, 0.3, 0.2, 0.6, 1.0, -1.98, tr]],
      hornet: [[1.8, 0.4, 3.9, 0, 0.6, 0, c], [1.7, 0.24, 1.2, 0, 0.88, 1.2, c, -0.1], [1.4, 0.48, 1.9, 0, 1.05, -0.2, gl], [1.44, 0.06, 1.8, 0, 1.3, -0.25, c], [1.84, 0.12, 3.6, 0, 0.42, 0, dk], [1.4, 0.16, 0.5, 0, 1.2, -1.85, c]],
      bulldog: [[2.0, 0.55, 4.5, 0, 0.7, 0, c], [1.95, 0.18, 1.7, 0, 1.04, 1.3, c], [1.6, 0.48, 1.9, 0, 1.2, -0.45, gl], [1.66, 0.08, 1.8, 0, 1.46, -0.45, c], [2.06, 0.16, 4.3, 0, 0.45, 0, dk], [0.5, 0.18, 0.9, 0, 1.18, 1.2, tr], [2.02, 0.1, 0.25, 0, 0.62, 2.28, 0x777780]],
      phantom: [[1.98, 0.36, 4.5, 0, 0.56, 0, c], [1.9, 0.16, 1.7, 0, 0.8, 1.45, c, -0.16], [1.4, 0.36, 1.6, 0, 0.92, -0.35, gl], [1.44, 0.05, 1.5, 0, 1.11, -0.4, c], [2.02, 0.1, 4.3, 0, 0.38, 0, dk], [2.1, 0.07, 0.55, 0, 1.25, -2.05, tr], [0.08, 0.45, 0.25, -0.75, 1.0, -2.05, tr], [0.08, 0.45, 0.25, 0.75, 1.0, -2.05, tr]],
    };
    return mergeBoxes(L[kind] || L.viper);
  }

  // ── Effektlar ──
  function FX(scene, quality) {
    this.scene = scene; this.q = quality; const S = shared();
    const N = (this.N = quality === 'low' ? 160 : 360);
    this.pp = new Float32Array(N * 3); this.pc = new Float32Array(N * 3); this.pv = new Float32Array(N * 3); this.pl = new Float32Array(N); this.pm = new Float32Array(N); this.base = new Float32Array(N * 3); this.pi = 0;
    for (let i = 0; i < N; i++) this.pp[i * 3 + 1] = -999;
    const g = (this.pg = new THREE.BufferGeometry()); g.setAttribute('position', new THREE.BufferAttribute(this.pp, 3)); g.setAttribute('color', new THREE.BufferAttribute(this.pc, 3));
    this.pts = new THREE.Points(g, (this.pmat = new THREE.PointsMaterial({ size: 0.9, map: S.glow, vertexColors: true, transparent: true, depthWrite: false, blending: THREE.AdditiveBlending })));
    this.pts.frustumCulled = false; scene.add(this.pts);
    this.booms = []; this.rings = [];
    this.boomMat = new THREE.SpriteMaterial({ map: S.glow, color: 0xffa040, transparent: true, depthWrite: false, blending: THREE.AdditiveBlending });
    this.ringGeo = new THREE.RingGeometry(0.85, 1, 40); this.ringGeo.rotateX(-Math.PI / 2);
  }
  FX.prototype.spark = function (x, y, z, n, color, spd, life) {
    const c = new THREE.Color(color);
    for (let k = 0; k < n; k++) {
      const i = this.pi = (this.pi + 1) % this.N, o = i * 3;
      this.pp[o] = x; this.pp[o + 1] = y; this.pp[o + 2] = z;
      const a = Math.random() * Math.PI * 2, e = Math.random() * 1.2;
      this.pv[o] = Math.cos(a) * Math.cos(e) * spd; this.pv[o + 1] = Math.sin(e) * spd + 2; this.pv[o + 2] = Math.sin(a) * Math.cos(e) * spd;
      this.base[o] = c.r; this.base[o + 1] = c.g; this.base[o + 2] = c.b; this.pl[i] = this.pm[i] = life * (0.6 + Math.random() * 0.6);
    }
  };
  FX.prototype.boom = function (x, y, z, size, color) {
    const s = new THREE.Sprite(this.boomMat.clone()); s.material.color.set(color || 0xffa040); s.position.set(x, y + 1, z); s.scale.set(1, 1, 1); this.scene.add(s);
    this.booms.push({ s, t: 0, life: 0.55, size: size || 10 });
    this.spark(x, y + 0.8, z, 40, color || 0xffb050, 12, 0.8);
  };
  FX.prototype.ring = function (x, y, z, r, color) {
    const m = new THREE.Mesh(this.ringGeo, new THREE.MeshBasicMaterial({ color, transparent: true, side: THREE.DoubleSide, depthWrite: false, blending: THREE.AdditiveBlending }));
    m.position.set(x, y + 0.6, z); this.scene.add(m); this.rings.push({ m, t: 0, life: 0.45, r });
  };
  FX.prototype.update = function (dt) {
    const N = this.N;
    for (let i = 0; i < N; i++) {
      if (this.pl[i] <= 0) continue;
      const o = i * 3; this.pl[i] -= dt;
      if (this.pl[i] <= 0) { this.pp[o + 1] = -999; this.pc[o] = this.pc[o + 1] = this.pc[o + 2] = 0; continue; }
      this.pv[o + 1] -= 18 * dt; this.pp[o] += this.pv[o] * dt; this.pp[o + 1] += this.pv[o + 1] * dt; this.pp[o + 2] += this.pv[o + 2] * dt;
      const f = this.pl[i] / this.pm[i]; this.pc[o] = this.base[o] * f; this.pc[o + 1] = this.base[o + 1] * f; this.pc[o + 2] = this.base[o + 2] * f;
    }
    this.pg.attributes.position.needsUpdate = true; this.pg.attributes.color.needsUpdate = true;
    for (let i = this.booms.length - 1; i >= 0; i--) {
      const b = this.booms[i]; b.t += dt; const k = b.t / b.life;
      if (k >= 1) { this.scene.remove(b.s); b.s.material.dispose(); this.booms.splice(i, 1); continue; }
      const s = b.size * (0.4 + k * 0.9); b.s.scale.set(s, s, 1); b.s.material.opacity = 1 - k;
    }
    for (let i = this.rings.length - 1; i >= 0; i--) {
      const r = this.rings[i]; r.t += dt; const k = r.t / r.life;
      if (k >= 1) { this.scene.remove(r.m); r.m.material.dispose(); this.rings.splice(i, 1); continue; }
      const s = r.r * (0.2 + k); r.m.scale.set(s, 1, s); r.m.material.opacity = 1 - k;
    }
  };
  FX.prototype.dispose = function () {
    this.scene.remove(this.pts); this.pg.dispose(); this.pmat.dispose(); this.boomMat.dispose(); this.ringGeo.dispose();
    for (const b of this.booms) { this.scene.remove(b.s); b.s.material.dispose(); } for (const r of this.rings) { this.scene.remove(r.m); r.m.material.dispose(); }
  };

  // ── Mashina ──
  function Car(race, opt) {
    const S = shared(); this.race = race; this.id = opt.id; this.name = opt.name; this.bot = !!opt.bot; this.kind = opt.kind;
    this.def = CARS[opt.kind] || CARS.viper; this.color = opt.color != null ? opt.color : this.def.color;
    this.maxHp = this.def.hp; this.hp = this.maxHp; this.items = []; this.sel = 0;
    this.x = 0; this.y = 0; this.z = 0; this.h = 0; this.vx = 0; this.vz = 0; this.v = 0; this.steer = 0; this.roll = 0; this.pitch = 0;
    this.shield = 0; this.nitro = 0; this.stun = 0; this.spin = 0; this.slow = 0; this.wreck = 0; this.ghost = 0; this.air = 0; this.ay = 0;
    this.lap = -1; this.lapT = 0; this.bestLap = 0; this.lastD = 0; this.total = 0; this.finished = false; this.finishT = 0; this.place = 0;
    this.fans = 0; this.hits = 0; this.wrecks = 0; this.drift = 0; this.loc = {}; this.prevPlace = 0;
    const g = (this.g = new THREE.Group());
    this.bodyGeo = bodyGeo(this.kind, this.color); this.bodyMat = new THREE.MeshLambertMaterial({ vertexColors: true, emissive: 0x000000 });
    this.body = new THREE.Mesh(this.bodyGeo, this.bodyMat); g.add(this.body);
    this.body.add(new THREE.Mesh(S.wheels, S.wheelMat)); this.body.add(new THREE.Mesh(S.lights, S.lightMat));
    this.underMat = new THREE.MeshBasicMaterial({ map: S.glow, color: this.color, transparent: true, opacity: 0.85, depthWrite: false, blending: THREE.AdditiveBlending });
    const under = new THREE.Mesh(S.under, this.underMat); under.position.y = 0.06; g.add(under);
    const sh = new THREE.Mesh(S.shadow, S.shadowMat); sh.position.y = 0.04; g.add(sh);
    this.shieldMat = new THREE.MeshBasicMaterial({ color: 0x7aff8a, transparent: true, opacity: 0.25, depthWrite: false, blending: THREE.AdditiveBlending });
    this.shieldMesh = new THREE.Mesh(S.shieldGeo, this.shieldMat); this.shieldMesh.position.y = 0.8; this.shieldMesh.visible = false; g.add(this.shieldMesh);
    this.flameMat = new THREE.SpriteMaterial({ map: S.glow, color: 0x44aaff, transparent: true, depthWrite: false, blending: THREE.AdditiveBlending });
    this.flame = new THREE.Sprite(this.flameMat); this.flame.position.set(0, 0.7, -2.6); this.flame.visible = false; this.body.add(this.flame);
    race.scene.add(g);
    // Yorug'lik izi (orqa chiroqlar) — o'rta/yuqori sifatda
    if (race.quality !== 'low') {
      const n = (this.trN = 22); this.trP = new Float32Array(n * 2 * 3); this.trInit = false;
      const tg = (this.trG = new THREE.BufferGeometry()); tg.setAttribute('position', new THREE.BufferAttribute(this.trP, 3));
      const al = new Float32Array(n * 2 * 3), idx = [];
      for (let i = 0; i < n; i++) { const f = 1 - i / n; al.set([f, f * 0.1, f * 0.25, f, f * 0.1, f * 0.25], i * 6); if (i < n - 1) { const a = i * 2; idx.push(a, a + 1, a + 2, a + 1, a + 3, a + 2); } }
      tg.setAttribute('color', new THREE.BufferAttribute(al, 3)); tg.setIndex(idx);
      this.trM = new THREE.Mesh(tg, (this.trMat = new THREE.MeshBasicMaterial({ vertexColors: true, transparent: true, opacity: 0.8, depthWrite: false, blending: THREE.AdditiveBlending, side: THREE.DoubleSide })));
      this.trM.frustumCulled = false; race.scene.add(this.trM);
    }
  }
  const CP = Car.prototype;
  CP.place0 = function (d, lat) {
    const T = this.race.track, p = T.at(d, lat); this.x = p.x; this.z = p.z; this.y = p.y; this.h = p.head; this.vx = this.vz = 0; this.v = 0;
    T.locate(this.x, this.z, null, this.loc); this.lastD = this.loc.d; this.trInit = false;
  };
  CP.top = function () { const d = this.def; return d.top * (this.nitro > 0 ? 1.32 : 1) * (this.slow > 0 ? 0.55 : 1) * (this.hp < this.maxHp * 0.25 ? 0.93 : 1) * (this.topMul || 1); };
  CP.update = function (dt, inp) {
    const R = this.race, T = R.track, W = T.W, d = this.def;
    this.shield = Math.max(0, this.shield - dt); this.nitro = Math.max(0, this.nitro - dt); this.slow = Math.max(0, this.slow - dt); this.ghost = Math.max(0, this.ghost - dt);
    if (this.wreck > 0) {
      this.wreck -= dt; this.ay -= 20 * dt; this.air += this.ay * dt; this.spin += dt * 8;
      this.x += this.vx * dt; this.z += this.vz * dt; this.vx *= 0.97; this.vz *= 0.97;
      if (this.wreck <= 0) {   // trassaga qaytarish
        const oldD = this.loc.d; this.place0(oldD - 5, U.clamp(this.loc.lat, -W / 4, W / 4)); this.hp = this.maxHp; this.ghost = 2.2; this.air = 0; this.spin = 0; this.stun = 0;
        if (this.loc.d - oldD > T.length / 2) this.lap--;          // start chizig'idan orqaga qaytarildi
      }
      this.draw(dt); return;
    }
    const top = this.top(), fx = Math.sin(this.h), fz = Math.cos(this.h);
    let fv = this.vx * fx + this.vz * fz, lv = this.vx * fz - this.vz * fx;    // oldinga va yon tezlik
    let steer = inp.steer, thr = inp.throttle, brk = inp.brake;
    if (R.state === 'count') { thr = 0; steer = 0; brk = true; }
    if (this.stun > 0) { this.stun -= dt; this.h += this.spin * dt; this.spin *= Math.pow(0.15, dt); thr = 0; steer = 0; }
    this.steer = U.lerp(this.steer, steer, Math.min(1, dt * 10));
    const acc = d.acc * (this.nitro > 0 ? 1.7 : 1);
    if (thr > 0) fv += thr * acc * Math.max(0, 1 - fv / top) * dt * (fv < top ? 1 : 0);
    if (fv > top) fv = U.lerp(fv, top, Math.min(1, dt * 1.5));
    if (brk) fv -= 38 * dt;
    fv -= (fv * 0.012 + (thr > 0 ? 0 : 3)) * dt;
    if (fv < 0) fv = Math.max(fv, -6);
    const spd = Math.abs(fv), drifting = brk && Math.abs(this.steer) > 0.4 && spd > 22;
    const yaw = this.steer * (1.75 - 0.85 * Math.min(1, spd / 60)) * d.grip * (drifting ? 1.35 : 1) * Math.min(1, spd / 6) * (fv < 0 ? -1 : 1);
    if (this.stun <= 0) this.h += yaw * dt;
    if (drifting) { fv += 34 * dt * 0.9; this.drift += dt; } else if (this.drift > 0.6 && !this.bot) { const f = Math.round(this.drift * 25); this.fans += f; R.event('fans', this, '+' + f + ' drift'); this.drift = 0; } else this.drift = 0;
    lv *= Math.exp(-(drifting ? 2.2 : 9 * d.grip) * dt);
    const nfx = Math.sin(this.h), nfz = Math.cos(this.h);
    this.vx = nfx * fv + nfz * lv; this.vz = nfz * fv - nfx * lv;
    this.x += this.vx * dt; this.z += this.vz * dt;
    // Trassa chegarasi (to'siqlar)
    const L = T.locate(this.x, this.z, this.loc.i, this.loc), lim = W / 2 - 1.05;
    if (Math.abs(L.lat) > lim) {
      const sd = Math.sign(L.lat), ex = Math.abs(L.lat) - lim; this.x -= L.sx * sd * ex; this.z -= L.sz * sd * ex;
      const out = (this.vx * L.sx + this.vz * L.sz) * sd;
      if (out > 0) {
        this.vx -= L.sx * sd * out * 1.35; this.vz -= L.sz * sd * out * 1.35;
        const along = this.vx * L.tx + this.vz * L.tz, loss = U.clamp(out / 25, 0.02, 0.4);
        this.vx -= L.tx * along * loss; this.vz -= L.tz * along * loss;
        if (out > 6) { R.fx.spark(this.x + L.sx * sd, this.y + 0.6, this.z + L.sz * sd, 8, 0xffd080, 7, 0.4); if (!this.bot) { A.scrape(); R.shake(0.25); } }
        if (out > 16) this.damage(out * 0.6, null, 'wall');
      }
      const ad = U.angDiff(this.h, L.head); if (Math.abs(ad) < 1.4) this.h += ad * Math.min(1, dt * 3) * 0.6;   // faqat oldinga tekislanadi
    }
    this.v = this.vx * Math.sin(this.h) + this.vz * Math.cos(this.h);
    this.y = U.lerp(this.y, L.y, Math.min(1, dt * 12)); this.pitch = U.lerp(this.pitch, -Math.atan(L.slope || 0) + (brk ? 0.03 : thr > 0 ? -0.02 : 0), Math.min(1, dt * 6));
    this.roll = U.lerp(this.roll, -this.steer * Math.min(1, spd / 50) * 0.08 + (drifting ? -this.steer * 0.05 : 0), Math.min(1, dt * 6));
    // Aylana hisobi
    const Ln = T.length, dd = L.d - this.lastD;
    if (dd < -Ln / 2) this.crossLine(); else if (dd > Ln / 2) this.lap--;
    this.lastD = L.d; this.total = this.lap * Ln + L.d; if (R.state === 'race') this.lapT += dt;
    // Teskari yo'nalish / tiqilib qolish → avtomatik trassaga qaytarish
    if (R.state === 'race' && this.stun <= 0) {
      const wrong = Math.abs(U.angDiff(this.h, L.head)) > 1.95, slow = spd < 4;
      this.wrongT = wrong ? (this.wrongT || 0) + dt : 0; this.slowT = slow ? (this.slowT || 0) + dt : 0;
      if (this.wrongT > (this.bot ? 1.6 : 4.5) || this.slowT > (this.bot ? 2.5 : 5)) this.reset();
    }
    if (drifting && Math.random() < 0.6) R.fx.spark(this.x - nfx * 2 + nfz * 0.9, this.y + 0.15, this.z - nfz * 2 - nfx * 0.9, 1, 0xdddddd, 1.5, 0.5);
    this.draw(dt);
  };
  CP.reset = function () {
    const T = this.race.track, oldD = this.loc.d; this.place0(oldD - 3, U.clamp(this.loc.lat, -T.W / 4, T.W / 4));
    if (this.loc.d - oldD > T.length / 2) this.lap--; else if (oldD - this.loc.d > T.length / 2) this.lap++;
    this.v = 12; this.vx = Math.sin(this.h) * 12; this.vz = Math.cos(this.h) * 12; this.ghost = Math.max(this.ghost, 1.5); this.wrongT = this.slowT = 0; this.stun = 0;
    if (!this.bot) this.race.event('reset', this);
  };
  CP.crossLine = function () {
    const R = this.race; this.lap++;
    if (this.lap >= 1) {
      if (!this.bestLap || this.lapT < this.bestLap) this.bestLap = this.lapT;
      if (!this.bot) R.event('lap', this, this.lapT);
    }
    this.lapT = 0;
    if (this.lap >= R.laps && !this.finished) { this.finished = true; this.finishT = R.time; R.onFinish(this); }
  };
  CP.draw = function (dt) {
    const g = this.g; g.position.set(this.x, this.y + this.air, this.z); g.rotation.set(0, this.h, 0);
    this.body.rotation.set(this.pitch + (this.wreck > 0 ? this.spin * 0.6 : 0), 0, this.roll + (this.wreck > 0 ? this.spin : 0));
    this.shieldMesh.visible = this.shield > 0; if (this.shield > 0) this.shieldMesh.rotation.y += dt * 2;
    this.flame.visible = this.nitro > 0; if (this.nitro > 0) { const s = 1.6 + Math.random() * 0.8; this.flame.scale.set(s, s, 1); }
    this.bodyMat.emissive.setHex(this.ghost > 0 && Math.floor(this.ghost * 10) % 2 ? 0x333333 : this.stun > 0 ? 0x220000 : 0x000000);
    if (this.trM) {
      const n = this.trN, p = this.trP, bx = this.x - Math.sin(this.h) * 2.2, bz = this.z - Math.cos(this.h) * 2.2, rx = Math.cos(this.h) * 0.75, rz = -Math.sin(this.h) * 0.75, y = this.y + 0.75 + this.air;
      if (!this.trInit) { for (let i = 0; i < n; i++) p.set([bx - rx, y, bz - rz, bx + rx, y, bz + rz], i * 6); this.trInit = true; }
      p.copyWithin(6, 0, (n - 1) * 6); p.set([bx - rx, y, bz - rz, bx + rx, y, bz + rz], 0);
      this.trG.attributes.position.needsUpdate = true;
      this.trMat.opacity = U.clamp(Math.abs(this.v) / 50, 0, 0.85);
    }
  };
  CP.damage = function (dmg, by, kind) {
    const R = this.race;
    if (this.wreck > 0 || this.ghost > 0 || R.state !== 'race') return false;
    if (this.shield > 0 && kind !== 'wall') { this.shield = 0; R.fx.ring(this.x, this.y, this.z, 5, 0x7aff8a); R.event('blocked', this, by); return false; }
    this.hp -= dmg;
    if (kind !== 'wall') {
      this.stun = Math.max(this.stun, kind === 'volt' ? 0.25 : 0.9); this.spin = (Math.random() < 0.5 ? -1 : 1) * (kind === 'volt' ? 3 : 9);
      const k = kind === 'volt' ? 0.75 : 0.35; this.vx *= k; this.vz *= k;
      if (by && by !== this) { by.hits++; by.fans += { seeker: 60, volt: 20, blast: 30, mine: 40, storm: 25 }[kind] || 20; }
      R.event('hit', this, by, kind);
    }
    if (this.hp <= 0) {
      this.hp = 0; this.wreck = 1.8; this.wrecks++; this.ay = 9; this.air = 0;
      R.fx.boom(this.x, this.y, this.z, 16, 0xff8a30);
      if (by && by !== this) { by.fans += 150; R.event('wreck', this, by); } else R.event('wreck', this, null);
    }
    return true;
  };
  CP.give = function (k) { if (this.items.length >= 3) return false; this.items.push(k); if (this.items.length === 1) this.sel = 0; return true; };
  CP.dispose = function () {
    const sc = this.race.scene; sc.remove(this.g); this.bodyGeo.dispose(); this.bodyMat.dispose(); this.underMat.dispose(); this.shieldMat.dispose(); this.flameMat.dispose();
    if (this.trM) { sc.remove(this.trM); this.trG.dispose(); this.trMat.dispose(); }
  };

  // ── AI haydovchi ──
  const DIFF = { easy: { k: 0.86, lat: 17, use: 0.35, err: 0.18 }, normal: { k: 0.95, lat: 21, use: 0.7, err: 0.1 }, hard: { k: 1.01, lat: 24, use: 1.1, err: 0.05 } };
  function aiInput(c, R, dt) {
    const T = R.track, D = DIFF[R.diff] || DIFF.normal, L = c.loc, W = T.W;
    c.ai = c.ai || { line: U.rand(-0.25, 0.25), lt: 0, think: 0, target: 0, wob: Math.random() * 10 };
    const ai = c.ai; ai.think -= dt; ai.wob += dt;
    if (ai.think <= 0) {
      ai.think = 0.25 + Math.random() * 0.3;
      let lat = ai.line * W + Math.sin(ai.wob * 0.7) * W * 0.08;
      // power-up olish (bo'sh joy bo'lsa)
      if (c.items.length < 3 && R.mode !== 'clean') {
        let best = null, bd = 1e9;
        for (const p of T.pads) { if (!p.kind) continue; let ah = p.d - L.d; if (ah < 0) ah += T.length; if (ah > 8 && ah < 90 && ah < bd) { bd = ah; best = p; } }
        if (best) lat = best.lat;
      }
      // oldingi mashinani chetlab o'tish
      for (const o of R.cars) {
        if (o === c || o.wreck > 0) continue; let ah = o.loc.d - L.d; if (ah < -T.length / 2) ah += T.length; if (ah > T.length / 2) ah -= T.length;
        if (ah > 0 && ah < 14 && Math.abs(o.loc.lat - lat) < 2.6) lat = o.loc.lat + (o.loc.lat > 0 ? -3.2 : 3.2);
      }
      ai.target = U.clamp(lat, -W / 2 + 2, W / 2 - 2);
      // mashina rubber-band (o'yinchidan juda uzoqlashmasin)
      const pl = R.player, gap = c.total - pl.total;
      c.topMul = D.k * (gap > 140 ? 0.94 : gap < -160 ? 1.07 : 1) * (R.diff === 'hard' && gap < -60 ? 1.03 : 1);
      if (R.mode !== 'clean' && c.items.length) aiUse(c, R, D);
    }
    const spd = Math.max(8, Math.abs(c.v)), look = 9 + spd * 0.55;
    const tp = T.at(L.d + look, ai.target), want = Math.atan2(tp.x - c.x, tp.z - c.z);
    let steer = U.clamp(U.angDiff(c.h, want) * 2.4 + (Math.random() - 0.5) * D.err, -1, 1);
    const n = Math.max(6, Math.round((spd * 1.4) / T.step)), cv = T.curvAhead(L.i, n);
    const vmax = Math.sqrt(D.lat * c.def.grip / Math.max(cv, 0.0008));
    return { steer, throttle: spd < vmax ? 1 : 0, brake: spd > vmax * 1.12 };
  }
  function aiUse(c, R, D) {
    if (Math.random() > D.use * 0.5) return;
    const k = c.items[c.sel] || c.items[0], T = R.track; let use = false, back = false;
    const near = (pred) => R.cars.some((o) => o !== c && o.wreck <= 0 && pred(o));
    const ahead = (o, a, b) => { let d = o.total - c.total; return d > a && d < b; };
    if (k === 'seeker') use = near((o) => ahead(o, 5, 160)) || (back = near((o) => ahead(o, -40, -5)));
    else if (k === 'volt') use = near((o) => ahead(o, 4, 45) && Math.abs(o.loc.lat - c.loc.lat) < 3) || (back = near((o) => ahead(o, -30, -4) && Math.abs(o.loc.lat - c.loc.lat) < 3));
    else if (k === 'blast') use = near((o) => Math.hypot(o.x - c.x, o.z - c.z) < 11);
    else if (k === 'mine') { back = true; use = near((o) => ahead(o, -45, -6)); }
    else if (k === 'shield') use = c.hp < c.maxHp * 0.7 || R.projs.some((p) => p.target === c);
    else if (k === 'nitro') use = T.curvAhead(c.loc.i, 25) < 0.012;
    else if (k === 'repair') use = c.hp < c.maxHp * 0.55;
    else if (k === 'storm') use = c.place > 3;
    if (use) { c.sel = c.items.indexOf(k); R.use(c, back); }
  }

  // ── Poyga ──
  function Race(opt) {
    this.scene = opt.scene; this.quality = opt.quality; this.diff = opt.diff || 'normal'; this.mode = opt.mode || 'race';
    this.track = opt.track; this.laps = opt.laps || this.track.laps; this.onEvent = opt.onEvent || (() => {}); this.shake = opt.shake || (() => {});
    this.fx = new FX(this.scene, this.quality); this.cars = []; this.projs = []; this.mines = []; this.domes = []; this.time = 0; this.state = 'count'; this.count = 3.6; this.finishers = [];
    const S = shared(), n = opt.cars || 8;
    // Power-up belgilari
    this.icons = {};
    for (const k of PU_KEYS) {
      const c = document.createElement('canvas'); c.width = c.height = 64; const g = c.getContext('2d');
      g.fillStyle = PU[k].col; g.globalAlpha = 0.9; g.beginPath(); g.arc(32, 32, 28, 0, 7); g.fill(); g.globalAlpha = 1; g.font = '34px sans-serif'; g.textAlign = 'center'; g.textBaseline = 'middle'; g.fillText(PU[k].icon, 32, 35);
      this.icons[k] = new THREE.SpriteMaterial({ map: new THREE.CanvasTexture(c), depthWrite: false });
    }
    this.padGlow = new THREE.SpriteMaterial({ map: S.glow, color: 0xffffff, transparent: true, opacity: 0.6, depthWrite: false, blending: THREE.AdditiveBlending });
    for (const p of this.track.pads) {
      p.kind = this.mode === 'clean' ? null : rollPU(4, 8); p.t = 0;
      p.spr = new THREE.Sprite(this.icons[p.kind || 'nitro']); p.spr.scale.set(1.9, 1.9, 1); p.spr.position.set(p.x, p.y + 1.4, p.z); p.spr.visible = !!p.kind; this.scene.add(p.spr);
      p.glow = new THREE.Sprite(this.padGlow); p.glow.scale.set(4.5, 4.5, 1); p.glow.position.copy(p.spr.position); p.glow.visible = !!p.kind; this.scene.add(p.glow);
    }
    this.projMat = { seeker: new THREE.SpriteMaterial({ map: S.glow, color: 0xff3050, depthWrite: false, blending: THREE.AdditiveBlending }), volt: new THREE.SpriteMaterial({ map: S.glow, color: 0x40c0ff, depthWrite: false, blending: THREE.AdditiveBlending }) };
    this.mineGeo = new THREE.CylinderGeometry(0.55, 0.65, 0.3, 10); this.mineMat = new THREE.MeshLambertMaterial({ color: 0x222222, emissive: 0x550000 });
    this.mineGlow = new THREE.SpriteMaterial({ map: S.glow, color: 0xff2020, depthWrite: false, blending: THREE.AdditiveBlending });
    this.domeGeo = new THREE.SphereGeometry(4, 18, 10, 0, Math.PI * 2, 0, Math.PI / 2); this.domeMat = new THREE.MeshBasicMaterial({ color: 0xb04bff, transparent: true, opacity: 0.35, depthWrite: false, blending: THREE.AdditiveBlending, side: THREE.DoubleSide });
    // Mashinalar: o'yinchi oxirida (orqadan boshlaydi — quvib o'tish qiziqroq)
    const names = BOT_NAMES.slice().sort(() => Math.random() - 0.5), kinds = Object.keys(CARS);
    for (let i = 0; i < n; i++) {
      const me = i === n - 1;
      const c = new Car(this, { id: i, name: me ? (opt.playerName || 'Siz') : names[i % names.length], bot: !me, kind: me ? opt.car : kinds[(i + 1) % kinds.length], color: me ? null : BOT_COLORS[i % BOT_COLORS.length] });
      const row = Math.floor(i / 2), lat = (i % 2 ? 1 : -1) * this.track.W * 0.22;
      c.place0(this.track.length - 12 - row * 9, lat); c.lap = -1;
      this.cars.push(c);
    }
    this.player = this.cars[n - 1];
  }
  const RP = Race.prototype;
  RP.event = function (k, car, a, b) { this.onEvent(k, car, a, b); };
  RP.onFinish = function (c) { this.finishers.push(c); c.place = this.finishers.length; if (!c.bot) this.event('finish', c); };
  RP.use = function (c, back) {
    if (!c.items.length || this.state !== 'race' || c.wreck > 0) return;
    const k = c.items.splice(c.sel, 1)[0]; c.sel = Math.min(c.sel, Math.max(0, c.items.length - 1));
    const fx = Math.sin(c.h), fz = Math.cos(c.h), me = c === this.player, near = Math.hypot(c.x - this.player.x, c.z - this.player.z) < 120;
    const snd = (fn) => { if (me || near) fn(); };
    if (k === 'seeker') {
      let tgt = null;
      if (!back) { let bd = 1e9; for (const o of this.cars) { const d = o.total - c.total; if (o !== c && o.wreck <= 0 && d > 2 && d < 260 && d < bd) { bd = d; tgt = o; } } }
      this.proj(c, k, back ? -1 : 1, back ? 75 : 92, tgt, 40, 3.5); snd(() => A.seeker());
    } else if (k === 'volt') {
      for (let i = 0; i < 3; i++) setTimeout(() => { if (this.disposed || c.wreck > 0) return; this.proj(c, 'volt', back ? -1 : 1, 140, null, 13, 1.2); }, i * 120);
      snd(() => A.volt());
    } else if (k === 'blast') {
      this.fx.ring(c.x, c.y, c.z, 15, 0xff9a1a);
      for (const o of this.cars) {
        if (o === c) continue; const dx = o.x - c.x, dz = o.z - c.z, d = Math.hypot(dx, dz);
        if (d < 14) { if (o.damage(22, c, 'blast')) { o.vx += dx / (d || 1) * 22; o.vz += dz / (d || 1) * 22; } }
      }
      snd(() => A.blast()); if (near) this.shake(me ? 0.5 : 0.3);
    } else if (k === 'mine') {
      const dist = back ? -5 : 32; this.mines.push(this.mk('mine', c.x + fx * dist, c.y, c.z + fz * dist, c)); snd(() => A.mine());
    } else if (k === 'shield') { c.shield = 8; snd(() => A.shield()); }
    else if (k === 'nitro') { c.nitro = 2.5; snd(() => A.nitro()); if (me) this.shake(0.2); }
    else if (k === 'repair') { c.hp = Math.min(c.maxHp, c.hp + 55); this.fx.spark(c.x, c.y + 1, c.z, 20, 0x7aff8a, 4, 0.6); snd(() => A.repair()); }
    else if (k === 'storm') {
      const lead = this.cars.filter((o) => o !== c && o.wreck <= 0 && o.total > c.total).sort((a, b) => b.total - a.total).slice(0, 3);
      for (const o of lead) { const p = this.track.at(o.loc.d + 45 + o.v * 0.6, o.loc.lat); this.domes.push(this.mk('dome', p.x, p.y, p.z, c)); }
      snd(() => A.storm());
    }
    if (me) this.event('use', c, k);
  };
  RP.proj = function (c, kind, dir, speed, target, dmg, life) {
    const fx = Math.sin(c.h) * dir, fz = Math.cos(c.h) * dir, s = new THREE.Sprite(this.projMat[kind]);
    s.scale.set(kind === 'seeker' ? 2.6 : 1.8, kind === 'seeker' ? 2.6 : 1.8, 1);
    const p = { kind, owner: c, target, dmg, life, speed, x: c.x + fx * 3, y: c.y + 0.9, z: c.z + fz * 3, h: Math.atan2(fx, fz), s, loc: {} };
    s.position.set(p.x, p.y, p.z); this.scene.add(s); this.track.locate(p.x, p.z, c.loc.i, p.loc); this.projs.push(p);
  };
  RP.mk = function (kind, x, y, z, owner) {
    if (kind === 'mine') {
      const m = new THREE.Mesh(this.mineGeo, this.mineMat), gl = new THREE.Sprite(this.mineGlow); gl.scale.set(2.2, 2.2, 1); gl.position.y = 0.4; m.add(gl);
      m.position.set(x, y + 0.15, z); this.scene.add(m); return { kind, x, y, z, owner, m, gl, life: 40, arm: 0.5 };
    }
    const m = new THREE.Mesh(this.domeGeo, this.domeMat); m.position.set(x, y, z); this.scene.add(m); return { kind, x, y, z, owner, m, life: 6, arm: 0 };
  };
  RP.ranks = function () {
    const live = this.cars.filter((c) => !c.finished).sort((a, b) => b.total - a.total);
    const order = this.finishers.concat(live); order.forEach((c, i) => (c.place = i + 1)); return order;
  };
  RP.update = function (dt, pin) {
    this.time += dt;
    if (this.state === 'count') {
      const before = Math.ceil(this.count); this.count -= dt; const now = Math.ceil(this.count);
      if (now !== before && now > 0) this.event('count', null, now);
      if (this.count <= 0) { this.state = 'race'; this.time = 0; for (const c of this.cars) c.lapT = 0; this.event('go'); }
    }
    for (const c of this.cars) c.update(dt, this.state === 'count' ? { steer: 0, throttle: 0, brake: true } : (c.bot || c.finished) ? aiInput(c, this, dt) : pin);
    // Mashinalar to'qnashuvi (ikki doira — old/orqa)
    const cs = this.cars;
    for (let i = 0; i < cs.length; i++) for (let j = i + 1; j < cs.length; j++) {
      const a = cs[i], b = cs[j]; if (a.wreck > 0 || b.wreck > 0 || a.ghost > 0 || b.ghost > 0) continue;
      if (Math.abs(a.x - b.x) > 7 || Math.abs(a.z - b.z) > 7) continue;
      for (const sa of [1.15, -1.15]) for (const sb of [1.15, -1.15]) {
        const ax = a.x + Math.sin(a.h) * sa, az = a.z + Math.cos(a.h) * sa, bx = b.x + Math.sin(b.h) * sb, bz = b.z + Math.cos(b.h) * sb;
        const dx = bx - ax, dz = bz - az, d = Math.hypot(dx, dz);
        if (d < 2.1 && d > 1e-3) {
          const nx = dx / d, nz = dz / d, ov = (2.1 - d), ma = a.def.mass, mb = b.def.mass, ta = mb / (ma + mb), tb = ma / (ma + mb);
          a.x -= nx * ov * ta; a.z -= nz * ov * ta; b.x += nx * ov * tb; b.z += nz * ov * tb;
          const rv = (b.vx - a.vx) * nx + (b.vz - a.vz) * nz;
          if (rv < 0) { const imp = -rv * 0.9; a.vx -= nx * imp * ta; a.vz -= nz * imp * ta; b.vx += nx * imp * tb; b.vz += nz * imp * tb;
            if (-rv > 6 && (a === this.player || b === this.player)) { A.bump(); this.shake(Math.min(0.4, -rv / 40)); this.fx.spark((ax + bx) / 2, a.y + 0.7, (az + bz) / 2, 6, 0xffe0a0, 6, 0.35); } }
        }
      }
    }
    // Power-up joylari
    for (const p of this.track.pads) {
      if (!p.kind) { if (this.mode !== 'clean' && (p.t -= dt) <= 0) { p.kind = rollPU(4, 8); p.spr.material = this.icons[p.kind]; p.spr.visible = p.glow.visible = true; } continue; }
      p.spr.position.y = p.y + 1.4 + Math.sin(this.time * 3 + p.d) * 0.25;
      for (const c of cs) {
        if (c.wreck > 0) continue; const dx = c.x - p.x, dz = c.z - p.z;
        if (dx * dx + dz * dz < 2.6 * 2.6 && c.items.length < 3) {
          const k = c === this.player ? p.kind : rollPU(c.place || 4, cs.length); c.give(k);
          if (c === this.player) { A.pickup(); this.event('pickup', c, k); }
          p.kind = null; p.t = 5.5; p.spr.visible = p.glow.visible = false; break;
        }
      }
    }
    // Snaryadlar
    const T = this.track;
    for (let i = this.projs.length - 1; i >= 0; i--) {
      const p = this.projs[i]; p.life -= dt; let done = p.life <= 0;
      if (p.target && p.target.wreck <= 0) { const want = Math.atan2(p.target.x - p.x, p.target.z - p.z); p.h += U.clamp(U.angDiff(p.h, want), -3.2 * dt, 3.2 * dt); }
      else if (p.kind === 'seeker' && !p.target) {   // trassa bo'ylab
        const ahead = T.at(p.loc.d + 20 * (Math.cos(U.angDiff(p.h, p.loc.head || 0)) < 0 ? -1 : 1), p.loc.lat * 0.9); const want = Math.atan2(ahead.x - p.x, ahead.z - p.z); p.h += U.clamp(U.angDiff(p.h, want), -2 * dt, 2 * dt);
      }
      p.x += Math.sin(p.h) * p.speed * dt; p.z += Math.cos(p.h) * p.speed * dt;
      const L = T.locate(p.x, p.z, p.loc.i, p.loc); p.y = L.y + 0.9;
      if (Math.abs(L.lat) > T.W / 2 + 0.5) done = true;
      p.s.position.set(p.x, p.y, p.z);
      if (Math.random() < 0.8) this.fx.spark(p.x, p.y, p.z, 1, p.kind === 'seeker' ? 0xff5060 : 0x60d0ff, 1, 0.3);
      for (const c of cs) {
        if (c === p.owner && p.life > (p.kind === 'seeker' ? 3.2 : 1.0)) continue;
        if (c.wreck > 0) continue; const dx = c.x - p.x, dz = c.z - p.z;
        if (dx * dx + dz * dz < (p.kind === 'seeker' ? 2.4 : 1.8) ** 2) {
          c.damage(p.dmg, p.owner, p.kind); this.fx.boom(p.x, p.y - 0.9, p.z, p.kind === 'seeker' ? 9 : 4, p.kind === 'seeker' ? 0xff5040 : 0x50c8ff);
          if (c === this.player || p.owner === this.player) A.hit(p.kind === 'seeker'); if (c === this.player) this.shake(0.6);
          done = true; break;
        }
      }
      if (done) { if (p.life > 0 && !p.hitFx) this.fx.spark(p.x, p.y, p.z, 10, 0xffffff, 5, 0.3); this.scene.remove(p.s); this.projs.splice(i, 1); }
    }
    // Minalar va gumbazlar
    const traps = this.mines.concat(this.domes);
    for (const m of traps) {
      m.life -= dt; m.arm -= dt; if (m.gl) m.gl.material.opacity = 0.5 + Math.sin(this.time * 10) * 0.5;
      if (m.kind === 'dome') m.m.scale.setScalar(Math.min(1, (6 - m.life) * 3));
      if (m.arm > 0 || m.life <= 0) continue;
      for (const c of cs) {
        if (c.wreck > 0 || c === m.owner && m.kind === 'dome') continue; const dx = c.x - m.x, dz = c.z - m.z, r = m.kind === 'mine' ? 2.2 : 4.2;
        if (dx * dx + dz * dz < r * r) {
          if (m.kind === 'mine') { if (c.damage(32, m.owner, 'mine')) { c.ay = 7; c.air = 0.01; } this.fx.boom(m.x, m.y, m.z, 11, 0xff4030); if (c === this.player || m.owner === this.player) A.hit(true); if (c === this.player) this.shake(0.6); m.life = 0; }
          else if (!m.hit || !m.hit.includes(c)) { (m.hit = m.hit || []).push(c); c.damage(16, m.owner, 'storm'); c.slow = 1.6; this.fx.spark(c.x, c.y + 1, c.z, 18, 0xc070ff, 6, 0.5); if (c === this.player) { A.storm(); this.shake(0.4); } }
          break;
        }
      }
    }
    for (const arr of [this.mines, this.domes]) for (let i = arr.length - 1; i >= 0; i--) if (arr[i].life <= 0) { this.scene.remove(arr[i].m); arr.splice(i, 1); }
    // Havodagi mashinalar (mina) qo'nishi
    for (const c of cs) if (c.air > 0 && c.wreck <= 0) { c.ay -= 22 * dt; c.air += c.ay * dt; if (c.air <= 0) { c.air = 0; c.ay = 0; } }
    this.fx.update(dt);
    const order = this.ranks();
    if (this.state === 'race') {
      const pl = this.player;
      if (pl.prevPlace && pl.place < pl.prevPlace && !pl.finished) { pl.fans += 10; this.event('fans', pl, '+10 quvib o‘tish'); }
      pl.prevPlace = pl.place;
      if (pl.finished && !this.doneT) this.doneT = this.time;
      if (this.doneT && (this.time - this.doneT > 4 || this.finishers.length === cs.length)) { this.state = 'done'; this.event('done', pl, order); }
      // xavfsizlik: o'yinchi tugatmasa ham juda uzoq poyga to'xtaydi
      if (this.time > 60 * 8) { this.state = 'done'; this.event('done', pl, order); }
    }
  };
  RP.dispose = function () {
    this.disposed = true;
    for (const c of this.cars) c.dispose();
    for (const p of this.projs) this.scene.remove(p.s); for (const m of this.mines.concat(this.domes)) this.scene.remove(m.m);
    for (const p of this.track.pads) { this.scene.remove(p.spr); this.scene.remove(p.glow); }
    for (const k of PU_KEYS) { this.icons[k].map.dispose(); this.icons[k].dispose(); }
    this.padGlow.dispose(); this.projMat.seeker.dispose(); this.projMat.volt.dispose(); this.mineGeo.dispose(); this.mineMat.dispose(); this.mineGlow.dispose(); this.domeGeo.dispose(); this.domeMat.dispose();
    this.fx.dispose();
  };

  NR.Race = { CARS, PU, PU_KEYS, DIFF, Race, Car, disposeShared, aiInput };
})();
