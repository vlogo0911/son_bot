/* METRO DASH — World: Kenney (CC0) modellarini yuklash, atrof-muhit (relslar, graffitili devorlar, shahar, osmon) va
   cheksiz trassa generatori (poyezdlar, rampalar, to'siqlar, tangalar, power-up'lar). O'yinchi -z yo'nalishida yuguradi; s = -z. */
(function () {
  'use strict';
  const MD = window.MDASH, U = MD.U;
  const LANES = [-1.5, 0, 1.5], ROOF = 1.57, CAR = 2.6;
  MD.C = { LANES, ROOF, CAR };

  // ── Resurslar ──
  const Assets = (MD.Assets = {
    world: null, chars: {}, loading: null, base: '', ver: '',
    lib(lib) {
      const sc = (u) => new Promise((ok, bad) => { const e = document.createElement('script'); e.src = u; e.onload = ok; e.onerror = bad; document.head.appendChild(e); });
      const EX = lib || 'https://cdn.jsdelivr.net/npm/three@0.128.0/examples/js/';
      return Promise.all([THREE.GLTFLoader ? 0 : sc(EX + 'loaders/GLTFLoader.js'), window.MeshoptDecoder ? 0 : sc(EX + 'libs/meshopt_decoder.js')]);
    },
    get(file) {
      return new Promise((ok, bad) => { const L = new THREE.GLTFLoader(); L.setMeshoptDecoder(window.MeshoptDecoder); L.load(this.base + file + (this.ver ? '?v=' + this.ver : ''), ok, undefined, bad); });
    },
    load(base, ver, lib) {
      this.base = base || ''; this.ver = ver || '';
      if (this.world) return Promise.resolve();
      if (!this.loading) this.loading = this.lib(lib).then(() => this.get('md_world.glb')).then((g) => {
        const map = {}; for (const n of g.scene.children.slice()) { map[n.name] = n; n.traverse((o) => { if (o.isMesh) { o.frustumCulled = false; if (o.material.map) o.material.map.encoding = THREE.LinearEncoding; } }); }
        this.world = map;
      }).catch((e) => { this.loading = null; throw e; });
      return this.loading;
    },
    char(id) {
      if (this.chars[id]) return Promise.resolve(this.chars[id]);
      return this.get('md_char_' + id + '.glb').then((g) => {
        g.scene.traverse((o) => { if (o.isMesh) { o.frustumCulled = false; if (o.material.map) o.material.map.encoding = THREE.LinearEncoding; } });
        this.chars[id] = g; return g;
      });
    },
    clone(name) { const n = this.world && this.world[name]; return n ? n.clone(true) : null; },
    dispose() {
      const done = new Set(), kill = (root) => root.traverse((o) => { if (o.isMesh && !done.has(o.geometry)) { done.add(o.geometry); o.geometry.dispose(); const m = o.material; if (m.map) m.map.dispose(); m.dispose(); } });
      if (this.world) for (const k of Object.keys(this.world)) kill(this.world[k]);
      for (const k of Object.keys(this.chars)) kill(this.chars[k].scene);
      this.world = null; this.chars = {}; this.loading = null;
    },
  });

  // ── Kanvas teksturalar ──
  function cv(w, h) { const c = document.createElement('canvas'); c.width = w; c.height = h; return [c, c.getContext('2d')]; }
  const GRAF_WORDS = ['METRO', 'DASH', 'RUN!', 'EMPIRE', 'GO', 'FAST', 'YO!', 'TOSH', 'BOOM', 'ZOOM'];
  const GRAF_COLS = ['#ff3b6b', '#ffcc00', '#2fd4ff', '#7dff5a', '#b45cff', '#ff8a1f', '#ffffff'];
  function graffitiTex(seed) {
    const [c, g] = cv(512, 128); let r = seed * 9301 + 49297; const rnd = () => ((r = (r * 9301 + 49297) % 233280) / 233280);
    g.fillStyle = '#8d8f94'; g.fillRect(0, 0, 512, 128);
    for (let i = 0; i < 900; i++) { g.fillStyle = rnd() < 0.5 ? 'rgba(0,0,0,.08)' : 'rgba(255,255,255,.06)'; g.fillRect(rnd() * 512, rnd() * 128, 2, 2); }
    g.fillStyle = 'rgba(0,0,0,.18)'; for (let x = 0; x < 512; x += 64) g.fillRect(x, 0, 2, 128); g.fillRect(0, 118, 512, 10);
    for (let k = 0; k < 2; k++) {        // pufakli graffiti so'zlar
      const word = GRAF_WORDS[(rnd() * GRAF_WORDS.length) | 0], x = 30 + k * 250 + rnd() * 30, y = 82 + rnd() * 10, sz = 52 + rnd() * 14;
      const c1 = GRAF_COLS[(rnd() * GRAF_COLS.length) | 0], c2 = GRAF_COLS[(rnd() * GRAF_COLS.length) | 0];
      g.save(); g.translate(x, y); g.rotate((rnd() - 0.5) * 0.18); g.font = '900 ' + sz + 'px "Arial Black", Impact, sans-serif'; g.lineJoin = 'round';
      g.lineWidth = 14; g.strokeStyle = '#111'; g.strokeText(word, 0, 0); g.lineWidth = 6; g.strokeStyle = '#fff'; g.strokeText(word, 0, 0);
      const gr = g.createLinearGradient(0, -sz, 0, 0); gr.addColorStop(0, c1); gr.addColorStop(1, c2); g.fillStyle = gr; g.fillText(word, 0, 0);
      g.fillStyle = 'rgba(255,255,255,.55)'; g.fillRect(4, -sz * 0.62, word.length * sz * 0.5, 4); g.restore();
    }
    for (let i = 0; i < 4; i++) { g.strokeStyle = GRAF_COLS[(rnd() * GRAF_COLS.length) | 0]; g.lineWidth = 3; g.beginPath(); let x = rnd() * 512, y = 20 + rnd() * 90; g.moveTo(x, y); for (let k = 0; k < 4; k++) { x += (rnd() - 0.3) * 60; y += (rnd() - 0.5) * 30; g.lineTo(x, y); } g.stroke(); }
    const t = new THREE.CanvasTexture(c); t.anisotropy = 4; return t;
  }
  function gravelTex() {
    const [c, g] = cv(256, 256); g.fillStyle = '#6b5f55'; g.fillRect(0, 0, 256, 256);
    for (let i = 0; i < 5000; i++) { const v = (Math.random() * 60) | 0; g.fillStyle = 'rgba(' + (90 + v) + ',' + (80 + v) + ',' + (72 + v) + ',.9)'; g.fillRect(Math.random() * 256, Math.random() * 256, 2 + Math.random() * 2, 2 + Math.random() * 2); }
    const t = new THREE.CanvasTexture(c); t.wrapS = t.wrapT = THREE.RepeatWrapping; t.anisotropy = 4; return t;
  }
  function coinTex() {
    const [c, g] = cv(64, 64), r = g.createRadialGradient(26, 24, 4, 32, 32, 30);
    r.addColorStop(0, '#fff6b0'); r.addColorStop(0.45, '#ffcf2e'); r.addColorStop(1, '#c47a00'); g.fillStyle = r; g.beginPath(); g.arc(32, 32, 30, 0, 7); g.fill();
    g.strokeStyle = '#a86400'; g.lineWidth = 3; g.beginPath(); g.arc(32, 32, 22, 0, 7); g.stroke();
    g.fillStyle = '#a86400'; g.font = '900 26px Arial'; g.textAlign = 'center'; g.textBaseline = 'middle'; g.fillText('$', 32, 34);
    return new THREE.CanvasTexture(c);
  }
  function glowTex() { const [c, g] = cv(64, 64), r = g.createRadialGradient(32, 32, 0, 32, 32, 32); r.addColorStop(0, 'rgba(255,255,255,1)'); r.addColorStop(0.3, 'rgba(255,255,255,.5)'); r.addColorStop(1, 'rgba(255,255,255,0)'); g.fillStyle = r; g.fillRect(0, 0, 64, 64); return new THREE.CanvasTexture(c); }
  function stripeTex(a, b) { const [c, g] = cv(64, 16); for (let i = -2; i < 10; i++) { g.fillStyle = i % 2 ? a : b; g.beginPath(); g.moveTo(i * 8, 16); g.lineTo(i * 8 + 8, 16); g.lineTo(i * 8 + 16, 0); g.lineTo(i * 8 + 8, 0); g.fill(); } const t = new THREE.CanvasTexture(c); t.wrapS = THREE.RepeatWrapping; return t; }
  const PU = MD.PU = {
    magnet: { icon: '🧲', col: '#ff3b5c', dur: 10, name: 'Magnit' },
    jet: { icon: '🚀', col: '#ff9a1a', dur: 7, name: 'Jetpak' },
    boots: { icon: '👟', col: '#7dff5a', dur: 10, name: 'Super sakrash' },
    x2: { icon: '✖2', col: '#2fd4ff', dur: 15, name: 'x2 ochko' },
  };
  function puTex(k) {
    const [c, g] = cv(96, 96), p = PU[k]; g.fillStyle = p.col; g.globalAlpha = 0.95; g.beginPath(); g.arc(48, 48, 42, 0, 7); g.fill(); g.globalAlpha = 1;
    g.strokeStyle = '#fff'; g.lineWidth = 6; g.stroke(); g.font = (k === 'x2' ? '900 34px Arial' : '46px sans-serif'); g.fillStyle = '#fff'; g.textAlign = 'center'; g.textBaseline = 'middle'; g.fillText(p.icon, 48, 52);
    return new THREE.CanvasTexture(c);
  }

  // ── Dunyo ──
  function World(scene, quality) {
    this.scene = scene; this.q = quality; const D = (this.disp = []), own = (o) => { D.push(o); return o; };
    this.obs = []; this.coins = []; this.pows = []; this.genS = 0; this.lastPattern = ''; this.objs = [];
    // Osmon
    scene.background = new THREE.Color(0x8fd0ff); scene.fog = new THREE.Fog(0xbfe4ff, 38, 95);
    const sg = own(new THREE.SphereGeometry(200, 16, 8)), cols = [], top = new THREE.Color(0x3d8fe0), hor = new THREE.Color(0xcdeaff), tmp = new THREE.Color(), pos = sg.attributes.position;
    for (let i = 0; i < pos.count; i++) { const h = Math.max(0, pos.getY(i) / 200); tmp.copy(hor).lerp(top, Math.pow(h, 0.6)); cols.push(tmp.r, tmp.g, tmp.b); }
    sg.setAttribute('color', new THREE.Float32BufferAttribute(cols, 3));
    this.sky = new THREE.Mesh(sg, own(new THREE.MeshBasicMaterial({ vertexColors: true, side: THREE.BackSide, fog: false, depthWrite: false }))); this.sky.renderOrder = -5; scene.add(this.sky);
    const glow = (this.glow = own(glowTex()));
    const sun = new THREE.Sprite(own(new THREE.SpriteMaterial({ map: glow, color: 0xfff2c0, fog: false, depthWrite: false, blending: THREE.AdditiveBlending }))); sun.scale.set(60, 60, 1); sun.position.set(-60, 70, -150); this.sky.add(sun);
    scene.add(new THREE.HemisphereLight(0xffffff, 0x8a7a66, 0.85));
    const dl = (this.sun = new THREE.DirectionalLight(0xfff1dc, 0.85)); dl.position.set(-4, 10, 3); scene.add(dl); scene.add(dl.target);
    // Yer (shag'al) — tekstura s bo'yicha suriladi
    const gt = (this.gravel = own(gravelTex())); gt.repeat.set(6, 30);
    this.ground = new THREE.Mesh(own(new THREE.PlaneGeometry(9, 120)), own(new THREE.MeshLambertMaterial({ map: gt }))); this.ground.rotation.x = -Math.PI / 2; scene.add(this.ground);
    const sideG = own(new THREE.PlaneGeometry(40, 120)), sideM = own(new THREE.MeshLambertMaterial({ color: 0x9a9183 }));
    this.sideL = new THREE.Mesh(sideG, sideM); this.sideL.rotation.x = -Math.PI / 2; this.sideL.position.set(-24.4, 0.02, 0); scene.add(this.sideL);
    this.sideR = this.sideL.clone(); this.sideR.position.x = 24.4; scene.add(this.sideR);
    // Relslar: har yo'lakka shpallar (instanced) + ikkita po'lat rels (uzun bloklar o'yinchi bilan suriladi)
    const slG = own(new THREE.BoxGeometry(1.15, 0.07, 0.2)), slM = own(new THREE.MeshLambertMaterial({ color: 0x5a4636 }));
    this.sleepers = new THREE.InstancedMesh(slG, slM, 3 * 170); this.sleepers.frustumCulled = false; scene.add(this.sleepers);
    const rG = own(new THREE.BoxGeometry(0.07, 0.11, 120)), rM = own(new THREE.MeshLambertMaterial({ color: 0xb8bec8, emissive: 0x1a1d22 }));
    this.railBars = []; for (const lx of LANES) for (const o of [-0.36, 0.36]) { const m = new THREE.Mesh(rG, rM); m.position.set(lx + o, 0.1, 0); scene.add(m); this.railBars.push(m); }
    // Graffitili devorlar (segmentlar qayta ishlatiladi)
    this.wallTex = []; for (let i = 0; i < 6; i++) this.wallTex.push(own(graffitiTex(i + 1)));
    this.wallMats = this.wallTex.map((t) => own(new THREE.MeshLambertMaterial({ map: t })));
    const wg = own(new THREE.BoxGeometry(0.3, 2.4, 12)); wg.translate(0, 1.2, 0);
    this.walls = []; for (let i = 0; i < 18; i++) { const side = i % 2 ? 1 : -1, m = new THREE.Mesh(wg, this.wallMats[i % 6]); m.position.x = side * 3.05; m.rotation.y = side > 0 ? Math.PI : 0; m.userData.s = -999; scene.add(m); this.walls.push(m); }
    // Ustunlar (kontakt tarmog'i)
    const pg = own(new THREE.BoxGeometry(0.12, 3.6, 0.12)); pg.translate(0, 1.8, 0); const am = own(new THREE.BoxGeometry(2.6, 0.1, 0.1));
    const pmat = own(new THREE.MeshLambertMaterial({ color: 0x4a4f58 }));
    this.poles = []; for (let i = 0; i < 16; i++) { const g = new THREE.Group(), side = i % 2 ? 1 : -1, p = new THREE.Mesh(pg, pmat), a = new THREE.Mesh(am, pmat); a.position.set(-side * 1.2, 3.5, 0); g.add(p, a); g.position.x = side * 2.85; g.userData.s = -999; scene.add(g); this.poles.push(g); }
    // Binolar (Kenney City Kit) — ikki tomonda
    const BN = ['building-a', 'building-b', 'building-c', 'building-d', 'building-e', 'building-f', 'building-g', 'building-h', 'building-skyscraper-a', 'building-skyscraper-b', 'building-skyscraper-c'];
    this.blds = []; const nB = quality === 'low' ? 14 : 24;
    for (let i = 0; i < nB; i++) { const o = Assets.clone(BN[i % BN.length]); if (!o) continue; o.scale.setScalar(BN[i % BN.length].includes('sky') ? 4.2 : 5.2); o.userData.side = i % 2 ? 1 : -1; o.userData.s = -999; scene.add(o); this.blds.push(o); }
    // Tangalar — bitta InstancedMesh (aylanadi)
    const cg = own(new THREE.CylinderGeometry(0.22, 0.22, 0.06, 18)); cg.rotateX(Math.PI / 2);
    this.coinMat = own(new THREE.MeshLambertMaterial({ map: own(coinTex()), emissive: 0x553300 }));
    this.coinIM = new THREE.InstancedMesh(cg, this.coinMat, 260); this.coinIM.frustumCulled = false; scene.add(this.coinIM);
    // To'siq materiallari
    this.barMat = own(new THREE.MeshLambertMaterial({ map: own(stripeTex('#d42020', '#f2f2f2')) })); this.legMat = own(new THREE.MeshLambertMaterial({ color: 0x333333 }));
    this.rampMat = own(new THREE.MeshLambertMaterial({ color: 0x8a6a45 })); this.signMat = own(new THREE.MeshLambertMaterial({ color: 0xffc400 }));
    this.puMats = {}; for (const k of Object.keys(PU)) this.puMats[k] = own(new THREE.SpriteMaterial({ map: own(puTex(k)), depthWrite: false }));
    this.puGlow = own(new THREE.SpriteMaterial({ map: glow, color: 0xffffff, transparent: true, opacity: 0.6, depthWrite: false, blending: THREE.AdditiveBlending }));
    this.boxG = own(new THREE.BoxGeometry(1, 1, 1)); this.trainMat = own(new THREE.MeshLambertMaterial({ color: 0x3a7bd5 }));
    const rampG = (this.rampG = own(new THREE.BufferGeometry()));      // pona (s yo'nalishida ko'tariladi)
    const L = 2.6, W = 1.25, H = ROOF; rampG.setAttribute('position', new THREE.Float32BufferAttribute([
      -W / 2, 0, 0, W / 2, 0, 0, W / 2, H, -L, -W / 2, 0, 0, W / 2, H, -L, -W / 2, H, -L,     // ustki qiya yuza
      -W / 2, 0, 0, -W / 2, H, -L, -W / 2, 0, -L, W / 2, 0, 0, W / 2, 0, -L, W / 2, H, -L,    // yon tomonlar
      -W / 2, 0, -L, -W / 2, H, -L, W / 2, H, -L, -W / 2, 0, -L, W / 2, H, -L, W / 2, 0, -L,   // orqa
    ], 3)); rampG.computeVertexNormals();
  }
  const WP = World.prototype;
  WP.reset = function () {
    for (const o of this.objs) this.scene.remove(o); this.objs = [];
    this.obs = []; this.coins = []; this.pows = []; this.genS = 26;
    for (const w of this.walls) w.userData.s = -999; for (const p of this.poles) p.userData.s = -999; for (const b of this.blds) b.userData.s = -999;
  };
  WP.add = function (o) { this.scene.add(o); this.objs.push(o); return o; };
  // ── Obyektlar ──
  const TRAINS = ['train-electric-subway-a', 'train-electric-subway-b', 'train-electric-subway-c', 'train-electric-city-a', 'train-electric-city-c'];
  WP.train = function (lane, s0, cars, speed) {
    const g = new THREE.Group(), kind = U.pick(TRAINS);
    for (let i = 0; i < cars; i++) {
      let c = Assets.clone(kind);
      if (!c) { c = new THREE.Mesh(this.boxG, this.trainMat); c.scale.set(1.35, ROOF, CAR - 0.1); c.position.y = ROOF / 2; }     // model yuklanmasa — oddiy vagon
      c.position.z = -i * CAR - CAR / 2; if (i > 0 && i === cars - 1) c.rotation.y = Math.PI; g.add(c);
    }
    g.position.set(LANES[lane], 0, -s0); this.add(g);
    const o = { type: 'train', lane, s0, s1: s0 + cars * CAR, h: ROOF, speed: speed || 0, mesh: g }; this.obs.push(o); return o;
  };
  WP.ramp = function (lane, s0) {
    const m = new THREE.Mesh(this.rampG, this.rampMat); m.position.set(LANES[lane], 0, -s0); this.add(m);
    const o = { type: 'ramp', lane, s0, s1: s0 + 2.6, h: ROOF, mesh: m }; this.obs.push(o); return o;
  };
  WP.barrier = function (lane, s, kind) {      // low — sakrash, high — sirpanish (roll)
    const g = new THREE.Group(), bar = new THREE.Mesh(this.boxG, this.barMat);
    if (kind === 'low') { bar.scale.set(1.25, 0.32, 0.12); bar.position.y = 0.42; }
    else { bar.scale.set(1.25, 0.34, 0.12); bar.position.y = 1.02; const sign = new THREE.Mesh(this.boxG, this.signMat); sign.scale.set(0.5, 0.22, 0.05); sign.position.y = 1.32; g.add(sign); }
    g.add(bar);
    for (const sx of [-0.55, 0.55]) { const l = new THREE.Mesh(this.boxG, this.legMat); const hh = kind === 'low' ? 0.58 : 1.2; l.scale.set(0.07, hh, 0.07); l.position.set(sx, hh / 2, 0); g.add(l); }
    g.position.set(LANES[lane], 0, -s); this.add(g);
    const o = kind === 'low' ? { type: 'low', lane, s0: s - 0.12, s1: s + 0.12, top: 0.58, mesh: g } : { type: 'high', lane, s0: s - 0.12, s1: s + 0.12, bot: 0.85, mesh: g };
    this.obs.push(o); return o;
  };
  WP.coinLine = function (lane, s0, n, y, gap, arc) {
    for (let i = 0; i < n; i++) { const t = n > 1 ? i / (n - 1) : 0; this.coins.push({ lane, s: s0 + i * (gap || 1.2), y: y + (arc ? Math.sin(t * Math.PI) * arc : 0), got: false, x: LANES[lane] }); }
  };
  WP.power = function (lane, s, kind) {
    const spr = new THREE.Sprite(this.puMats[kind]); spr.scale.set(0.7, 0.7, 1); const gl = new THREE.Sprite(this.puGlow); gl.scale.set(1.5, 1.5, 1);
    const g = new THREE.Group(); g.add(gl, spr); g.position.set(LANES[lane], 0.6, -s); this.add(g);
    this.pows.push({ lane, s, kind, got: false, mesh: g });
  };
  // Yo'lakdagi eng yaqin to'siq oxiri (harakatlanuvchi poyezd uchun bo'sh yo'lak tanlash)
  WP.laneFreeFrom = function (lane, fromS, toS) { return !this.obs.some((o) => o.lane === lane && o.s1 > fromS && o.s0 < toS); };

  // ── Generator: har bo'lak kamida bitta o'tib bo'ladigan yo'l qoldiradi ──
  WP.generate = function (playerS, diff) {
    while (this.genS < playerS + 90) {
      const s = this.genS, d = U.clamp(diff, 0, 1);
      const pats = ['trains', 'rampTrain', 'barriers', 'mixed', 'coins'];
      if (d > 0.15) pats.push('moving', 'trains');
      if (d > 0.35) pats.push('moving', 'wall2');
      let p = U.pick(pats); if (p === this.lastPattern && p !== 'trains') p = 'barriers'; this.lastPattern = p;
      const L = [0, 1, 2].sort(() => Math.random() - 0.5);
      let len = 16;
      if (p === 'trains') {
        const c1 = U.irand(2, 4), c2 = U.irand(2, 3);
        this.train(L[0], s + 4, c1); this.train(L[1], s + 6 + U.irand(0, 4), c2);
        this.coinLine(L[2], s + 3, 8, 0.35); len = 8 + Math.max(c1, c2) * CAR;
      } else if (p === 'rampTrain') {
        const c = U.irand(3, 5); this.ramp(L[0], s + 4); const t = this.train(L[0], s + 6.6, c);
        this.coinLine(L[0], s + 7.5, Math.floor(c * CAR / 1.2), ROOF + 0.35);
        if (Math.random() < 0.6) this.train(L[1], s + 8, U.irand(2, 3)); else this.barrier(L[1], s + 9, 'low');
        if (Math.random() < 0.3) this.power(L[0], t.s1 - 1.2, U.pick(Object.keys(PU)));
        len = 10 + c * CAR;
      } else if (p === 'barriers') {
        const k = ['low', 'high', U.pick(['low', 'high'])];
        for (let i = 0; i < 3; i++) this.barrier(L[i], s + 6, k[i]);
        this.coinLine(L[0], s + 3, 6, 0.35, 1.0, k[0] === 'low' ? 1.0 : 0);
        if (Math.random() < 0.5) { for (let i = 0; i < 3; i++) this.barrier(L[i], s + 14, U.pick(['low', 'high'])); len = 20; } else len = 13;
      } else if (p === 'mixed') {
        this.train(L[0], s + 4, U.irand(2, 4)); this.barrier(L[1], s + 7, U.pick(['low', 'high'])); this.coinLine(L[2], s + 4, 6, 0.35);
        if (Math.random() < 0.35) this.power(L[2], s + 12, U.pick(Object.keys(PU)));
        len = 16;
      } else if (p === 'moving') {
        const lane = [0, 1, 2].find((l) => this.laneFreeFrom(l, playerS - 2, s + 30));
        if (lane != null) {
          const sp = 5 + d * 6; this.train(lane, s + 18, U.irand(2, 3), sp);
          const other = [0, 1, 2].filter((l) => l !== lane); this.coinLine(U.pick(other), s + 4, 8, 0.35);
          if (Math.random() < 0.5) this.barrier(other[0], s + 10, U.pick(['low', 'high']));
        } else this.coinLine(1, s + 4, 8, 0.35);
        len = 18;
      } else if (p === 'wall2') {
        const c = U.irand(3, 4); this.train(L[0], s + 4, c); this.train(L[1], s + 4, c); this.barrier(L[2], s + 7, U.pick(['low', 'high']));
        this.coinLine(L[2], s + 9, 6, 0.35); len = 6 + c * CAR;
      } else {
        let lane = U.irand(0, 2); for (let i = 0; i < 14; i++) { if (i % 5 === 4) lane = U.clamp(lane + U.pick([-1, 1]), 0, 2); this.coinLine(lane, s + 2 + i * 1.1, 1, 0.35); }
        if (Math.random() < 0.5) this.power(U.irand(0, 2), s + 10, U.pick(Object.keys(PU)));
        len = 18;
      }
      this.genS += len + Math.max(3, 9 - d * 6);
    }
  };
  // Har kadr: harakatlanuvchi poyezdlar, atrof-muhit qayta ishlatilishi, tangalar rendering
  const M4 = new THREE.Matrix4(), Q = new THREE.Quaternion(), V = new THREE.Vector3(), SC = new THREE.Vector3(1, 1, 1), E = new THREE.Euler();
  WP.update = function (dt, ps, time, cam) {
    for (const o of this.obs) if (o.speed) { o.s0 -= o.speed * dt; o.s1 -= o.speed * dt; o.mesh.position.z = -o.s0; }
    // eskilarini olib tashlash
    for (let i = this.obs.length - 1; i >= 0; i--) { const o = this.obs[i]; if (o.s1 < ps - 12) { this.scene.remove(o.mesh); this.obs.splice(i, 1); const j = this.objs.indexOf(o.mesh); if (j >= 0) this.objs.splice(j, 1); } }
    for (let i = this.pows.length - 1; i >= 0; i--) { const p = this.pows[i]; p.mesh.position.y = 0.6 + Math.sin(time * 4 + p.s) * 0.12; if (p.s < ps - 6 || p.got) { this.scene.remove(p.mesh); this.pows.splice(i, 1); } }
    if (this.coins.length > 400) this.coins = this.coins.filter((c) => c.s > ps - 4 && !c.got);
    // relslar: shpallar 0.6 m qadam bilan
    const base = Math.floor(ps / 0.6) - 16; let k = 0;
    for (let l = 0; l < 3; l++) for (let i = 0; i < 170; i++) { M4.makeTranslation(LANES[l], 0.035, -(base + i) * 0.6); this.sleepers.setMatrixAt(k++, M4); }
    this.sleepers.instanceMatrix.needsUpdate = true; for (const m of this.railBars) m.position.z = -ps - 45;
    this.ground.position.z = -ps - 45; this.sideL.position.z = this.sideR.position.z = -ps - 45; this.gravel.offset.y = (ps / 4) % 1;
    for (const w of this.walls) if (w.userData.s < ps - 14) { const side = w.position.x > 0 ? 1 : -1; let mx = ps - 14; for (const q of this.walls) if (Math.sign(q.position.x) === side) mx = Math.max(mx, q.userData.s); w.userData.s = mx + 12; w.position.z = -w.userData.s; w.material = U.pick(this.wallMats); }
    for (const p of this.poles) if (p.userData.s < ps - 14) { let mx = ps - 14; for (const q of this.poles) if (Math.sign(q.position.x) === Math.sign(p.position.x)) mx = Math.max(mx, q.userData.s); p.userData.s = mx + 15; p.position.z = -p.userData.s; }
    for (const b of this.blds) if (b.userData.s < ps - 20) { let mx = ps - 20; for (const q of this.blds) if (q.userData.side === b.userData.side) mx = Math.max(mx, q.userData.s); b.userData.s = mx + U.rand(6, 10); b.position.set(b.userData.side * U.rand(8, 13), 0, -b.userData.s); b.rotation.y = b.userData.side > 0 ? -Math.PI / 2 : Math.PI / 2; }
    // tangalar
    let n = 0; const rot = time * 3;
    for (const c of this.coins) { if (c.got || c.s < ps - 3 || c.s > ps + 80) continue; if (n >= 260) break; E.set(0, rot + c.s, 0); Q.setFromEuler(E); V.set(c.x, c.y, -c.s); M4.compose(V, Q, SC); this.coinIM.setMatrixAt(n++, M4); }
    this.coinIM.count = n; this.coinIM.instanceMatrix.needsUpdate = true;
    this.sky.position.copy(cam.position); this.sun.position.set(cam.position.x - 4, 10, cam.position.z + 3); this.sun.target.position.set(cam.position.x, 0, cam.position.z - 6);
  };
  // Yuza balandligi (o'yinchi turgan joyda): poyezd tomi yoki rampa
  WP.groundAt = function (x, s) {
    let h = 0;
    for (const o of this.obs) {
      if (Math.abs(LANES[o.lane] - x) > 0.72) continue; if (s < o.s0 - 0.05 || s > o.s1 + 0.05) continue;
      if (o.type === 'train') h = Math.max(h, ROOF); else if (o.type === 'ramp') h = Math.max(h, U.clamp((s - o.s0) / (o.s1 - o.s0), 0, 1) * ROOF);
    }
    return h;
  };
  WP.dispose = function () {
    this.reset(); for (const d of this.disp) { try { d.dispose(); } catch (e) { /* */ } }
  };
  MD.World = World;
})();
