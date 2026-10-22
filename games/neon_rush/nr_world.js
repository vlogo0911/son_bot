/* NEON RUSH — World: 3 ta original trassa (yopiq spline), yo'l/to'siq/neon chiziqlar, shahar va kanyon manzarasi,
   trassa bo'yicha joylashuv (progress, lateral), power-up joylari. Draw call'lar kam: instancing + Points. */
(function () {
  'use strict';
  const NR = window.NR3D, U = NR.U;

  const TRACKS = {
    harbor: {
      name: 'Neon Harbor', sub: 'Tungi port shahri, ho‘l asfalt', width: 17, laps: 3, kind: 'city',
      pts: [[0, 0, 0], [160, 0, 0], [270, 30, 0], [320, 130, 2], [290, 240, 6], [190, 290, 6], [90, 250, 2], [20, 300, 0], [-90, 330, 0],
        [-190, 270, 0], [-200, 160, 0], [-140, 90, 0], [-210, 30, 0], [-140, -30, 0]],
      sky: [0x05010f, 0x2a0a3d, 0x6a1b5a], fog: [0x1a0830, 120, 520], ground: '#0b0b14', road: ['#1c1d24', '#23242c'], wet: true,
      neon: [0xff2bd6, 0x22e4ff], bld: [0x1a1d2e, 0x23182e, 0x14233a, 0x2b1a24], win: ['#ffd27a', '#7af0ff', '#ff7ae0', '#ffffff'], lamp: 0xffb84d,
      sun: null, stars: true, hemi: [0x6a5aff, 0x10081a, 0.9], dir: [0xff6ad5, 0.35],
    },
    canyon: {
      name: 'Sunset Canyon', sub: 'Shom paytidagi qizil kanyon, tepaliklar', width: 16, laps: 3, kind: 'canyon',
      pts: [[0, 0, 0], [180, 10, 4], [300, 80, 12], [330, 200, 18], [240, 280, 10], [120, 250, 4], [60, 330, 8], [-60, 350, 14], [-170, 290, 10],
        [-200, 170, 4], [-120, 110, 0], [-180, 40, 2], [-110, -30, 0]],
      sky: [0x1b1340, 0xb3477a, 0xffa25a], fog: [0xe0805a, 160, 650], ground: '#7a3d22', road: ['#3a2c28', '#433330'], wet: false,
      neon: [0xffa024, 0xb04bff], rock: [0xa04a2a, 0x8a3b22, 0xb85a30, 0x6e2f1c], lamp: 0xffd08a,
      sun: 0xffb36b, stars: false, hemi: [0xffc49a, 0x5a2030, 0.95], dir: [0xffb07a, 0.8],
    },
    downtown: {
      name: 'Downtown Rush', sub: 'Tor burilishli markaz, osmono‘par binolar', width: 15, laps: 3, kind: 'city',
      pts: [[0, 0, 0], [190, 0, 0], [230, 40, 0], [225, 150, 0], [160, 175, 0], [150, 255, 0], [70, 285, 0], [-20, 250, 0], [-40, 170, 0],
        [-130, 160, 0], [-170, 90, 0], [-130, 20, 0], [-60, -20, 0]],
      sky: [0x02040c, 0x0b1a3a, 0x1d3f6e], fog: [0x0a1630, 100, 460], ground: '#0a0d14', road: ['#202228', '#272a31'], wet: true,
      neon: [0x2b8cff, 0xffd400], bld: [0x161a24, 0x1c2230, 0x202020, 0x182028], win: ['#9fd3ff', '#ffe08a', '#ffffff', '#7affc8'], lamp: 0xcfe4ff,
      sun: null, stars: true, hemi: [0x5a8aff, 0x08101c, 0.9], dir: [0x9ec8ff, 0.35],
    },
  };

  // ── Kanvas teksturalar ──
  function cv(w, h) { const c = document.createElement('canvas'); c.width = w; c.height = h; return [c, c.getContext('2d')]; }
  function roadTex(T) {
    const [c, g] = cv(256, 256);
    g.fillStyle = T.road[0]; g.fillRect(0, 0, 256, 256);
    for (let i = 0; i < 2600; i++) { g.fillStyle = Math.random() < 0.5 ? 'rgba(255,255,255,.035)' : 'rgba(0,0,0,.09)'; g.fillRect(Math.random() * 256, Math.random() * 256, 1 + Math.random() * 2, 1 + Math.random() * 2); }
    g.fillStyle = 'rgba(255,255,255,.55)'; g.fillRect(6, 0, 5, 256); g.fillRect(245, 0, 5, 256);       // chekka chiziqlar
    g.fillStyle = 'rgba(255,255,255,.4)'; g.fillRect(84, 0, 3, 120); g.fillRect(169, 0, 3, 120);       // bo'lak chiziqlari
    if (T.wet) { const gr = g.createLinearGradient(0, 0, 256, 0); gr.addColorStop(0.3, 'rgba(120,140,255,0)'); gr.addColorStop(0.5, 'rgba(120,140,255,.07)'); gr.addColorStop(0.7, 'rgba(120,140,255,0)'); g.fillStyle = gr; g.fillRect(0, 0, 256, 256); }
    const t = new THREE.CanvasTexture(c); t.wrapS = t.wrapT = THREE.RepeatWrapping; t.anisotropy = 4; return t;
  }
  function wallTex(col) {
    const [c, g] = cv(128, 32);
    g.fillStyle = '#15161c'; g.fillRect(0, 0, 128, 32);
    g.fillStyle = col; for (let i = -1; i < 9; i++) { g.beginPath(); g.moveTo(i * 16, 32); g.lineTo(i * 16 + 8, 32); g.lineTo(i * 16 + 24, 0); g.lineTo(i * 16 + 16, 0); g.fill(); }
    g.fillStyle = 'rgba(0,0,0,.45)'; g.fillRect(0, 0, 128, 6); g.fillRect(0, 26, 128, 6);
    const t = new THREE.CanvasTexture(c); t.wrapS = THREE.RepeatWrapping; return t;
  }
  function windowTex(T) {
    const [c, g] = cv(128, 256);
    g.fillStyle = '#000'; g.fillRect(0, 0, 128, 256);
    for (let y = 6; y < 250; y += 12) for (let x = 6; x < 124; x += 12) {
      if (Math.random() < 0.42) continue;
      g.fillStyle = U.pick(T.win); g.globalAlpha = 0.35 + Math.random() * 0.65; g.fillRect(x, y, 7, 7);
    }
    g.globalAlpha = 1; return new THREE.CanvasTexture(c);
  }
  function rockTex() {
    const [c, g] = cv(128, 128);
    g.fillStyle = '#9a6a52'; g.fillRect(0, 0, 128, 128);
    for (let y = 0; y < 128; y += 4) { g.fillStyle = 'rgba(0,0,0,' + (0.05 + Math.random() * 0.15) + ')'; g.fillRect(0, y, 128, 2 + Math.random() * 3); }
    for (let i = 0; i < 500; i++) { g.fillStyle = 'rgba(255,220,180,.08)'; g.fillRect(Math.random() * 128, Math.random() * 128, 2, 2); }
    return new THREE.CanvasTexture(c);
  }
  function glowTex() {
    const [c, g] = cv(64, 64), r = g.createRadialGradient(32, 32, 0, 32, 32, 32);
    r.addColorStop(0, 'rgba(255,255,255,1)'); r.addColorStop(0.25, 'rgba(255,255,255,.55)'); r.addColorStop(1, 'rgba(255,255,255,0)');
    g.fillStyle = r; g.fillRect(0, 0, 64, 64); return new THREE.CanvasTexture(c);
  }
  function stripTex() {      // neon chiziq atrofidagi yorug'lik (gorizontal gradient)
    const [c, g] = cv(4, 64), r = g.createLinearGradient(0, 0, 0, 64);
    r.addColorStop(0, 'rgba(255,255,255,0)'); r.addColorStop(0.5, 'rgba(255,255,255,1)'); r.addColorStop(1, 'rgba(255,255,255,0)');
    g.fillStyle = r; g.fillRect(0, 0, 4, 64); return new THREE.CanvasTexture(c);
  }
  function checkerTex() {
    const [c, g] = cv(128, 32);
    for (let y = 0; y < 4; y++) for (let x = 0; x < 16; x++) { g.fillStyle = (x + y) % 2 ? '#111' : '#eee'; g.fillRect(x * 8, y * 8, 8, 8); }
    return new THREE.CanvasTexture(c);
  }
  NR.Tex = { glowTex };

  // ── Track ──
  function Track(id) {
    const T = (this.def = TRACKS[id] || TRACKS.harbor); this.id = TRACKS[id] ? id : 'harbor';
    this.W = T.width; this.laps = T.laps;
    const curve = new THREE.CatmullRomCurve3(T.pts.map((p) => new THREE.Vector3(p[0], p[2], p[1])), true, 'centripetal');
    this.length = curve.getLength();
    const M = (this.M = Math.round(this.length / 2.5)); this.step = this.length / M;
    const pts = curve.getSpacedPoints(M); pts.pop();
    this.px = new Float32Array(M); this.py = new Float32Array(M); this.pz = new Float32Array(M);
    this.tx = new Float32Array(M); this.tz = new Float32Array(M); this.sx = new Float32Array(M); this.sz = new Float32Array(M);
    this.curv = new Float32Array(M); this.head = new Float32Array(M);
    for (let i = 0; i < M; i++) { this.px[i] = pts[i].x; this.py[i] = pts[i].y; this.pz[i] = pts[i].z; }
    for (let i = 0; i < M; i++) {
      const a = (i - 1 + M) % M, b = (i + 1) % M; let dx = this.px[b] - this.px[a], dz = this.pz[b] - this.pz[a]; const l = Math.hypot(dx, dz) || 1;
      dx /= l; dz /= l; this.tx[i] = dx; this.tz[i] = dz; this.sx[i] = dz; this.sz[i] = -dx;   // s — o'ng tomon
      this.head[i] = Math.atan2(dx, dz);
    }
    for (let i = 0; i < M; i++) {          // egrilik: oldindagi 6 nuqta bo'yicha burchak o'zgarishi / masofa
      const j = (i + 6) % M; this.curv[i] = Math.abs(U.angDiff(this.head[i], this.head[j])) / (6 * this.step);
    }
    // Power-up joylari: trassa bo'ylab 6 ta qator, har birida 3 ta
    this.pads = [];
    for (let k = 0; k < 6; k++) {
      const d = this.length * (0.08 + k / 6);
      for (const lat of [-this.W / 3.2, 0, this.W / 3.2]) { const p = this.at(d, lat); this.pads.push({ x: p.x, y: p.y, z: p.z, d, lat, t: 0, kind: null }); }
    }
  }
  const P = Track.prototype;
  P.wrapI = function (i) { const M = this.M; return ((i % M) + M) % M; };
  // d masofadagi (lateral siljish bilan) nuqta
  P.at = function (d, lat) {
    const L = this.length; d = ((d % L) + L) % L;
    const f = d / this.step, i = Math.floor(f) % this.M, j = (i + 1) % this.M, t = f - Math.floor(f);
    const x = U.lerp(this.px[i], this.px[j], t), y = U.lerp(this.py[i], this.py[j], t), z = U.lerp(this.pz[i], this.pz[j], t);
    const sx = U.lerp(this.sx[i], this.sx[j], t), sz = U.lerp(this.sz[i], this.sz[j], t);
    return { x: x + sx * (lat || 0), y, z: z + sz * (lat || 0), head: this.head[i] + U.angDiff(this.head[i], this.head[j]) * t, i };
  };
  // Dunyodagi nuqtani trassaga proyeksiya qilish (hint — oldingi indeks, lokal qidiruv)
  P.locate = function (x, z, hint, out) {
    const M = this.M; let best = -1, bd = 1e18;
    const lo = hint == null ? 0 : hint - 10, hi = hint == null ? M : hint + 16;
    for (let k = lo; k < hi; k++) { const i = ((k % M) + M) % M, dx = x - this.px[i], dz = z - this.pz[i], d = dx * dx + dz * dz; if (d < bd) { bd = d; best = i; } }
    if (hint != null && bd > 30 * 30) return this.locate(x, z, null, out);
    const i = best, dx = x - this.px[i], dz = z - this.pz[i];
    let along = dx * this.tx[i] + dz * this.tz[i], ii = i;
    if (along < 0) { ii = (i - 1 + M) % M; along = (x - this.px[ii]) * this.tx[ii] + (z - this.pz[ii]) * this.tz[ii]; }
    let t = U.clamp(along / this.step, 0, 1), jj = (ii + 1) % M, lat = 0;
    for (let it = 0; it < 3; it++) {     // interpolatsiyalangan normal bo'yicha aniqlashtirish (burilishlarda xato kam)
      const cx = U.lerp(this.px[ii], this.px[jj], t), cz = U.lerp(this.pz[ii], this.pz[jj], t);
      let tx = U.lerp(this.tx[ii], this.tx[jj], t), tz = U.lerp(this.tz[ii], this.tz[jj], t); const l = Math.hypot(tx, tz) || 1; tx /= l; tz /= l;
      const ex = x - cx, ez = z - cz; lat = ex * tz - ez * tx;
      const dt = (ex * tx + ez * tz) / this.step; if (Math.abs(dt) < 1e-4) break;
      t += dt;
      if (t > 1) { ii = jj; jj = (ii + 1) % M; t -= 1; } else if (t < 0) { jj = ii; ii = (ii - 1 + M) % M; t += 1; }
      t = U.clamp(t, 0, 1);
    }
    out = out || {}; out.i = ii; out.d = (ii + t) * this.step; out.lat = lat; out.y = U.lerp(this.py[ii], this.py[jj], t);
    out.head = this.head[ii]; out.sx = this.sx[ii]; out.sz = this.sz[ii]; out.tx = this.tx[ii]; out.tz = this.tz[ii];
    out.slope = (this.py[jj] - this.py[ii]) / this.step;
    return out;
  };
  // Oldindagi egrilik (AI tezligi uchun)
  P.curvAhead = function (i, n) { let m = 0; for (let k = 0; k < n; k++) m = Math.max(m, this.curv[(i + k) % this.M]); return m; };
  P.minimap = function () {
    let x0 = 1e9, x1 = -1e9, z0 = 1e9, z1 = -1e9;
    for (let i = 0; i < this.M; i++) { x0 = Math.min(x0, this.px[i]); x1 = Math.max(x1, this.px[i]); z0 = Math.min(z0, this.pz[i]); z1 = Math.max(z1, this.pz[i]); }
    return { x0, z0, s: Math.max(x1 - x0, z1 - z0) || 1 };
  };

  // ── Sahna qurish ──
  P.build = function (scene, quality) {
    const T = this.def, D = (this.disp = []), M = this.M, W = this.W, hq = quality === 'high', lq = quality === 'low';
    const own = (o) => { D.push(o); return o; };
    scene.background = new THREE.Color(T.sky[0]);
    scene.fog = new THREE.Fog(T.fog[0], T.fog[1] * (lq ? 0.8 : 1), T.fog[2] * (lq ? 0.75 : 1));
    // Osmon gumbazi (vertex rang gradient)
    const sg = own(new THREE.SphereGeometry(900, 24, 12)), cols = [], c0 = new THREE.Color(T.sky[0]), c1 = new THREE.Color(T.sky[1]), c2 = new THREE.Color(T.sky[2]), tmp = new THREE.Color();
    const pos = sg.attributes.position;
    for (let i = 0; i < pos.count; i++) { const h = pos.getY(i) / 900; if (h > 0.25) tmp.copy(c1).lerp(c0, U.clamp((h - 0.25) / 0.75, 0, 1)); else tmp.copy(c2).lerp(c1, U.clamp((h + 0.05) / 0.3, 0, 1)); cols.push(tmp.r, tmp.g, tmp.b); }
    sg.setAttribute('color', new THREE.Float32BufferAttribute(cols, 3));
    const sky = new THREE.Mesh(sg, own(new THREE.MeshBasicMaterial({ vertexColors: true, side: THREE.BackSide, fog: false, depthWrite: false })));
    sky.renderOrder = -10; scene.add(sky); this.sky = sky;
    const glow = own(glowTex());
    if (T.stars) {
      const sp = []; for (let i = 0; i < 600; i++) { const a = Math.random() * Math.PI * 2, e = 0.15 + Math.random() * 1.3; sp.push(Math.cos(a) * Math.cos(e) * 850, Math.sin(e) * 850, Math.sin(a) * Math.cos(e) * 850); }
      const stg = own(new THREE.BufferGeometry()); stg.setAttribute('position', new THREE.Float32BufferAttribute(sp, 3));
      const st = new THREE.Points(stg, own(new THREE.PointsMaterial({ size: 2.2, sizeAttenuation: false, color: 0xffffff, fog: false, transparent: true, opacity: 0.8 })));
      sky.add(st);
    }
    if (T.sun) {
      const sm = own(new THREE.SpriteMaterial({ map: glow, color: T.sun, fog: false, depthWrite: false, blending: THREE.AdditiveBlending }));
      const sun = new THREE.Sprite(sm); sun.scale.set(420, 420, 1); sun.position.set(-500, 70, 600); sky.add(sun);
      const core = new THREE.Sprite(own(new THREE.SpriteMaterial({ map: glow, color: 0xfff0d0, fog: false, depthWrite: false, blending: THREE.AdditiveBlending }))); core.scale.set(120, 120, 1); core.position.copy(sun.position); sky.add(core);
    }
    // Yorug'lik
    scene.add(new THREE.HemisphereLight(T.hemi[0], T.hemi[1], T.hemi[2]));
    const dl = new THREE.DirectionalLight(T.dir[0], T.dir[1]); dl.position.set(-200, 300, 250); scene.add(dl);
    // Yer
    const [gc, gg] = cv(64, 64); gg.fillStyle = T.ground; gg.fillRect(0, 0, 64, 64);
    if (T.kind === 'city') { gg.strokeStyle = 'rgba(120,140,255,.10)'; gg.strokeRect(0.5, 0.5, 63, 63); } else for (let i = 0; i < 300; i++) { gg.fillStyle = 'rgba(0,0,0,.08)'; gg.fillRect(Math.random() * 64, Math.random() * 64, 2, 2); }
    const gt = own(new THREE.CanvasTexture(gc)); gt.wrapS = gt.wrapT = THREE.RepeatWrapping; gt.repeat.set(160, 160);
    const ground = new THREE.Mesh(own(new THREE.PlaneGeometry(2400, 2400)), own(new THREE.MeshLambertMaterial({ map: gt })));
    ground.rotation.x = -Math.PI / 2; ground.position.set(60, -0.6, 140); scene.add(ground);

    // Yo'l lentasi
    const rp = [], ru = [], ri = [];
    for (let i = 0; i <= M; i++) {
      const k = i % M, x = this.px[k], y = this.py[k] + 0.02, z = this.pz[k], sx = this.sx[k], sz = this.sz[k];
      rp.push(x - sx * W / 2, y, z - sz * W / 2, x + sx * W / 2, y, z + sz * W / 2); ru.push(0, i * this.step / 14, 1, i * this.step / 14);
      if (i < M) { const a = i * 2; ri.push(a, a + 2, a + 1, a + 1, a + 2, a + 3); }
    }
    const rg = own(new THREE.BufferGeometry()); rg.setAttribute('position', new THREE.Float32BufferAttribute(rp, 3)); rg.setAttribute('uv', new THREE.Float32BufferAttribute(ru, 2)); rg.setIndex(ri); rg.computeVertexNormals();
    const rt = own(roadTex(T));
    const roadMat = own(T.wet && !lq ? new THREE.MeshPhongMaterial({ map: rt, shininess: 90, specular: 0x50506a }) : new THREE.MeshLambertMaterial({ map: rt }));
    scene.add(new THREE.Mesh(rg, roadMat));
    // To'siqlar (ikki tomonda) + neon chiziq + yorug'lik halosi
    const ribbon = (off, y0, y1, uScale) => {
      const p = [], u = [], idx = [];
      for (let i = 0; i <= M; i++) {
        const k = i % M, x = this.px[k] + this.sx[k] * off, z = this.pz[k] + this.sz[k] * off, y = this.py[k];
        p.push(x, y + y0, z, x, y + y1, z); u.push(i * this.step / uScale, 0, i * this.step / uScale, 1);
        if (i < M) { const a = i * 2; idx.push(a, a + 1, a + 2, a + 1, a + 3, a + 2); }
      }
      const g = own(new THREE.BufferGeometry()); g.setAttribute('position', new THREE.Float32BufferAttribute(p, 3)); g.setAttribute('uv', new THREE.Float32BufferAttribute(u, 2)); g.setIndex(idx); g.computeVertexNormals(); return g;
    };
    const strip = own(stripTex());
    [-1, 1].forEach((sd, n) => {
      const col = T.neon[n], css = '#' + new THREE.Color(col).getHexString();
      const wt = own(wallTex(css)); wt.repeat.set(1, 1);
      const wall = new THREE.Mesh(ribbon(sd * (W / 2 + 0.3), -0.3, 1.1, 8), own(new THREE.MeshLambertMaterial({ map: wt, side: THREE.DoubleSide, emissive: col, emissiveIntensity: 0.15 })));
      scene.add(wall);
      const line = new THREE.Mesh(ribbon(sd * (W / 2 + 0.28), 1.1, 1.3, 50), own(new THREE.MeshBasicMaterial({ color: col, side: THREE.DoubleSide })));
      scene.add(line);
      if (!lq) {
        const halo = new THREE.Mesh(ribbon(sd * (W / 2 + 0.26), 0.2, 2.2, 50), own(new THREE.MeshBasicMaterial({ color: col, map: strip, transparent: true, opacity: 0.45, blending: THREE.AdditiveBlending, depthWrite: false, side: THREE.DoubleSide })));
        scene.add(halo);
      }
    });
    // Start/finish chizig'i + arka
    const s0 = this.at(0, 0);
    const fl = new THREE.Mesh(own(new THREE.PlaneGeometry(W, 2.4)), own(new THREE.MeshBasicMaterial({ map: own(checkerTex()), transparent: true, opacity: 0.9 })));
    fl.rotation.x = -Math.PI / 2; fl.rotation.z = -s0.head; fl.position.set(s0.x, s0.y + 0.04, s0.z); scene.add(fl);
    const arch = new THREE.Group(), am = own(new THREE.MeshLambertMaterial({ color: 0x22232b })), an = own(new THREE.MeshBasicMaterial({ color: T.neon[0] })), bx = own(new THREE.BoxGeometry(1, 1, 1));
    const pl = (sx, sy, sz, x, y, z, m) => { const o = new THREE.Mesh(bx, m); o.scale.set(sx, sy, sz); o.position.set(x, y, z); arch.add(o); };
    pl(1, 9, 1, -W / 2 - 1.2, 4.5, 0, am); pl(1, 9, 1, W / 2 + 1.2, 4.5, 0, am); pl(W + 3.4, 1.6, 1.2, 0, 9, 0, am); pl(W + 3.4, 0.25, 1.25, 0, 8.1, 0, an); pl(W + 3.4, 0.25, 1.25, 0, 9.9, 0, an);
    arch.position.set(s0.x, s0.y, s0.z); arch.rotation.y = s0.head; scene.add(arch);
    const bannerCv = cv(512, 64), bg = bannerCv[1]; bg.fillStyle = '#0b0b12'; bg.fillRect(0, 0, 512, 64); bg.font = '900 44px Arial'; bg.textAlign = 'center'; bg.fillStyle = '#' + new THREE.Color(T.neon[1]).getHexString(); bg.fillText('NEON  RUSH', 256, 48);
    const ban = new THREE.Mesh(own(new THREE.PlaneGeometry(W, 1.2)), own(new THREE.MeshBasicMaterial({ map: own(new THREE.CanvasTexture(bannerCv[0])), side: THREE.DoubleSide })));
    ban.position.set(0, 9, -0.62); ban.rotation.y = Math.PI; arch.add(ban);

    // Trassadan uzoqlikni tekshirish (manzara yo'lga tushmasin)
    const far = (x, z, r) => { for (let i = 0; i < M; i += 2) { const dx = x - this.px[i], dz = z - this.pz[i]; if (dx * dx + dz * dz < r * r) return false; } return true; };
    const m4 = new THREE.Matrix4(), q = new THREE.Quaternion(), e = new THREE.Euler(), v = new THREE.Vector3(), sc = new THREE.Vector3(), col = new THREE.Color();
    const box = own(new THREE.BoxGeometry(1, 1, 1)); box.translate(0, 0.5, 0);
    if (T.kind === 'city') {
      const n = lq ? 140 : hq ? 320 : 230, list = [];
      for (let tries = 0; list.length < n && tries < n * 30; tries++) {
        const i = (Math.random() * M) | 0, side = Math.random() < 0.5 ? -1 : 1, off = W / 2 + 10 + Math.pow(Math.random(), 1.6) * 140;
        const x = this.px[i] + this.sx[i] * off * side, z = this.pz[i] + this.sz[i] * off * side, w = U.rand(10, 22), dd = U.rand(10, 22);
        if (!far(x, z, W / 2 + Math.max(w, dd) * 0.75 + 3)) continue;
        if (list.some((b) => Math.abs(b.x - x) < (b.w + w) / 2 + 2 && Math.abs(b.z - z) < (b.d + dd) / 2 + 2)) continue;
        list.push({ x, z, w, d: dd, h: U.rand(14, 30) + Math.pow(Math.random(), 3) * 90, r: this.head[i] });
      }
      const wt = own(windowTex(T));
      const bm = own(new THREE.MeshLambertMaterial({ color: 0xffffff, emissive: 0xffffff, emissiveMap: wt, emissiveIntensity: 0.9 }));
      const im = new THREE.InstancedMesh(box, bm, list.length);
      list.forEach((b, k) => { e.set(0, b.r, 0); q.setFromEuler(e); m4.compose(v.set(b.x, -0.5, b.z), q, sc.set(b.w, b.h, b.d)); im.setMatrixAt(k, m4); im.setColorAt(k, col.set(U.pick(T.bld))); });
      im.instanceMatrix.needsUpdate = true; im.instanceColor.needsUpdate = true; scene.add(im);
      // Tom neon belgilari
      const signs = list.filter(() => Math.random() < 0.35), sm = own(new THREE.MeshBasicMaterial({ color: 0xffffff }));
      const sIm = new THREE.InstancedMesh(box, sm, signs.length);
      signs.forEach((b, k) => { e.set(0, b.r, 0); q.setFromEuler(e); m4.compose(v.set(b.x, b.h - 0.5, b.z), q, sc.set(b.w * 0.7, 1.4, 0.4)); sIm.setMatrixAt(k, m4); sIm.setColorAt(k, col.set(U.pick(T.neon.concat([0xffffff])))); });
      sIm.instanceMatrix.needsUpdate = true; if (sIm.instanceColor) sIm.instanceColor.needsUpdate = true; scene.add(sIm);
    } else {
      // Kanyon: qoyalar va mezalar
      const rg2 = own(new THREE.DodecahedronGeometry(1, 0)), rm = own(new THREE.MeshLambertMaterial({ map: own(rockTex()), color: 0xffffff }));
      const n = lq ? 110 : hq ? 240 : 170, rocks = [];
      for (let tries = 0; rocks.length < n && tries < n * 30; tries++) {
        const i = (Math.random() * M) | 0, side = Math.random() < 0.5 ? -1 : 1, off = W / 2 + 8 + Math.pow(Math.random(), 1.4) * 170, s = U.rand(6, 26) * (off > 60 ? 1.8 : 1);
        const x = this.px[i] + this.sx[i] * off * side, z = this.pz[i] + this.sz[i] * off * side;
        if (!far(x, z, W / 2 + s + 2)) continue; rocks.push([x, z, s, this.py[i]]);
      }
      const im = new THREE.InstancedMesh(rg2, rm, rocks.length);
      rocks.forEach(([x, z, s, y], k) => { e.set(Math.random(), Math.random() * 6, Math.random() * 0.4); q.setFromEuler(e); m4.compose(v.set(x, y - s * 0.3, z), q, sc.set(s, s * U.rand(0.8, 2.6), s)); im.setMatrixAt(k, m4); im.setColorAt(k, col.set(U.pick(T.rock))); });
      im.instanceMatrix.needsUpdate = true; im.instanceColor.needsUpdate = true; scene.add(im);
      // Uzoqdagi mezalar (silindr)
      const cg = own(new THREE.CylinderGeometry(1, 1.25, 1, 8)), cm = new THREE.InstancedMesh(cg, rm, 26);
      for (let k = 0; k < 26; k++) { const a = k / 26 * Math.PI * 2, r = U.rand(520, 700), s = U.rand(40, 110); m4.compose(v.set(60 + Math.cos(a) * r, U.rand(20, 50), 140 + Math.sin(a) * r), q.identity(), sc.set(s, U.rand(60, 130), s)); cm.setMatrixAt(k, m4); cm.setColorAt(k, col.set(U.pick(T.rock)).multiplyScalar(0.8)); }
      cm.instanceMatrix.needsUpdate = true; cm.instanceColor.needsUpdate = true; scene.add(cm);
    }
    // Ko'cha chiroqlari: ustun (instanced) + yorug'lik (Points — bitta draw call)
    const lamps = [], lstep = Math.max(1, Math.round((lq ? 44 : 30) / this.step));
    for (let i = 0; i < M; i += lstep) for (const sd of [-1, 1]) if ((i / lstep + (sd > 0 ? 1 : 0)) % 2 === 0) lamps.push([this.px[i] + this.sx[i] * sd * (W / 2 + 1.6), this.py[i], this.pz[i] + this.sz[i] * sd * (W / 2 + 1.6), this.head[i], sd]);
    const pg = own(new THREE.BoxGeometry(0.25, 8, 0.25)); pg.translate(0, 4, 0);
    const pIm = new THREE.InstancedMesh(pg, own(new THREE.MeshLambertMaterial({ color: 0x2a2b33 })), lamps.length);
    const gp = [];
    lamps.forEach(([x, y, z, h, sd], k) => { m4.makeTranslation(x, y - 0.3, z); pIm.setMatrixAt(k, m4); gp.push(x - this.sx[0] * 0, y + 8.1, z); });
    pIm.instanceMatrix.needsUpdate = true; scene.add(pIm);
    const glg = own(new THREE.BufferGeometry()); glg.setAttribute('position', new THREE.Float32BufferAttribute(gp, 3));
    scene.add(new THREE.Points(glg, own(new THREE.PointsMaterial({ map: glow, color: T.lamp, size: 9, sizeAttenuation: true, transparent: true, depthWrite: false, blending: THREE.AdditiveBlending }))));
    if (T.wet && !lq) {       // ho'l asfaltdagi aks (yo'lga tushgan yorug'lik dog'lari)
      const rp2 = []; lamps.forEach(([x, y, z, h, sd], k) => { const i = (k * lstep / 2) | 0; rp2.push(x, y + 0.06, z); });
      const rfg = own(new THREE.BufferGeometry()); rfg.setAttribute('position', new THREE.Float32BufferAttribute(rp2, 3));
      scene.add(new THREE.Points(rfg, own(new THREE.PointsMaterial({ map: glow, color: T.lamp, size: 14, transparent: true, opacity: 0.35, depthWrite: false, blending: THREE.AdditiveBlending }))));
    }
    this.glow = glow;
  };
  P.dispose = function () { for (const d of this.disp || []) { try { d.dispose(); } catch (e) { /* */ } } this.disp = []; };

  NR.World = { TRACKS, Track, list: () => Object.keys(TRACKS) };
})();
