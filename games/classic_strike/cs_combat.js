/* CLASSIC STRIKE — WeaponSystem (qurollar, otish, effektlar, viewmodel) va EnemyAI (bot holatlari, ko'rish/eshitish, A*). */
(function () {
  'use strict';
  const CS3D = window.CS3D, U = CS3D.U;

  // ── Qurollar (original nomlar) ──
  const WEAPONS = {
    knife:   { name: 'Knife',       slot: 3, melee: true, dmg: 55, rate: 0.5, range: 1.9, move: 1.08, mag: 0, res: 0 },
    pistol:  { name: 'P-9 Pistol',  slot: 2, dmg: 27, rate: 0.16, auto: false, mag: 12, res: 60, reload: 1.6, spread: 0.010, moveSpread: 0.035, recoil: 0.022, range: 45, falloff: 0.55, move: 1.0, snd: 'pistol' },
    deagle:  { name: 'Hawk .50',    slot: 2, dmg: 60, rate: 0.38, auto: false, mag: 7, res: 35, reload: 2.1, spread: 0.014, moveSpread: 0.07, recoil: 0.08, range: 70, falloff: 0.75, move: 0.97, snd: 'deagle' },
    smg:     { name: 'Viper SMG',   slot: 1, dmg: 19, rate: 0.072, auto: true, mag: 30, res: 120, reload: 2.2, spread: 0.026, moveSpread: 0.028, recoil: 0.013, range: 32, falloff: 0.45, move: 0.98, snd: 'smg' },
    rifle:   { name: 'AR-7 Rifle',  slot: 1, dmg: 31, rate: 0.1, auto: true, mag: 30, res: 90, reload: 2.5, spread: 0.012, moveSpread: 0.06, recoil: 0.02, range: 75, falloff: 0.8, move: 0.9, zoom: 1.35, snd: 'rifle' },
    sniper:  { name: 'Longshot',    slot: 1, dmg: 118, rate: 1.35, auto: false, mag: 5, res: 20, reload: 3.2, spread: 0.07, adsSpread: 0.0012, moveSpread: 0.12, recoil: 0.11, range: 160, falloff: 1, move: 0.8, zoom: 3.4, scope: true, snd: 'sniper' },
    shotgun: { name: 'Breacher 12', slot: 1, dmg: 16, pellets: 8, rate: 0.85, auto: false, mag: 7, res: 28, reload: 2.8, spread: 0.07, moveSpread: 0.03, recoil: 0.08, range: 20, falloff: 0.2, move: 0.92, snd: 'shotgun' },
  };
  const HEAD = 2.4;

  // Ray ↔ tik silindr (entity: x,z, feet y, r, h). Natija: {t, head}
  function rayEntity(ox, oy, oz, dx, dy, dz, e, max) {
    const r = e.r || 0.34, h = e.h || 1.8, fx = ox - e.x, fz = oz - e.z;
    const a = dx * dx + dz * dz; if (a < 1e-9) return null;
    const b = 2 * (fx * dx + fz * dz), c = fx * fx + fz * fz - r * r, disc = b * b - 4 * a * c;
    if (disc < 0) return null;
    const sq = Math.sqrt(disc);
    for (const t of [(-b - sq) / (2 * a), (-b + sq) / (2 * a)]) {
      if (t <= 0 || t > max) continue;
      const y = oy + dy * t;
      if (y >= e.y && y <= e.y + h) return { t, head: y > e.y + h - 0.32 };
    }
    return null;
  }

  // ── Effektlar (object pooling) ──
  function Effects(scene, quality) {
    this.scene = scene;
    const geo = new THREE.BufferGeometry(); this.trN = 28;
    this.trPos = new Float32Array(this.trN * 6); geo.setAttribute('position', new THREE.BufferAttribute(this.trPos, 3));
    this.trMat = new THREE.LineBasicMaterial({ color: 0xfff2b0, transparent: true, opacity: 0.85 });
    this.tracers = new THREE.LineSegments(geo, this.trMat); this.tracers.frustumCulled = false; scene.add(this.tracers);
    this.trLife = new Float32Array(this.trN); this.trI = 0; this.trGeo = geo;
    // Uchqun/qon zarralari
    this.pN = quality === 'low' ? 120 : 260;
    const pg = new THREE.BufferGeometry(); this.pPos = new Float32Array(this.pN * 3); this.pCol = new Float32Array(this.pN * 3);
    pg.setAttribute('position', new THREE.BufferAttribute(this.pPos, 3)); pg.setAttribute('color', new THREE.BufferAttribute(this.pCol, 3));
    this.pMat = new THREE.PointsMaterial({ size: 0.09, vertexColors: true, transparent: true, opacity: 0.95 });
    this.points = new THREE.Points(pg, this.pMat); this.points.frustumCulled = false; scene.add(this.points);
    this.pVel = new Float32Array(this.pN * 3); this.pLife = new Float32Array(this.pN); this.pI = 0; this.pGeo = pg;
    for (let i = 0; i < this.pN; i++) this.pPos[i * 3 + 1] = -99;
    // O'q izlari (decal)
    this.dN = quality === 'low' ? 24 : 48; this.dI = 0; this.decals = [];
    this.dGeo = new THREE.PlaneGeometry(0.14, 0.14); this.dMat = new THREE.MeshBasicMaterial({ color: 0x1a1a1a, transparent: true, opacity: 0.8, depthWrite: false, polygonOffset: true, polygonOffsetFactor: -2 });
    for (let i = 0; i < this.dN; i++) { const m = new THREE.Mesh(this.dGeo, this.dMat); m.visible = false; scene.add(m); this.decals.push(m); }
    // Dushman o'q chaqnashi
    this.flashGeo = new THREE.PlaneGeometry(0.35, 0.35); this.flashMat = new THREE.MeshBasicMaterial({ color: 0xffd27a, transparent: true, opacity: 0.95, blending: THREE.AdditiveBlending, depthWrite: false, side: THREE.DoubleSide });
    this.flashes = []; for (let i = 0; i < 10; i++) { const m = new THREE.Mesh(this.flashGeo, this.flashMat); m.visible = false; m.userData.t = 0; scene.add(m); this.flashes.push(m); }
    this.fI = 0;
  }
  const EP = Effects.prototype;
  EP.tracer = function (a, b) {
    const i = this.trI = (this.trI + 1) % this.trN, o = i * 6;
    this.trPos.set([a[0], a[1], a[2], b[0], b[1], b[2]], o); this.trLife[i] = 0.06; this.trGeo.attributes.position.needsUpdate = true;
  };
  EP.burst = function (x, y, z, n, rgb, spd) {
    for (let k = 0; k < n; k++) {
      const i = this.pI = (this.pI + 1) % this.pN;
      this.pPos[i * 3] = x; this.pPos[i * 3 + 1] = y; this.pPos[i * 3 + 2] = z;
      this.pVel[i * 3] = (Math.random() - 0.5) * spd; this.pVel[i * 3 + 1] = Math.random() * spd * 0.9; this.pVel[i * 3 + 2] = (Math.random() - 0.5) * spd;
      const j = 0.75 + Math.random() * 0.25; this.pCol[i * 3] = rgb[0] * j; this.pCol[i * 3 + 1] = rgb[1] * j; this.pCol[i * 3 + 2] = rgb[2] * j;
      this.pLife[i] = 0.35 + Math.random() * 0.3;
    }
  };
  EP.decal = function (h) {
    const m = this.decals[this.dI = (this.dI + 1) % this.dN];
    m.position.set(h.x + h.nx * 0.015, h.y + h.ny * 0.015, h.z + h.nz * 0.015);
    m.lookAt(h.x + h.nx, h.y + h.ny, h.z + h.nz); m.visible = true;
  };
  EP.flash = function (x, y, z) {
    const m = this.flashes[this.fI = (this.fI + 1) % this.flashes.length];
    m.position.set(x, y, z); m.rotation.set(Math.random() * 3, Math.random() * 3, 0); m.visible = true; m.userData.t = 0.05;
  };
  EP.update = function (dt, cam) {
    let dirty = false;
    for (let i = 0; i < this.trN; i++) if (this.trLife[i] > 0) { this.trLife[i] -= dt; if (this.trLife[i] <= 0) { this.trPos.fill(0, i * 6, i * 6 + 6); dirty = true; } }
    if (dirty) this.trGeo.attributes.position.needsUpdate = true;
    let any = false;
    for (let i = 0; i < this.pN; i++) {
      if (this.pLife[i] <= 0) continue; any = true;
      this.pLife[i] -= dt; this.pVel[i * 3 + 1] -= 9 * dt;
      this.pPos[i * 3] += this.pVel[i * 3] * dt; this.pPos[i * 3 + 1] += this.pVel[i * 3 + 1] * dt; this.pPos[i * 3 + 2] += this.pVel[i * 3 + 2] * dt;
      if (this.pLife[i] <= 0 || this.pPos[i * 3 + 1] < 0) { this.pLife[i] = 0; this.pPos[i * 3 + 1] = -99; }
    }
    if (any) this.pGeo.attributes.position.needsUpdate = true;
    for (const m of this.flashes) if (m.visible) { m.userData.t -= dt; if (m.userData.t <= 0) m.visible = false; else if (cam) m.quaternion.copy(cam.quaternion); }
  };
  EP.dispose = function () {
    for (const o of [this.trGeo, this.trMat, this.pGeo, this.pMat, this.dGeo, this.dMat, this.flashGeo, this.flashMat]) o.dispose();
  };

  // ── Otish (o'yinchi va botlar uchun umumiy) ──
  // shooter: {team, id, eye:[x,y,z]}, targets: entity ro'yxati, returns natijalar
  function fire(world, shooter, wid, ox, oy, oz, yaw, pitch, spread, dmgMul) {
    const w = WEAPONS[wid], map = world.map, out = [];
    const pellets = w.pellets || 1;
    for (let p = 0; p < pellets; p++) {
      const sy = yaw + (Math.random() - 0.5) * 2 * spread, sp = pitch + (Math.random() - 0.5) * 2 * spread;
      const cp = Math.cos(sp), dx = -Math.sin(sy) * cp, dy = Math.sin(sp), dz = -Math.cos(sy) * cp;
      const maxD = w.melee ? w.range : 200;
      const wh = w.melee ? { d: maxD } : map.ray(ox, oy, oz, dx, dy, dz, maxD);
      let best = null, bt = wh.d;
      for (const e of world.entities) {
        if (!e.alive || e === shooter || (e.team === shooter.team && !world.ff)) continue;
        const r = rayEntity(ox, oy, oz, dx, dy, dz, e, bt);
        if (r && r.t < bt) { bt = r.t; best = { e, head: r.head }; }
      }
      const hx = ox + dx * bt, hy = oy + dy * bt, hz = oz + dz * bt;
      if (best) {
        const fall = w.melee ? 1 : U.lerp(1, w.falloff, U.clamp(bt / w.range, 0, 1));
        let dmg = w.dmg * fall * (best.head && !w.melee ? HEAD : 1) * (dmgMul || 1);
        world.damage(best.e, dmg, shooter, wid, best.head, [dx, dz]);
        world.fx.burst(hx, hy, hz, w.melee ? 6 : 5, [0.7, 0.05, 0.05], 2.2);
        out.push({ hit: true, head: best.head, e: best.e });
      } else if (!w.melee && wh.d < maxD) {
        world.fx.decal(wh); world.fx.burst(wh.x, wh.y, wh.z, 4, [0.85, 0.78, 0.6], 3);
        if (p === 0) world.sound('impact', wh.x, wh.z);
        out.push({ hit: false });
      }
      if (!w.melee && (p < 2)) world.fx.tracer([ox + dx * 0.6, oy - 0.08 + dy * 0.6, oz + dz * 0.6], [hx, hy, hz]);
    }
    return out;
  }

  // ── Viewmodel (birinchi shaxs qurol) — past poligonli original modellar ──
  function vmBuild(wid) {
    const g = new THREE.Group(), M = (c) => new THREE.MeshLambertMaterial({ color: c });
    const metal = M(0x2c2f33), dark = M(0x1b1d20), wood = M(0x6b4423), poly = M(0x3d4436), skin = M(0xc99a72), glove = M(0x26282b);
    const B = (w, h, d, m, x, y, z) => { const o = new THREE.Mesh(new THREE.BoxGeometry(w, h, d), m); o.position.set(x, y, z); g.add(o); return o; };
    const C = (r, l, m, x, y, z) => { const o = new THREE.Mesh(new THREE.CylinderGeometry(r, r, l, 8), m); o.rotation.x = Math.PI / 2; o.position.set(x, y, z); g.add(o); return o; };
    let muzzle = [0, 0.02, -0.6];
    if (wid === 'knife') { B(0.03, 0.04, 0.12, dark, 0, 0, 0); const bl = B(0.012, 0.035, 0.22, M(0xc9ccd1), 0, 0.01, -0.17); bl.rotation.x = 0.05; B(0.06, 0.02, 0.03, metal, 0, 0, -0.06); B(0.09, 0.07, 0.1, glove, 0, -0.02, 0.06); muzzle = [0, 0, -0.3]; }
    else if (wid === 'pistol' || wid === 'deagle') {
      const big = wid === 'deagle';
      B(0.05, 0.06, big ? 0.28 : 0.22, big ? M(0x9a9da2) : metal, 0, 0.03, -0.1); B(0.045, 0.12, 0.06, dark, 0, -0.05, 0.0); B(0.05, 0.02, 0.05, dark, 0, -0.01, -0.04);
      C(0.012, 0.04, dark, 0, 0.03, big ? -0.26 : -0.23); B(0.09, 0.09, 0.11, glove, 0, -0.1, 0.03); B(0.07, 0.07, 0.18, skin, 0.01, -0.13, 0.16);
      muzzle = [0, 0.03, big ? -0.28 : -0.24];
    } else {
      const L = { smg: 0.42, rifle: 0.66, sniper: 0.82, shotgun: 0.7 }[wid];
      B(0.06, 0.08, L * 0.55, wid === 'rifle' ? poly : metal, 0, 0, -L * 0.25);          // korpus
      C(wid === 'shotgun' ? 0.022 : 0.013, L * 0.55, dark, 0, 0.015, -L * 0.62);           // stvol
      B(0.045, 0.11, 0.05, dark, 0, -0.08, -0.05);                                          // dasta
      if (wid !== 'shotgun') B(0.04, wid === 'smg' ? 0.16 : 0.13, 0.06, dark, 0, -0.1, -0.17); // magazin
      B(0.055, 0.07, 0.2, wid === 'rifle' || wid === 'shotgun' ? wood : poly, 0, -0.01, 0.16); // qo'ndoq
      if (wid === 'sniper') { C(0.028, 0.24, dark, 0, 0.075, -0.2); B(0.02, 0.04, 0.02, dark, 0, 0.045, -0.2); }
      if (wid === 'rifle') B(0.012, 0.04, 0.03, dark, 0, 0.055, -0.36);
      if (wid === 'shotgun') B(0.06, 0.05, 0.22, wood, 0, -0.035, -0.38);
      B(0.09, 0.09, 0.11, glove, 0, -0.1, -0.02); B(0.08, 0.07, 0.12, glove, -0.02, -0.05, -L * 0.45);
      B(0.07, 0.07, 0.2, skin, 0.02, -0.13, 0.12);
      muzzle = [0, 0.015, -L * 0.9];
    }
    const fl = new THREE.Mesh(new THREE.PlaneGeometry(0.16, 0.16), new THREE.MeshBasicMaterial({ color: 0xffd47a, transparent: true, opacity: 0.95, blending: THREE.AdditiveBlending, depthWrite: false, side: THREE.DoubleSide }));
    fl.position.set(muzzle[0], muzzle[1], muzzle[2]); fl.visible = false; g.add(fl);
    const fl2 = fl.clone(); fl2.rotation.y = Math.PI / 2; g.add(fl2);
    g.userData = { muzzle, flash: [fl, fl2] };
    return g;
  }
  function vmDispose(g) { g.traverse((o) => { if (o.geometry) o.geometry.dispose(); if (o.material) o.material.dispose(); }); }

  // ══ EnemyAI ══
  const DIFF = {
    easy:   { react: 0.85, err: 0.085, view: 26, fov: 1.75, dmg: 0.65, turn: 3.2, strafe: 0, cover: 0.25, burst: [2, 3], hear: 0.7, hp: 90 },
    normal: { react: 0.5, err: 0.055, view: 36, fov: 2.1, dmg: 0.9, turn: 4.8, strafe: 0.5, cover: 0.55, burst: [3, 5], hear: 1, hp: 100 },
    hard:   { react: 0.28, err: 0.034, view: 48, fov: 2.45, dmg: 1.1, turn: 6.8, strafe: 1, cover: 0.85, burst: [4, 7], hear: 1.3, hp: 100 },
  };
  const NAMES = ['Kobra', 'Shadow', 'Viper', 'Falcon', 'Tiger', 'Ghost', 'Wolf', 'Raven', 'Hawk', 'Bison', 'Jaguar', 'Storm', 'Blaze', 'Rex', 'Ozod', 'Bahrom', 'Sarvar', 'Jasur', 'Temur', 'Bek'];
  let botSeq = 0;

  const GEO = {}, MAT = {};
  function botAssets() {
    if (GEO.torso) return;
    GEO.torso = new THREE.BoxGeometry(0.46, 0.6, 0.26); GEO.head = new THREE.BoxGeometry(0.24, 0.26, 0.24); GEO.leg = new THREE.BoxGeometry(0.17, 0.82, 0.2);
    GEO.arm = new THREE.BoxGeometry(0.13, 0.5, 0.14); GEO.gun = new THREE.BoxGeometry(0.07, 0.09, 0.55); GEO.helm = new THREE.BoxGeometry(0.28, 0.1, 0.28); GEO.mark = new THREE.ConeGeometry(0.12, 0.22, 4);
    MAT.T = new THREE.MeshLambertMaterial({ color: 0x9c8452 }); MAT.Tl = new THREE.MeshLambertMaterial({ color: 0x5b4b30 }); MAT.Ta = new THREE.MeshLambertMaterial({ color: 0xa2342a });
    MAT.CT = new THREE.MeshLambertMaterial({ color: 0x31476e }); MAT.CTl = new THREE.MeshLambertMaterial({ color: 0x1f2b40 }); MAT.CTa = new THREE.MeshLambertMaterial({ color: 0x2b2f36 });
    MAT.skin = new THREE.MeshLambertMaterial({ color: 0xc69872 }); MAT.gun = new THREE.MeshLambertMaterial({ color: 0x1d1f22 });
    MAT.ally = new THREE.MeshBasicMaterial({ color: 0x48ff7a }); MAT.hit = new THREE.MeshLambertMaterial({ color: 0xff5555, emissive: 0x661111 });
  }
  function botMesh(team, ally) {
    botAssets();
    const g = new THREE.Group(), body = new THREE.Group(); g.add(body);
    const tm = MAT[team], tl = MAT[team + 'l'], ta = MAT[team + 'a'];
    const torso = new THREE.Mesh(GEO.torso, tm); torso.position.y = 1.18; body.add(torso);
    const head = new THREE.Mesh(GEO.head, MAT.skin); head.position.y = 1.62; body.add(head);
    const hat = new THREE.Mesh(GEO.helm, ta); hat.position.y = team === 'CT' ? 1.76 : 1.6; hat.scale.y = team === 'CT' ? 1 : 0.7; body.add(hat);
    const legL = new THREE.Mesh(GEO.leg, tl), legR = new THREE.Mesh(GEO.leg, tl);
    legL.position.set(-0.11, 0.42, 0); legR.position.set(0.11, 0.42, 0); body.add(legL, legR);
    const armL = new THREE.Mesh(GEO.arm, tm), armR = new THREE.Mesh(GEO.arm, tm);
    armL.position.set(-0.3, 1.2, -0.12); armR.position.set(0.3, 1.2, -0.12); armL.rotation.x = armR.rotation.x = -1.1; body.add(armL, armR);
    const gun = new THREE.Mesh(GEO.gun, MAT.gun); gun.position.set(0.12, 1.22, -0.42); body.add(gun);
    let mark = null; if (ally) { mark = new THREE.Mesh(GEO.mark, MAT.ally); mark.position.y = 2.25; mark.rotation.x = Math.PI; g.add(mark); }
    g.userData = { body, legL, legR, torso, head, mark };
    for (const m of [torso, head, hat, legL, legR, armL, armR, gun]) m.castShadow = true;
    return g;
  }

  function Bot(world, team, diff, opt) {
    this.id = 'b' + (++botSeq); const used = new Set((world.bots || []).map((b) => b.name)), free = NAMES.filter((n) => !used.has(n));
    this.name = opt && opt.name || U.pick(free.length ? free : NAMES); this.bot = true;
    this.team = team; this.D = DIFF[diff] || DIFF.normal; this.world = world;
    const wp = opt && opt.weapon || U.pick(diff === 'hard' ? ['rifle', 'rifle', 'smg', 'deagle'] : ['rifle', 'smg', 'pistol', 'smg', 'shotgun']);
    this.wid = wp; this.mag = WEAPONS[wp].mag;
    this.x = 0; this.z = 0; this.y = 0; this.yaw = 0; this.r = 0.34; this.h = 1.8;
    this.hpMax = Math.round(this.D.hp * (opt && opt.hpMul || 1)); this.hp = this.hpMax; this.alive = true;
    this.kills = 0; this.deaths = 0; this.ally = !!(opt && opt.ally);
    this.mesh = botMesh(team, this.ally); world.scene.add(this.mesh);
    this.reset();
  }
  const BP = Bot.prototype;
  BP.reset = function () {
    this.state = 'patrol'; this.path = null; this.pi = 0; this.target = null; this.seen = null; this.react = 0; this.fireCd = 0;
    this.burst = 0; this.burstPause = 0; this.reloadT = 0; this.coverT = 0; this.lookT = 0; this.perceptT = Math.random() * 0.25;
    this.strafe = Math.random() < 0.5 ? -1 : 1; this.strafeT = 0; this.flinch = 0; this.walkPh = 0; this.deathT = 0; this.goal = null;
    this.repath = 0; this.spotNotified = false; this.stuck = 0; this.lastX = this.x; this.lastZ = this.z; this.plantT = 0;
  };
  BP.spawn = function (x, z) {
    this.x = x; this.z = z; this.y = 0; this.hp = this.hpMax; this.alive = true; this.mag = WEAPONS[this.wid].mag; this.reset();
    this.mesh.visible = true; this.mesh.position.set(x, 0, z); this.mesh.userData.body.rotation.set(0, 0, 0); this.mesh.userData.body.position.y = 0;
    this.yaw = Math.random() * Math.PI * 2;
  };
  BP.eye = function () { return [this.x, this.y + 1.62, this.z]; };
  BP.setPath = function (tx, tz) { this.path = this.world.map.path(this.x, this.z, tx, tz); this.pi = 0; this.repath = 1.2 + Math.random(); };
  BP.follow = function (dt, speed) {
    if (!this.path || this.pi >= this.path.length) return true;
    const [tx, tz] = this.path[this.pi], dx = tx - this.x, dz = tz - this.z, d = Math.hypot(dx, dz);
    if (d < 0.35) { this.pi++; return this.pi >= this.path.length; }
    const want = Math.atan2(-dx, -dz);
    this.yaw += U.clamp(U.angDiff(this.yaw, want), -this.D.turn * dt, this.D.turn * dt);
    this.step(dx / d * speed * dt, dz / d * speed * dt);
    return false;
  };
  BP.step = function (mx, mz) {
    // bir-biridan itarilish
    for (const o of this.world.entities) {
      if (o === this || !o.alive) continue; const ddx = this.x - o.x, ddz = this.z - o.z, d = Math.hypot(ddx, ddz);
      if (d < 0.7 && d > 1e-3) { mx += ddx / d * 0.02; mz += ddz / d * 0.02; }
    }
    this.world.map.move(this, mx, mz, this.r, 0);
    this.walkPh += Math.hypot(mx, mz) * 4.2;
  };
  BP.canSee = function (e) {
    const dx = e.x - this.x, dz = e.z - this.z, d = Math.hypot(dx, dz);
    if (d > this.D.view) return false;
    const ang = Math.abs(U.angDiff(this.yaw, Math.atan2(-dx, -dz)));
    if (d > 3.5 && ang > this.D.fov / 2) return false;
    const ey = this.y + 1.62;
    return this.world.map.los(this.x, ey, this.z, e.x, e.y + 1.35, e.z) || this.world.map.los(this.x, ey, this.z, e.x, e.y + 1.62, e.z);
  };
  BP.perceive = function () {
    let best = null, bd = 1e9;
    for (const e of this.world.entities) {
      if (!e.alive || e.team === this.team) continue;
      if (!this.canSee(e)) continue;
      const d = Math.hypot(e.x - this.x, e.z - this.z); if (d < bd) { bd = d; best = e; }
    }
    if (best) {
      if (this.target !== best || this.state !== 'attack') {
        if (this.state !== 'attack') this.react = this.D.react * U.rand(0.8, 1.3) * (this.state === 'cover' ? 0.6 : 1);
        if (!best.bot && !this.spotNotified) { this.spotNotified = true; this.world.onSpotted(this); }
      }
      this.target = best; this.seen = { x: best.x, z: best.z, t: this.world.time };
      if (!['cover', 'reload', 'retreat'].includes(this.state) || this.world.time - (this.coverStart || 0) > 1.2) this.state = 'attack';
    } else if (this.target && this.world.time - this.seen.t > 0.7) {
      this.target = null;
      if (this.state === 'attack') { this.state = 'chase'; this.setPath(this.seen.x, this.seen.z); }
    }
  };
  BP.hear = function (n) {
    if (this.state === 'attack' || this.state === 'retreat' || n.team === this.team) return;
    const d = Math.hypot(n.x - this.x, n.z - this.z);
    if (d < n.r * this.D.hear) {
      this.state = 'investigate'; this.setPath(n.x + U.rand(-2, 2), n.z + U.rand(-2, 2)); this.lookT = 0;
      this.yaw += U.clamp(U.angDiff(this.yaw, Math.atan2(-(n.x - this.x), -(n.z - this.z))), -0.8, 0.8);
    }
  };
  BP.findCover = function () {
    const th = this.seen; if (!th) return null;
    const map = this.world.map; let best = null, bs = 1e9;
    for (let i = 0; i < 26; i++) {
      const c = map.cover[(Math.random() * map.cover.length) | 0]; if (!c) break;
      const cx = map.center(c[0]), cz = map.center(c[1]), d = Math.hypot(cx - this.x, cz - this.z);
      if (d > 14) continue;
      if (map.los(cx, 1.2, cz, th.x, 1.5, th.z)) continue;   // tahdiddan yashiringan bo'lishi kerak
      const s = d + Math.random() * 2; if (s < bs) { bs = s; best = [cx, cz]; }
    }
    return best;
  };
  BP.shoot = function (dt) {
    const w = WEAPONS[this.wid], t = this.target;
    if (this.mag <= 0) { this.state = 'reload'; this.reloadT = w.reload * U.rand(1, 1.25); return; }
    if (this.fireCd > 0) return;
    if (this.burstPause > 0) { this.burstPause -= dt; return; }
    const e = this.eye(), tx = t.x - e[0], tz = t.z - e[2], d = Math.hypot(tx, tz), ty = t.y + 1.3 - e[1];
    const yaw = Math.atan2(-tx, -tz), pitch = Math.atan2(ty, d);
    if (Math.abs(U.angDiff(this.yaw, yaw)) > 0.35) return;
    const moving = t.speed > 1 ? 1.5 : 1, err = this.D.err * (1 + d / 28) * moving + (w.spread || 0) * 0.5;
    this.world.botFire(this, yaw + U.rand(-err, err), pitch + U.rand(-err, err) * 0.7, 0.004);
    this.mag--; this.fireCd = w.rate * (w.auto ? 1.15 : 1.7);
    if (--this.burst <= 0) { this.burst = U.rand(this.D.burst[0], this.D.burst[1]) | 0; this.burstPause = U.rand(0.25, 0.6); }
  };
  BP.update = function (dt) {
    const W = this.world, ud = this.mesh.userData;
    if (!this.alive) {
      // o'lim animatsiyasi: yiqilish va cho'kish
      this.deathT += dt;
      const k = Math.min(1, this.deathT / 0.55);
      ud.body.rotation.x = -k * 1.45 * this.fallDir; ud.body.position.y = -k * 0.15 - Math.max(0, this.deathT - 3) * 0.4;
      if (this.deathT > 4.5) this.mesh.visible = false;
      return;
    }
    if (this.fireCd > 0) this.fireCd -= dt;
    if (this.flinch > 0) this.flinch -= dt;
    this.perceptT -= dt;
    if (this.perceptT <= 0) { this.perceptT = 0.18 + Math.random() * 0.08; this.perceive(); }
    const D = this.D;
    let speed = 2.9, moving = false;
    switch (this.state) {
      case 'patrol': {
        if (!this.path || this.pi >= this.path.length || this.repath < 0) {
          const g = this.goal;
          if (g && g.x !== undefined) this.setPath(g.x + U.rand(-1.5, 1.5), g.z + U.rand(-1.5, 1.5));
          else { const [px, pz] = W.map.randomFree(); this.setPath(px, pz); }
        }
        this.repath -= dt; moving = !this.follow(dt, speed); break;
      }
      case 'investigate': {
        if (this.follow(dt, 3.3)) { this.lookT += dt; this.yaw += dt * 1.6; if (this.lookT > 2.2) this.state = 'patrol'; } else moving = true;
        break;
      }
      case 'chase': {
        if (this.follow(dt, 4.0)) { this.state = 'investigate'; this.lookT = 0; this.path = null; } else moving = true;
        break;
      }
      case 'attack': {
        const t = this.target;
        if (!t || !t.alive) { this.state = 'patrol'; this.target = null; break; }
        const dx = t.x - this.x, dz = t.z - this.z, d = Math.hypot(dx, dz);
        const want = Math.atan2(-dx, -dz);
        this.yaw += U.clamp(U.angDiff(this.yaw, want), -D.turn * dt, D.turn * dt);
        if (this.react > 0) { this.react -= dt; break; }
        // taktika: kam sog'liq → chekinish; o'q uzilsa → panaga
        if (this.hp < this.hpMax * 0.28 && Math.random() < D.cover * dt * 2) { this.state = 'retreat'; this.path = null; break; }
        if (this.hp < this.hpMax * 0.6 && this.flinch > 0 && Math.random() < D.cover * dt * 3) {
          const c = this.findCover(); if (c) { this.state = 'cover'; this.coverStart = W.time; this.setPath(c[0], c[1]); break; }
        }
        // strafe / yaqinlashish / uzoqlashish
        const w = WEAPONS[this.wid];
        let mx = 0, mz = 0;
        if (D.strafe && (this.strafeT -= dt) < 0) { this.strafeT = U.rand(0.5, 1.4); this.strafe = -this.strafe; }
        if (D.strafe) { mx += Math.cos(want) * this.strafe * 1.9 * D.strafe; mz += -Math.sin(want) * this.strafe * 1.9 * D.strafe; }
        const ideal = w.range * 0.45;
        if (d > ideal + 6) { mx += dx / d * 2.4; mz += dz / d * 2.4; } else if (d < 3 && w.range > 10) { mx -= dx / d * 1.6; mz -= dz / d * 1.6; }
        if (mx || mz) { this.step(mx * dt, mz * dt); moving = true; }
        this.shoot(dt);
        break;
      }
      case 'cover': {
        if (this.follow(dt, 4.2)) {
          this.coverT += dt; if (this.mag < WEAPONS[this.wid].mag * 0.5 && this.reloadT <= 0) { this.reloadT = WEAPONS[this.wid].reload; }
          if (this.reloadT > 0) { this.reloadT -= dt; if (this.reloadT <= 0) this.mag = WEAPONS[this.wid].mag; }
          if (this.coverT > U.rand(1.6, 3)) { this.coverT = 0; this.state = this.seen ? 'chase' : 'patrol'; if (this.seen) this.setPath(this.seen.x, this.seen.z); }
        } else moving = true;
        break;
      }
      case 'reload': {
        this.reloadT -= dt;
        if (this.target && D.cover > 0.5 && !this.path) { const c = this.findCover(); if (c) this.setPath(c[0], c[1]); }
        if (this.path && !this.follow(dt, 3.6)) moving = true;
        if (this.reloadT <= 0) { this.mag = WEAPONS[this.wid].mag; this.state = this.target ? 'attack' : 'patrol'; this.path = null; }
        break;
      }
      case 'retreat': {
        if (!this.path) {
          const sp = W.map.spawns[this.team][0]; if (sp) this.setPath(W.map.center(sp[0]), W.map.center(sp[1]));
          if (!this.path) { this.state = 'cover'; break; }
        }
        if (this.follow(dt, 4.3)) { this.state = 'cover'; this.coverT = 0; this.path = null; } else moving = true;
        if (this.target && this.react <= 0) this.shoot(dt);
        break;
      }
    }
    // tiqilib qolish
    if (moving) {
      const mv = Math.hypot(this.x - this.lastX, this.z - this.lastZ);
      this.stuck = mv < 0.004 ? this.stuck + dt : 0;
      if (this.stuck > 1.2) { this.stuck = 0; this.path = null; this.repath = -1; this.step(U.rand(-0.4, 0.4), U.rand(-0.4, 0.4)); }
    }
    this.lastX = this.x; this.lastZ = this.z;
    this.speed = moving ? speed : 0;
    // animatsiya
    this.mesh.position.set(this.x, 0, this.z); this.mesh.rotation.y = this.yaw;
    const sw = moving ? Math.sin(this.walkPh) * 0.6 : 0;
    ud.legL.rotation.x = sw; ud.legR.rotation.x = -sw;
    ud.body.rotation.z = this.flinch > 0 ? Math.sin(this.flinch * 40) * 0.12 : 0;
    if (ud.mark) ud.mark.rotation.y += dt * 2;
  };
  BP.hurt = function (dmg, from, dir) {
    this.hp -= dmg; this.flinch = 0.18;
    if (from && this.state !== 'attack') {
      this.seen = { x: from.x, z: from.z, t: this.world.time }; this.yaw = Math.atan2(-(from.x - this.x), -(from.z - this.z));
      this.react = Math.min(this.react || this.D.react, this.D.react * 0.5);
      if (this.state !== 'cover' && this.state !== 'retreat') { this.state = 'attack'; this.target = from; }
    }
    if (this.hp <= 0) { this.alive = false; this.deathT = 0; this.fallDir = dir && Math.random() < 0.5 ? -1 : 1; this.path = null; }
  };
  BP.dispose = function () { this.world.scene.remove(this.mesh); };

  function disposeShared() {
    for (const k of Object.keys(GEO)) { GEO[k].dispose(); delete GEO[k]; }
    for (const k of Object.keys(MAT)) { MAT[k].dispose(); delete MAT[k]; }
  }

  CS3D.WeaponSystem = { WEAPONS, fire, rayEntity, Effects, vmBuild, vmDispose, HEAD };
  CS3D.EnemyAI = { Bot, DIFF, NAMES, disposeShared };
})();
