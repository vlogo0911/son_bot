/* CLASSIC STRIKE — MapSystem: 3 ta original xarita (grid), instanced 3D devorlar, collision, 3D raycast (DDA), A* nav. */
(function () {
  'use strict';
  const CS3D = window.CS3D;
  const S = 2;              // katak o'lchami (metr)
  const N = 28;             // xarita 28×28 katak (56×56 m)
  // Katak turlari: balandlik (m), o'qni/ko'rishni to'sadimi (balandlik bo'yicha), yurish mumkinmi
  const KIND = {
    '.': { h: 0 }, A: { h: 0, site: 'A' }, B: { h: 0, site: 'B' }, t: { h: 0, spawn: 'T' }, u: { h: 0, spawn: 'CT' },
    '#': { h: 4.2, m: 'wall' }, H: { h: 7.5, m: 'tall' }, p: { h: 4.2, m: 'pillar' },
    c: { h: 1.05, m: 'crate' }, C: { h: 2.2, m: 'crate2' }, K: { h: 2.8, m: 'cont' }, v: { h: 1.35, m: 'car' },
  };

  function grid() { const g = []; for (let z = 0; z < N; z++) { g.push([]); for (let x = 0; x < N; x++) g[z].push(x === 0 || z === 0 || x === N - 1 || z === N - 1 ? '#' : '.'); } return g; }
  function rect(g, x, z, w, h, ch) { for (let j = z; j < z + h; j++) for (let i = x; i < x + w; i++) if (i > 0 && j > 0 && i < N - 1 && j < N - 1) g[j][i] = ch; }
  function put(g, list, ch) { for (const [x, z] of list) if (x > 0 && z > 0 && x < N - 1 && z < N - 1) g[z][x] = ch; }

  // ── Xaritalar (original dizayn) ──
  const MAPS = {
    desert: {
      name: 'Desert Base', sub: 'Cho‘ldagi harbiy baza', sky: 0xd8c39a, fog: [0xd8c39a, 30, 95], sun: 0xfff1d0, amb: [0xfff4dc, 0x8a6f48],
      floor: ['#c9a56a', '#b8945a'], wall: 0xd2b27a, tall: 0xc9a46c, crate: 0x8a5a2b, crate2: 0x7a4e24, pillar: 0xbfa070, cont: 0x7c6a4a, car: 0x6b5a40,
      build(g) {
        rect(g, 11, 1, 6, 3, 'u'); rect(g, 11, 24, 6, 3, 't');
        rect(g, 2, 2, 7, 6, 'A'); rect(g, 19, 2, 7, 6, 'B');
        put(g, [[3, 3], [4, 3], [7, 6]], 'c'); put(g, [[6, 4], [2, 6]], 'C');
        put(g, [[21, 4], [22, 4]], 'C'); put(g, [[24, 6], [19, 3]], 'c');
        rect(g, 1, 8, 9, 1, '#'); rect(g, 3, 8, 2, 1, '.'); rect(g, 18, 8, 9, 1, '#'); rect(g, 23, 8, 2, 1, '.');
        rect(g, 10, 7, 8, 1, '#'); rect(g, 13, 7, 2, 1, '.');
        rect(g, 6, 9, 4, 12, '#'); rect(g, 6, 14, 4, 2, '.');
        rect(g, 18, 9, 4, 12, '#'); rect(g, 18, 11, 4, 2, '.');
        rect(g, 22, 10, 1, 9, '#'); rect(g, 22, 16, 1, 1, '.');
        put(g, [[13, 13], [14, 13], [13, 14], [14, 14]], 'C'); put(g, [[11, 10], [16, 18], [11, 19], [16, 10]], 'c');
        put(g, [[2, 12], [3, 12], [4, 17]], 'c'); put(g, [[24, 13], [25, 19]], 'c'); put(g, [[12, 16], [15, 11]], 'p');
        rect(g, 1, 21, 9, 1, '#'); rect(g, 3, 21, 2, 1, '.'); rect(g, 18, 21, 9, 1, '#'); rect(g, 23, 21, 2, 1, '.');
        rect(g, 10, 22, 8, 1, '#'); rect(g, 13, 22, 2, 1, '.'); rect(g, 10, 22, 1, 1, '.'); rect(g, 17, 22, 1, 1, '.');
        put(g, [[3, 24], [24, 24], [6, 25], [21, 25]], 'c');
      },
    },
    urban: {
      name: 'Urban Strike', sub: 'Tor ko‘chalar va binolar', sky: 0x9fb3c8, fog: [0x9fb3c8, 25, 85], sun: 0xe8f0ff, amb: [0xdde8ff, 0x4a4f5a],
      floor: ['#5d6168', '#53575e'], wall: 0x8d8f94, tall: 0x9a8f86, crate: 0x6b5435, crate2: 0x5d4a30, pillar: 0x7a7c80, cont: 0x4a6a8a, car: 0x9c2f2f,
      build(g) {
        rect(g, 10, 1, 8, 2, 'u'); rect(g, 10, 25, 8, 2, 't');
        for (const [x, z, w, h] of [[2, 3, 6, 5], [11, 4, 6, 4], [20, 3, 6, 5], [2, 11, 5, 6], [21, 11, 5, 6], [2, 20, 6, 5], [11, 20, 6, 4], [20, 20, 6, 5]]) rect(g, x, z, w, h, 'H');
        rect(g, 4, 3, 2, 5, '.'); rect(g, 22, 13, 4, 2, '.'); rect(g, 13, 20, 2, 4, '.'); rect(g, 2, 13, 3, 2, '.');
        rect(g, 10, 10, 8, 8, 'A'); rect(g, 13, 13, 2, 2, 'C'); put(g, [[11, 11], [16, 16]], 'c');
        rect(g, 8, 12, 1, 4, '#'); rect(g, 19, 12, 1, 4, '#');
        rect(g, 22, 8, 4, 2, 'B'); rect(g, 22, 17, 4, 2, 'B');
        put(g, [[9, 5], [18, 6], [9, 22], [18, 21], [5, 9], [23, 9], [5, 18], [24, 19]], 'v');
        put(g, [[1, 9], [26, 9], [1, 18], [26, 18], [14, 8], [14, 19]], 'c');
        put(g, [[8, 9], [19, 9], [8, 18], [19, 18]], 'p');
      },
    },
    warehouse: {
      name: 'Warehouse', sub: 'Ombor, konteynerlar, yashirinish joylari', sky: 0x2a2f38, fog: [0x2a2f38, 18, 60], sun: 0xffe0b0, amb: [0xb9c4d8, 0x2a2a30],
      floor: ['#4a4e55', '#43474e'], wall: 0x5b6068, tall: 0x50555c, crate: 0x8b6a3c, crate2: 0x7a5c32, pillar: 0x6a6e75, cont: 0x2f6f5a, car: 0x6a6e75,
      build(g) {
        rect(g, 1, 1, 4, 4, 'u'); rect(g, 23, 23, 4, 4, 't');
        rect(g, 2, 18, 6, 6, 'A'); rect(g, 20, 3, 6, 6, 'B');
        for (const [x, z, w, h] of [[7, 3, 6, 2], [7, 7, 2, 6], [15, 6, 6, 2], [11, 11, 6, 2], [11, 15, 6, 2], [19, 14, 2, 6], [7, 21, 6, 2], [15, 23, 6, 2]]) rect(g, x, z, w, h, 'K');
        rect(g, 13, 1, 1, 4, '#'); rect(g, 14, 22, 1, 5, '#');
        put(g, [[3, 20], [4, 20], [6, 22]], 'C'); put(g, [[21, 5], [24, 7], [22, 4]], 'C');
        put(g, [[5, 10], [9, 16], [18, 10], [22, 17], [12, 9], [16, 19], [3, 14], [25, 13]], 'c');
        for (const [x, z] of [[5, 5], [22, 22], [9, 19], [18, 8], [5, 14], [22, 13]]) put(g, [[x, z]], 'p');
      },
    },
  };

  // ── Map obyekti ──
  function GameMap(id) {
    const def = MAPS[id] || MAPS.desert;
    const g = grid(); def.build(g);
    this.id = id; this.def = def; this.g = g; this.N = N; this.S = S;
    this.h = []; this.sites = { A: [], B: [] }; this.spawns = { T: [], CT: [] }; this.free = []; this.cover = [];
    for (let z = 0; z < N; z++) { this.h.push(new Float32Array(N)); for (let x = 0; x < N; x++) {
      const k = KIND[g[z][x]] || KIND['.']; this.h[z][x] = k.h;
      if (!k.h) { this.free.push([x, z]); if (k.site) this.sites[k.site].push([x, z]); if (k.spawn) this.spawns[k.spawn].push([x, z]); }
    } }
    // Faqat T spawnidan yetib boriladigan kataklar (ulanganlik)
    const reach = new Set(), start = this.spawns.T[0] || this.free[0], q = [start];
    reach.add(start[0] + ',' + start[1]);
    while (q.length) { const [x, z] = q.shift(); for (const [dx, dz] of [[1, 0], [-1, 0], [0, 1], [0, -1]]) { const nx = x + dx, nz = z + dz, k = nx + ',' + nz; if (!reach.has(k) && this.walk(nx, nz)) { reach.add(k); q.push([nx, nz]); } } }
    this.reach = reach;
    this.free = this.free.filter(([x, z]) => reach.has(x + ',' + z));
    for (const [x, z] of this.free) { let n = 0; for (const [dx, dz] of [[1, 0], [-1, 0], [0, 1], [0, -1]]) if (this.hc(x + dx, z + dz) >= 1) n++; if (n) this.cover.push([x, z]); }
    for (const k of ['A', 'B']) this.sites[k] = this.sites[k].filter(([x, z]) => reach.has(x + ',' + z));
    const cen = (l) => l.length ? [l.reduce((s, c) => s + c[0], 0) / l.length, l.reduce((s, c) => s + c[1], 0) / l.length] : [N / 2, N / 2];
    this.siteC = { A: cen(this.sites.A).map((v) => v * S + S / 2), B: cen(this.sites.B).map((v) => v * S + S / 2) };
  }
  const P = GameMap.prototype;
  P.hc = function (x, z) { return x < 0 || z < 0 || x >= N || z >= N ? 99 : this.h[z][x]; };
  P.walk = function (x, z) { return this.hc(x, z) === 0; };
  P.cell = (v) => Math.floor(v / S);
  P.center = (c) => c * S + S / 2;
  P.siteAt = function (x, z) { const cx = this.cell(x), cz = this.cell(z); if (cx < 0 || cz < 0 || cx >= N || cz >= N) return null; const k = KIND[this.g[cz][cx]]; return k && k.site || null; };
  // Doira ostidagi eng baland katak (oyoq ostidagi yer)
  P.heightAt = function (x, z, r) {
    let m = 0;
    const x0 = this.cell(x - r), x1 = this.cell(x + r), z0 = this.cell(z - r), z1 = this.cell(z + r);
    for (let j = z0; j <= z1; j++) for (let i = x0; i <= x1; i++) {
      const h = this.hc(i, j); if (h <= m) continue;
      const nx = Math.max(i * S, Math.min(x, i * S + S)), nz = Math.max(j * S, Math.min(z, j * S + S));
      if ((nx - x) * (nx - x) + (nz - z) * (nz - z) < r * r) m = h;
    }
    return m;
  };
  // Harakat: o'qlar bo'yicha alohida, step-up 0.45 m (sakrab qutiga chiqish mumkin)
  P.move = function (e, dx, dz, r, feet) {
    const step = 0.45;
    if (dx && this.heightAt(e.x + dx, e.z, r) <= feet + step) e.x += dx;
    if (dz && this.heightAt(e.x, e.z + dz, r) <= feet + step) e.z += dz;
  };
  // 3D raycast: devor/quti yuzasi yoki yer. {d, x,y,z, nx,ny,nz}
  P.ray = function (ox, oy, oz, dx, dy, dz, max) {
    let best = max, nx = 0, ny = 0, nz = 0;
    if (dy < -1e-6) { const tg = -oy / dy; if (tg > 0 && tg < best) { best = tg; nx = 0; ny = 1; nz = 0; } }
    let cx = this.cell(ox), cz = this.cell(oz);
    const sx = dx > 0 ? 1 : -1, sz = dz > 0 ? 1 : -1;
    const tdx = Math.abs(dx) > 1e-9 ? S / Math.abs(dx) : Infinity, tdz = Math.abs(dz) > 1e-9 ? S / Math.abs(dz) : Infinity;
    let tmx = Math.abs(dx) > 1e-9 ? ((dx > 0 ? (cx + 1) * S - ox : ox - cx * S) / Math.abs(dx)) : Infinity;
    let tmz = Math.abs(dz) > 1e-9 ? ((dz > 0 ? (cz + 1) * S - oz : oz - cz * S) / Math.abs(dz)) : Infinity;
    let t0 = 0, side = -1;
    for (let it = 0; it < 80 && t0 < best; it++) {
      const h = this.hc(cx, cz), t1 = Math.min(tmx, tmz, best);
      if (h > 0) {
        const y0 = oy + dy * t0;
        if (y0 < h && t0 > 0) { // yon yuzaga tegdi
          if (t0 < best) { best = t0; ny = 0; if (side === 0) { nx = -sx; nz = 0; } else { nx = 0; nz = -sz; } }
          break;
        }
        const y1 = oy + dy * t1;
        if (y1 < h && dy < 0) { const tt = (h - oy) / dy; if (tt >= t0 && tt < best) { best = tt; nx = 0; ny = 1; nz = 0; } break; }
        if (t0 === 0 && oy < h) { best = 0; break; }
      }
      if (tmx < tmz) { t0 = tmx; tmx += tdx; cx += sx; side = 0; } else { t0 = tmz; tmz += tdz; cz += sz; side = 1; }
      if (cx < 0 || cz < 0 || cx >= N || cz >= N) { if (t0 < best) { best = t0; ny = 0; nx = side === 0 ? -sx : 0; nz = side === 1 ? -sz : 0; } break; }
    }
    return { d: best, x: ox + dx * best, y: oy + dy * best, z: oz + dz * best, nx, ny, nz };
  };
  P.los = function (ax, ay, az, bx, by, bz) {
    const dx = bx - ax, dy = by - ay, dz = bz - az, d = Math.hypot(dx, dy, dz);
    if (d < 0.01) return true;
    return this.ray(ax, ay, az, dx / d, dy / d, dz / d, d).d >= d - 0.05;
  };
  // A* (8 yo'nalish, burchak kesmaydi). Natija: katak markazlari ro'yxati
  P.path = function (sx, sz, tx, tz) {
    const a = [this.cell(sx), this.cell(sz)], b = [this.cell(tx), this.cell(tz)];
    if (!this.walk(b[0], b[1])) { const nb = this.nearestFree(b[0], b[1]); if (!nb) return null; b[0] = nb[0]; b[1] = nb[1]; }
    if (!this.walk(a[0], a[1])) { const na = this.nearestFree(a[0], a[1]); if (!na) return null; a[0] = na[0]; a[1] = na[1]; }
    const key = (x, z) => z * N + x, start = key(a[0], a[1]), goal = key(b[0], b[1]);
    const gS = new Float32Array(N * N).fill(1e9), from = new Int32Array(N * N).fill(-1), closed = new Uint8Array(N * N);
    const open = [start]; gS[start] = 0;
    const hf = (k) => { const x = k % N, z = (k / N) | 0; const ddx = Math.abs(x - b[0]), ddz = Math.abs(z - b[1]); return Math.max(ddx, ddz) + 0.414 * Math.min(ddx, ddz); };
    let guard = 0;
    while (open.length && guard++ < 2000) {
      let bi = 0, bf = 1e9;
      for (let i = 0; i < open.length; i++) { const f = gS[open[i]] + hf(open[i]); if (f < bf) { bf = f; bi = i; } }
      const cur = open.splice(bi, 1)[0];
      if (cur === goal) break;
      closed[cur] = 1;
      const x = cur % N, z = (cur / N) | 0;
      for (let dz = -1; dz <= 1; dz++) for (let dx = -1; dx <= 1; dx++) {
        if (!dx && !dz) continue;
        const nx = x + dx, nz = z + dz; if (!this.walk(nx, nz)) continue;
        if (dx && dz && (!this.walk(x + dx, z) || !this.walk(x, z + dz))) continue;
        const k = key(nx, nz); if (closed[k]) continue;
        const ng = gS[cur] + (dx && dz ? 1.414 : 1);
        if (ng < gS[k]) { gS[k] = ng; from[k] = cur; if (open.indexOf(k) < 0) open.push(k); }
      }
    }
    if (from[goal] < 0 && goal !== start) return null;
    const out = []; let k = goal;
    while (k !== start && k >= 0) { out.push([this.center(k % N), this.center((k / N) | 0)]); k = from[k]; }
    out.reverse();
    return out;
  };
  P.nearestFree = function (x, z) {
    for (let r = 0; r < 6; r++) for (let dz = -r; dz <= r; dz++) for (let dx = -r; dx <= r; dx++) if (this.walk(x + dx, z + dz) && this.reach.has((x + dx) + ',' + (z + dz))) return [x + dx, z + dz];
    return null;
  };
  P.randomFree = function (filter) {
    const list = filter ? this.free.filter(filter) : this.free;
    const c = list.length ? list[(Math.random() * list.length) | 0] : this.free[0];
    return [this.center(c[0]) + (Math.random() - 0.5) * 0.6, this.center(c[1]) + (Math.random() - 0.5) * 0.6];
  };
  P.spawnPoint = function (team, avoid) {
    let list = (this.spawns[team] || []).filter(([x, z]) => this.reach.has(x + ',' + z));
    if (!list.length || avoid) {
      // Deathmatch: dushmanlardan uzoqroq tasodifiy joy
      const cand = list.length && !avoid ? list : this.free;
      let best = null, bd = -1;
      for (let i = 0; i < 14; i++) {
        const c = cand[(Math.random() * cand.length) | 0];
        let dmin = 1e9; for (const e of avoid || []) dmin = Math.min(dmin, Math.hypot(this.center(c[0]) - e.x, this.center(c[1]) - e.z));
        if (dmin > bd) { bd = dmin; best = c; }
      }
      list = [best];
    }
    const c = list[(Math.random() * list.length) | 0];
    return [this.center(c[0]) + (Math.random() - 0.5) * 0.8, this.center(c[1]) + (Math.random() - 0.5) * 0.8];
  };

  // ── 3D qurilish (instancing) ──
  function canvasTex(c1, c2, kind) {
    const cv = document.createElement('canvas'); cv.width = cv.height = 64;
    const g = cv.getContext('2d'); g.fillStyle = c1; g.fillRect(0, 0, 64, 64);
    for (let i = 0; i < 260; i++) { g.fillStyle = Math.random() < 0.5 ? c2 : 'rgba(255,255,255,0.05)'; g.fillRect((Math.random() * 64) | 0, (Math.random() * 64) | 0, 2, 2); }
    if (kind === 'tile') { g.strokeStyle = 'rgba(0,0,0,.18)'; g.lineWidth = 2; g.strokeRect(0, 0, 64, 64); }
    if (kind === 'brick') { g.strokeStyle = 'rgba(0,0,0,.18)'; for (let y = 0; y < 64; y += 16) { g.beginPath(); g.moveTo(0, y); g.lineTo(64, y); g.stroke(); for (let x = (y / 16) % 2 ? 16 : 0; x < 64; x += 32) { g.beginPath(); g.moveTo(x, y); g.lineTo(x, y + 16); g.stroke(); } } }
    if (kind === 'crate') { g.strokeStyle = 'rgba(30,15,0,.55)'; g.lineWidth = 5; g.strokeRect(3, 3, 58, 58); g.beginPath(); g.moveTo(4, 4); g.lineTo(60, 60); g.stroke(); }
    if (kind === 'cont') { g.fillStyle = 'rgba(0,0,0,.2)'; for (let x = 0; x < 64; x += 8) g.fillRect(x, 0, 3, 64); }
    const t = new THREE.CanvasTexture(cv); t.wrapS = t.wrapT = THREE.RepeatWrapping; t.magFilter = THREE.NearestFilter; t.minFilter = THREE.LinearMipMapLinearFilter;
    return t;
  }
  P.build = function (scene, quality) {
    const def = this.def, disp = (this.disposables = []);
    scene.background = new THREE.Color(def.sky);
    scene.fog = new THREE.Fog(def.fog[0], def.fog[1], def.fog[2]);
    const hemi = new THREE.HemisphereLight(def.amb[0], def.amb[1], 0.75); scene.add(hemi);
    const sun = new THREE.DirectionalLight(def.sun, 0.85); sun.position.set(30, 60, 18); scene.add(sun); scene.add(sun.target);
    sun.target.position.set(N * S / 2, 0, N * S / 2);
    if (quality === 'high') {
      sun.castShadow = true; sun.shadow.mapSize.set(1024, 1024);
      Object.assign(sun.shadow.camera, { left: -40, right: 40, top: 40, bottom: -40, near: 10, far: 140 });
      sun.position.set(N * S / 2 + 25, 60, N * S / 2 + 12);
    }
    // Pol
    const ft = canvasTex(def.floor[0], def.floor[1], 'tile'); ft.repeat.set(N, N);
    const fm = new THREE.MeshLambertMaterial({ map: ft }), fg = new THREE.PlaneGeometry(N * S, N * S);
    const floor = new THREE.Mesh(fg, fm); floor.rotation.x = -Math.PI / 2; floor.position.set(N * S / 2, 0, N * S / 2); floor.receiveShadow = true; scene.add(floor);
    disp.push(ft, fm, fg);
    // Bomba hududlari belgisi
    for (const k of ['A', 'B']) {
      if (!this.sites[k].length) continue;
      const cv = document.createElement('canvas'); cv.width = cv.height = 128; const g = cv.getContext('2d');
      g.strokeStyle = 'rgba(200,30,30,.75)'; g.lineWidth = 8; g.strokeRect(8, 8, 112, 112);
      g.fillStyle = 'rgba(200,30,30,.75)'; g.font = 'bold 84px Arial'; g.textAlign = 'center'; g.textBaseline = 'middle'; g.fillText(k, 64, 70);
      const tx = new THREE.CanvasTexture(cv), mm = new THREE.MeshBasicMaterial({ map: tx, transparent: true, depthWrite: false }), gg = new THREE.PlaneGeometry(5, 5);
      const m = new THREE.Mesh(gg, mm); m.rotation.x = -Math.PI / 2; m.position.set(this.siteC[k][0], 0.02, this.siteC[k][1]); scene.add(m);
      disp.push(tx, mm, gg);
    }
    // Instanced bloklar
    const types = {
      wall: [def.wall, 'brick'], tall: [def.tall, 'brick'], pillar: [def.pillar, 'tile'], crate: [def.crate, 'crate'],
      crate2: [def.crate2, 'crate'], cont: [def.cont, 'cont'], car: [def.car, 'tile'],
    };
    const cells = {};
    for (let z = 0; z < N; z++) for (let x = 0; x < N; x++) { const k = KIND[this.g[z][x]]; if (k && k.m) (cells[k.m] = cells[k.m] || []).push([x, z, k.h]); }
    const box = new THREE.BoxGeometry(1, 1, 1); disp.push(box);
    const m4 = new THREE.Matrix4(), col = new THREE.Color();
    const CONT = [0x2f6f5a, 0x8a3b2f, 0x2f4f8a, 0x8a7a2f, 0x5a5a5a];
    for (const m of Object.keys(cells)) {
      const list = cells[m], [c, tk] = types[m];
      const tex = canvasTex('#' + new THREE.Color(c).getHexString(), 'rgba(0,0,0,.12)', tk);
      const mat = new THREE.MeshLambertMaterial({ map: tex, color: 0xffffff });
      const im = new THREE.InstancedMesh(box, mat, list.length);
      list.forEach(([x, z, h], i) => {
        const shrink = m === 'pillar' ? 0.55 : m === 'car' ? 0.85 : m === 'crate' ? 0.92 : 1;
        m4.makeScale(S * shrink, h, S * (m === 'car' ? 0.6 : shrink)); m4.setPosition(x * S + S / 2, h / 2, z * S + S / 2);
        im.setMatrixAt(i, m4);
        col.set(m === 'cont' ? CONT[(x * 7 + z * 3) % CONT.length] : 0xffffff).multiplyScalar(0.85 + ((x * 13 + z * 7) % 5) * 0.04);
        im.setColorAt(i, col);
      });
      im.instanceMatrix.needsUpdate = true; if (im.instanceColor) im.instanceColor.needsUpdate = true;
      im.castShadow = quality === 'high'; im.receiveShadow = quality === 'high';
      scene.add(im); disp.push(tex, mat);
    }
  };
  P.dispose = function () { for (const d of this.disposables || []) { try { d.dispose(); } catch (e) { /* */ } } this.disposables = []; };

  CS3D.MapSystem = { MAPS, GameMap, S, N, KIND, list: () => Object.keys(MAPS) };
})();
